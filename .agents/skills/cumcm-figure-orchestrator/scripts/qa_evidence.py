#!/usr/bin/env python3
"""Bind an actually performed check to the current specification and file bytes.

This is an evidence recorder, not a source of pass decisions or proof of scientific truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def spec_hash(figure: dict, paper: dict, layout: dict) -> str:
    def strip(record: dict) -> dict:
        return {k: [strip(p) for p in v] if k == "panels" else v
                for k, v in record.items() if k not in {"qa", "pipeline_state", "blocked_reason"}}
    content = {"figure": strip(figure), "paper": paper, "layout": layout}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode("utf-8")).hexdigest()


def required_paths(figure: dict, paper: dict) -> set[str]:
    paths = {paper["source_path"], *figure.get("sources", [])}
    paths.update(v for v in figure.get("outputs", {}).values() if v)
    for key in ("data_source", "code_path"):
        if figure.get(key):
            paths.add(figure[key])
    contract = figure.get("data_contract", {})
    for key in ("reference_data", "plotted_data", "verification_code"):
        if contract.get(key):
            paths.add(contract[key])
    paths.update(contract.get("input_files", []))
    paths.update(figure.get("style_policy", {}).get("input_files", []))
    for panel in figure.get("panels", []):
        paths.update(required_paths(panel, paper))
    return paths


def make_evidence(figure: dict, paper: dict, layout: dict, check: str, result: dict,
                  base_dir: Path, checker: str, reviewer: str | None = None) -> dict:
    if result.get("status") not in {"pass", "fail", "pending", "not_applicable"}:
        raise ValueError("result must retain a real check status")
    if not result.get("method") or not checker.strip():
        raise ValueError("method and checker/version are required")
    return {"evidence_version": 1, "figure_id": figure["figure_id"], "check": check,
            "status": result["status"], "method": result["method"], "result": result,
            "checker": checker, "reviewer": reviewer,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "spec_sha256": spec_hash(figure, paper, layout),
            "bindings": {p: sha256(base_dir / p) for p in sorted(required_paths(figure, paper))}}


def validate_evidence(record: dict, figure: dict, paper: dict, layout: dict,
                      check: str, base_dir: Path, hash_cache: dict | None = None) -> list[str]:
    errors = []
    if record.get("evidence_version") != 1 or record.get("figure_id") != figure["figure_id"] or record.get("check") != check:
        errors.append("evidence identity/version mismatch")
    if record.get("status") != "pass" or record.get("result", {}).get("status") != "pass":
        errors.append("evidence result is not pass")
    if not record.get("checker") or not record.get("method"):
        errors.append("missing checker/version or method")
    try:
        checked = datetime.fromisoformat(record["checked_at"])
        if checked.tzinfo is None or checked > datetime.now(timezone.utc):
            errors.append("invalid evidence timestamp")
    except (KeyError, TypeError, ValueError):
        errors.append("missing/invalid evidence timestamp")
    if record.get("spec_sha256") != spec_hash(figure, paper, layout):
        errors.append("stale evidence: specification changed")
    bindings = record.get("bindings", {})
    if not isinstance(bindings, dict) or not required_paths(figure, paper).issubset(bindings):
        errors.append("evidence does not bind every source/code/output")
        return errors
    for path, expected in bindings.items():
        try:
            resolved = (base_dir / path).resolve()
            if hash_cache is None:
                actual = sha256(resolved)
            else:
                stat = resolved.stat()
                key = (resolved, stat.st_size, stat.st_mtime_ns)
                if key not in hash_cache:
                    hash_cache[key] = sha256(resolved)
                actual = hash_cache[key]
            if actual != expected:
                errors.append(f"stale evidence: {path}")
        except OSError:
            errors.append(f"missing evidence input: {path}")
    if check == "visual_review" and not str(record.get("reviewer") or "").strip():
        errors.append("visual review needs reviewer identity (agent or human)")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("figure_id")
    parser.add_argument("check")
    parser.add_argument("result", type=Path, help="JSON output of the check actually performed")
    parser.add_argument("--checker", required=True)
    parser.add_argument("--reviewer")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    def walk(items):
        for item in items:
            yield item
            yield from walk(item.get("panels", []))
    figure = next(f for f in walk(manifest["figures"]) if f["figure_id"] == args.figure_id)
    result = json.loads(args.result.read_text(encoding="utf-8"))
    evidence = make_evidence(figure, manifest["paper"], manifest["layout"], args.check,
                             result, args.manifest.parent, args.checker, args.reviewer)
    evidence["bindings"][str(args.result.resolve())] = sha256(args.result)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Recorded {evidence['status']} evidence; manifest was not promoted or rewritten")
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
