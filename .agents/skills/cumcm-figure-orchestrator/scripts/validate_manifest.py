#!/usr/bin/env python3
"""Fail-closed validator for routed and completed CUMCM figure manifests."""

from __future__ import annotations

import argparse
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from score_providers import DEFAULT_SCORECARD, eligibility_failures, load_scorecard
from qa_evidence import required_paths, validate_evidence
from verify_numeric import compare_tables

TASK_TYPES = {"data_chart", "flowchart", "network", "map", "conceptual_schematic", "composite"}
STATUSES = {"formal", "alternative", "draft", "excluded"}
COMMON_FORMAL_CHECKS = (
    "collision_check",
    "clipping_check",
    "grayscale_check",
    "export_check",
    "claim_caption_check",
    "visual_review",
)

SCHEMA = Path(__file__).resolve().parents[1] / "assets" / "figure-manifest.schema.json"


def inspect_outputs(figure: dict, base_dir: Path, layout: dict) -> list[str]:
    """Decode assets; file existence and suffix alone never establish an export."""
    try:
        from PIL import Image
    except ImportError:
        return ["export validation unavailable: Pillow is required"]
    errors = []
    outputs = figure.get("outputs", {})
    width = figure.get("final_width_mm") or 0
    png_size = None
    try:
        with Image.open(base_dir / outputs["png"]) as image:
            if image.format != "PNG":
                raise ValueError("PNG output is not a PNG")
            image.verify()
        with Image.open(base_dir / outputs["png"]) as image:
            image.load()
            png_size = image.size
        if width > 0 and png_size[0] / (width / 25.4) < layout.get("min_dpi", 300):
            errors.append("PNG resolution is below min_dpi at final width")
    except (OSError, KeyError, ValueError, TypeError, SyntaxError) as exc:
        errors.append(f"invalid PNG: {exc}")
    for kind in ("svg", "pdf"):
        if not outputs.get(kind):
            continue
        try:
            path = base_dir / outputs[kind]
            if kind == "svg":
                root = ET.parse(path).getroot()
                tags = [node.tag.rsplit("}", 1)[-1] for node in root.iter()]
                if root.tag.rsplit("}", 1)[-1] != "svg" or not set(tags) & {"path", "line", "rect", "circle", "polygon", "polyline", "text", "ellipse"}:
                    raise ValueError("SVG lacks vector marks/text")
                if figure["constraints"]["vector_required"] and "image" in tags:
                    raise ValueError("vector-required SVG embeds raster content")
                box = [float(x) for x in root.attrib.get("viewBox", "").replace(",", " ").split()]
                if len(box) != 4 or not all(math.isfinite(x) for x in box) or min(box[2:]) <= 0:
                    raise ValueError("invalid SVG viewBox")
                if png_size and abs(png_size[0]/png_size[1] / (box[2]/box[3]) - 1) > 0.01:
                    raise ValueError("SVG/PNG aspect mismatch")
                physical = re.fullmatch(r"([0-9.]+)(mm|cm|in|pt)", root.attrib.get("width", ""))
                if physical:
                    mm = float(physical[1]) * {"mm": 1, "cm": 10, "in": 25.4, "pt": 25.4/72}[physical[2]]
                    if abs(mm-width) > 0.5:
                        raise ValueError("SVG physical width differs from final_width_mm")
            else:
                import fitz
                with fitz.open(path) as document:
                    if not document.is_pdf or document.page_count != 1:
                        raise ValueError("figure PDF must contain exactly one PDF page")
                    page = document[0]
                    if not page.get_drawings() and not page.get_text().strip():
                        raise ValueError("PDF has no vector marks/text")
                    if figure["constraints"]["vector_required"] and page.get_images():
                        raise ValueError("vector-required PDF embeds raster content")
                    if abs(page.rect.width*25.4/72-width) > 0.5:
                        raise ValueError("PDF physical width differs from final_width_mm")
        except Exception as exc:
            errors.append(f"invalid {kind.upper()}: {exc}")
    return errors


