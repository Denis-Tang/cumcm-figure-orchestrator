#!/usr/bin/env python3
"""Route each planned CUMCM figure to an eligible provider and fallbacks."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from score_providers import DEFAULT_SCORECARD, load_scorecard, rank_providers


def select_skill(provider_id: str, scenario: str) -> str:
    if provider_id == "engineering-figure-agent":
        return "engineering-figure-agent"
    if provider_id == "openai-imagegen":
        return "imagegen"
    if scenario in {"data_chart", "network", "map", "composite"}:
        return "data-analytics:visualize-data"
    return "cumcm-figure-orchestrator"


def route_figure(figure: dict[str, Any], scorecard: dict[str, Any], environment: list[dict] | None = None) -> dict[str, Any]:
    scenario = figure.get("task_type")
    constraints = figure.get("constraints", {})
    requirements = {
        "exact_numeric": scenario in {"data_chart", "map"} or bool(constraints.get("exact_numeric")),
        "exact_text": bool(constraints.get("exact_text", True)),
        "vector_required": bool(constraints.get("vector_required", figure.get("status") == "formal")),
        "reproducible_required": bool(constraints.get("reproducible_required", figure.get("status") == "formal")),
        "formal_final": figure.get("status") == "formal",
    }
    prefer_ai = bool(figure.get("allow_ai_candidate", False)) and figure.get("status") != "formal"
    eligible, rejected = rank_providers(scorecard, scenario, requirements, prefer_ai)
    if environment is not None:
        ready = {row["id"] for row in environment if row.get("status") == "available"}
        rejected.extend({"id": row["id"], "failures": ["runtime dependency unavailable or unconfirmed"]}
                        for row in eligible if row["id"] not in ready)
        eligible = [row for row in eligible if row["id"] in ready]
    if not eligible:
        rejected_summary = "; ".join(
            f"{item['id']}: {', '.join(item['failures'])}" for item in rejected
        )
        raise ValueError(f"{figure.get('figure_id', '<unknown>')}: no eligible provider ({rejected_summary})")

    primary = eligible[0]
    reasons = [
        f"Passed hard gates: {', '.join(key for key, value in requirements.items() if value) or 'none'}.",
        f"Highest weighted score for {scenario}: {primary['score']:.3f}/10.",
        f"Evidence confidence: {primary['evidence_confidence']}.",
    ]
    if primary["availability"] == "probe" and environment is None:
        reasons.append("Runtime dependency availability must be confirmed by check_environment.py.")
    routed = deepcopy(figure)
    routed["route"] = {
        "skill": select_skill(primary["id"], scenario),
        "provider": primary["id"],
        "renderer": primary["id"],
        "score": primary["score"],
        "evidence_confidence": primary["evidence_confidence"],
        "availability": primary["availability"],
        "alternatives": [
            {"provider": item["id"], "score": item["score"], "availability": item["availability"]}
            for item in eligible[1:4]
        ],
        "reasons": reasons,
        "environment_checked": environment is not None,
    }
    routed["pipeline_state"] = "planned"
    routed.pop("blocked_reason", None)
    return routed


def route_manifest(manifest: dict[str, Any], scorecard: dict[str, Any], environment: list[dict] | None = None) -> dict[str, Any]:
    routed = deepcopy(manifest)
    def route_one(figure):
        if figure.get("status") == "excluded":
            return deepcopy(figure)
        try:
            result = route_figure(figure, scorecard, environment)
        except ValueError as exc:
            result = deepcopy(figure)
            result.pop("route", None)
            result.update(pipeline_state="blocked", blocked_reason=str(exc))
        if figure.get("panels"):
            result["panels"] = [route_one(panel) for panel in figure["panels"]]
        return result
    routed["figures"] = [route_one(figure) for figure in manifest.get("figures", [])]
    routed["delivery_status"] = "planned"
    routed["routing_meta"] = {
        "scorecard_version": scorecard.get("version"),
        "policy": "hard-gates-before-weighted-score",
    }
    return routed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD)
    parser.add_argument("--environment", type=Path, help="JSON array from check_environment.py --json")
    parser.add_argument("--planning-only", action="store_true", help="Skip dependency filtering; never implies executability")
    args = parser.parse_args()

    with args.manifest.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    scorecard = load_scorecard(args.scorecard)
    environment = None
    if not args.planning_only:
        if args.environment:
            environment = json.loads(args.environment.read_text(encoding="utf-8"))
        else:
            from check_environment import provider_status
            environment = [provider_status(provider) for provider in scorecard["providers"]]
    routed = route_manifest(manifest, scorecard, environment)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(routed, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Routed {len(routed.get('figures', []))} figures -> {args.out}")
    for figure in routed.get("figures", []):
        if "route" in figure:
            print(f"  {figure['figure_id']}: {figure['route']['provider']} ({figure['route']['score']:.3f})")
        elif figure.get("pipeline_state") == "blocked":
            print(f"  BLOCKED {figure['figure_id']}: {figure['blocked_reason']}")
    def blocked(items):
        return any(f.get("pipeline_state") == "blocked" or blocked(f.get("panels", [])) for f in items)
    return 1 if blocked(routed["figures"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