def _required_text(obj: dict[str, Any], key: str, context: str, errors: list[str]) -> None:
    if not isinstance(obj.get(key), str) or not obj[key].strip():
        errors.append(f"{context}.{key}: required non-empty string")


def _check_pass(qa: dict[str, Any], key: str, context: str, errors: list[str]) -> None:
    check = qa.get(key)
    if not isinstance(check, dict):
        errors.append(f"{context}.qa.{key}: missing check record")
        return
    if check.get("status") != "pass":
        errors.append(f"{context}.qa.{key}: expected pass, got {check.get('status')!r}")
    if not isinstance(check.get("method"), str) or not check["method"].strip():
        errors.append(f"{context}.qa.{key}.method: required non-empty string")


def validate_manifest(
    manifest: dict[str, Any],
    scorecard: dict[str, Any],
    strict: bool = False,
    check_files: bool = False,
    base_dir: Path | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    hash_cache: dict = {}
    base_dir = base_dir or Path.cwd()
    try:
        json.dumps(manifest, allow_nan=False)
        import jsonschema
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        for error in jsonschema.Draft202012Validator(schema).iter_errors(manifest):
            errors.append(f"schema {'.'.join(map(str, error.absolute_path))}: {error.message}")
    except (ImportError, OSError, ValueError) as exc:
        return [f"schema validation unavailable: {exc}"], []
    if errors:
        return errors, warnings
    # Production cannot opt out of physical file validation.
    check_files = check_files or strict
    layout = manifest.get("layout", {})
    if strict:
        if manifest.get("schema_version") != 2:
            errors.append("schema_version: strict production requires version 2; legacy QA is not migrated automatically")
        if manifest.get("delivery_status") != "ready":
            errors.append("delivery_status: strict delivery requires ready")
        if not manifest.get("target_figure_ids"):
            errors.append("target_figure_ids: required delivery coverage")
        if not layout:
            errors.append("layout: required final document geometry")
    if manifest.get("competition_profile") != "cumcm":
        errors.append("competition_profile: expected 'cumcm'")
    _required_text(manifest, "batch_id", "manifest", errors)
    paper = manifest.get("paper")
    if not isinstance(paper, dict):
        errors.append("paper: required object")
    else:
        _required_text(paper, "title", "paper", errors)
        _required_text(paper, "source_path", "paper", errors)

    figures = manifest.get("figures")
    if not isinstance(figures, list) or not figures:
        errors.append("figures: required non-empty array")
        return errors, warnings

    providers = {provider["id"]: provider for provider in scorecard["providers"]}
    seen: set[str] = set()
    formal_count = 0
    def walk(items):
        for item in items:
            yield item
            yield from walk(item.get("panels", []))

    all_figures = list(walk(figures))
    for index, figure in enumerate(all_figures):
        context = f"figures[{index}]"
        if not isinstance(figure, dict):
            errors.append(f"{context}: expected object")
            continue
        figure_id = figure.get("figure_id")
        _required_text(figure, "figure_id", context, errors)
        if figure_id in seen:
            errors.append(f"{context}.figure_id: duplicate {figure_id!r}")
        if isinstance(figure_id, str):
            seen.add(figure_id)
            context = figure_id
        status = figure.get("status")
        if status not in STATUSES:
            errors.append(f"{context}.status: invalid {status!r}")
        task_type = figure.get("task_type")
        if task_type not in TASK_TYPES:
            errors.append(f"{context}.task_type: invalid {task_type!r}")
        for key in ("claim", "caption", "paper_anchor"):
            _required_text(figure, key, context, errors)
        sources = figure.get("sources")
        if not isinstance(sources, list) or not sources or not all(isinstance(x, str) and x.strip() for x in sources):
            errors.append(f"{context}.sources: required non-empty string array")
        constraints = figure.get("constraints")
        if not isinstance(constraints, dict):
            errors.append(f"{context}.constraints: required object")
            constraints = {}
        for key in ("exact_numeric", "exact_text", "vector_required", "reproducible_required"):
            if not isinstance(constraints.get(key), bool):
                errors.append(f"{context}.constraints.{key}: required boolean")

        if status == "excluded":
            _required_text(figure, "exclusion_reason", context, errors)
            continue
        if figure.get("pipeline_state") == "blocked" and not strict:
            _required_text(figure, "blocked_reason", context, errors)
            warnings.append(f"{context}: blocked; not a deliverable")
            continue
        numeric_required = task_type in {"data_chart", "map"} or bool(constraints.get("exact_numeric"))
        route = figure.get("route")
        if not isinstance(route, dict):
            errors.append(f"{context}.route: missing; run route_figures.py")
            route = {}
        provider_id = route.get("provider")
        provider = providers.get(provider_id)
        if provider is None:
            errors.append(f"{context}.route.provider: unknown {provider_id!r}")
        else:
            requirements = {
                "exact_numeric": numeric_required,
                "exact_text": bool(constraints.get("exact_text")),
                "vector_required": bool(constraints.get("vector_required")),
                "reproducible_required": bool(constraints.get("reproducible_required")),
                "formal_final": status == "formal",
            }
            for failure in eligibility_failures(provider, requirements):
                errors.append(f"{context}.route.provider: {provider_id}: {failure}")

        if status != "formal" or not strict:
            continue
        formal_count += 1
        if figure.get("pipeline_state") != "verified":
            errors.append(f"{context}.pipeline_state: required verified; blocked/planned/rendered is not delivery")
        if not isinstance(figure.get("final_width_mm"), (int, float)) or not math.isfinite(figure["final_width_mm"]) or figure["final_width_mm"] <= 0:
            errors.append(f"{context}.final_width_mm: required positive number for formal output")
        available_width = layout.get("page_width_mm", 210)-layout.get("margin_left_mm", 25)-layout.get("margin_right_mm", 25)
        if available_width <= 0 or (figure.get("final_width_mm") or 0) > available_width:
            errors.append(f"{context}.final_width_mm: exceeds document content width {available_width} mm")
        if task_type == "composite":
            if not figure.get("panels") or any(p.get("status") != "formal" for p in figure.get("panels", [])):
                errors.append(f"{context}.panels: composite requires independently verified formal panels")
        if task_type in {"data_chart", "map", "network"} or numeric_required:
            _required_text(figure, "data_source", context, errors)
            _required_text(figure, "code_path", context, errors)
            if not figure.get("data_contract"):
                errors.append(f"{context}.data_contract: required field/unit/transformation contract")
        model = figure.get("data_contract", {}).get("model", {})
        if model.get("reproduction_status") == "blocked" or model.get("solver_status") in {"infeasible", "unbounded", "failed"}:
            errors.append(f"{context}.data_contract.model: unresolved model/solver result cannot support formal delivery")
        if task_type in {"flowchart", "network", "map"} and not figure.get("semantic_contract"):
            errors.append(f"{context}.semantic_contract: required edges/directions/CRS and source mapping")

        outputs = figure.get("outputs")
        if not isinstance(outputs, dict):
            errors.append(f"{context}.outputs: required object for formal output")
            outputs = {}
        for key in ("png", "source"):
            _required_text(outputs, key, f"{context}.outputs", errors)
        if constraints.get("vector_required") and not any(
            isinstance(outputs.get(key), str) and outputs[key].strip() for key in ("svg", "pdf")
        ):
            errors.append(f"{context}.outputs: vector_required needs svg or pdf")

        provenance = figure.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{context}.provenance: required object")
            provenance = {}
        _required_text(provenance, "renderer_version", f"{context}.provenance", errors)
        _required_text(provenance, "verification_method", f"{context}.provenance", errors)
        _required_text(provenance, "render_command", f"{context}.provenance", errors)
        if provenance.get("actual_provider") != provider_id:
            errors.append(f"{context}.provenance.actual_provider: must match the renderer actually routed/executed")
        if not isinstance(provenance.get("ai_assisted"), bool):
            errors.append(f"{context}.provenance.ai_assisted: required boolean")
        ai_assisted = provenance.get("ai_assisted") is True
        if provider and provider.get("capabilities", {}).get("ai_generated") and not ai_assisted:
            errors.append(f"{context}.provenance.ai_assisted: routed provider requires AI disclosure")
        if ai_assisted:
            for key in ("ai_tool_and_version", "prompt_summary", "human_edits"):
                _required_text(provenance, key, f"{context}.provenance", errors)
            if provenance.get("ai_output_adopted") not in {"none", "partial", "full"}:
                errors.append(f"{context}.provenance.ai_output_adopted: invalid or missing")

        qa = figure.get("qa")
        if not isinstance(qa, dict):
            errors.append(f"{context}.qa: required object")
            qa = {}
        for check_name in COMMON_FORMAL_CHECKS:
            _check_pass(qa, check_name, context, errors)
        if numeric_required:
            _check_pass(qa, "numeric_check", context, errors)
        if constraints.get("contains_text", True):
            _check_pass(qa, "ocr_check", context, errors)

        checks = list(COMMON_FORMAL_CHECKS)
        if numeric_required:
            checks.append("numeric_check")
        if constraints.get("contains_text", True):
            checks.append("ocr_check")
        if task_type in {"flowchart", "network", "map"}:
            checks.append("structure_check")
            _check_pass(qa, "structure_check", context, errors)
        # Explicit failures in even optional checks may not be silently discarded.
        for key, check in qa.items():
            if check["status"] in {"fail", "pending"}:
                errors.append(f"{context}.qa.{key}: unresolved {check['status']}")
        for key in checks:
            evidence = qa.get(key, {}).get("evidence")
            if not evidence:
                errors.append(f"{context}.qa.{key}: missing evidence path")
                continue
            try:
                record = json.loads((base_dir / evidence).read_text(encoding="utf-8"))
                for error in validate_evidence(record, figure, paper, layout, key, base_dir, hash_cache):
                    errors.append(f"{context}.qa.{key}: {error}")
            except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
                errors.append(f"{context}.qa.{key}: unreadable/invalid evidence: {exc}")
        if numeric_required and figure.get("data_contract"):
            contract = figure["data_contract"]
            try:
                reference = (base_dir / contract["reference_data"]).resolve()
                plotted = (base_dir / contract["plotted_data"]).resolve()
                if reference == plotted or (base_dir / contract["verification_code"]).resolve() == (base_dir / figure["code_path"]).resolve():
                    raise ValueError("numeric verification needs separate reference/artist data and verification code")
                result = compare_tables(reference, plotted, contract["keys"], contract["numeric_columns"],
                                        contract["atol"], contract["rtol"])
                if result["status"] != "pass":
                    errors.append(f"{context}.numeric_check: recomputation failed: {result['errors']}")
            except (OSError, KeyError, ValueError, TypeError) as exc:
                errors.append(f"{context}.numeric_check: cannot recompute comparison: {exc}")

        if check_files:
            for relative in required_paths(figure, paper):
                if not (base_dir / relative).is_file():
                    errors.append(f"{context}: file not found: {base_dir / relative}")
            errors.extend(f"{context}: {error}" for error in inspect_outputs(figure, base_dir, layout))

    if strict:
        top_formal = {f["figure_id"] for f in figures if f["status"] == "formal"}
        if not top_formal:
            errors.append("no formal figures: planning/exclusion is not a completed figure delivery")
        for target in manifest.get("target_figure_ids", []):
            if target not in top_formal:
                errors.append(f"target_figure_ids: undelivered target {target}")
        formal_count = len(top_formal)
    if strict and not (6 <= formal_count <= 12):
        warnings.append(
            f"formal figure count is {formal_count}; the recommended complete-paper range is 6-12 when supported by evidence"
        )
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--check-files", action="store_true")
    args = parser.parse_args()
    with args.manifest.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    errors, warnings = validate_manifest(
        manifest,
        load_scorecard(args.scorecard),
        strict=args.strict,
        check_files=args.check_files,
        base_dir=args.manifest.parent,
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"PASS: {len(manifest['figures'])} figure(s), {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
