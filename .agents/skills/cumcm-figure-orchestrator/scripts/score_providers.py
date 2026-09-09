#!/usr/bin/env python3
"""Rank CUMCM figure providers after applying hard capability gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SCORECARD = SKILL_DIR / "assets" / "provider-scorecard.json"

WEIGHTS = {
    "scenario_fit": 0.30,
    "semantic_numeric_accuracy": 0.16,
    "text_accuracy": 0.12,
    "collision_avoidance": 0.12,
    "vector_export": 0.08,
    "reproducibility": 0.08,
    "cumcm_auditability": 0.08,
    "visual_aesthetics": 0.04,
    "speed": 0.02,
}

PREFERRED_ORDER = {
    "data_chart": ["matplotlib-seaborn", "ggplot2-ggrepel", "plotly-kaleido"],
    "flowchart": ["d2-elk", "mermaid-elk", "networkx-graphviz"],
    "network": ["networkx-graphviz", "d2-elk", "mermaid-elk"],
    "map": ["geopandas-cartopy", "matplotlib-seaborn", "plotly-kaleido"],
    "conceptual_schematic": ["d2-elk", "engineering-figure-agent", "openai-imagegen"],
    "composite": ["matplotlib-seaborn", "engineering-figure-agent", "d2-elk"],
}


def load_scorecard(path: Path = DEFAULT_SCORECARD) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def eligibility_failures(provider: dict[str, Any], requirements: dict[str, bool]) -> list[str]:
    capabilities = provider.get("capabilities", {})
    failures: list[str] = []
    mapping = {
        "exact_numeric": "exact_numeric",
        "exact_text": "exact_text",
        "vector_required": "vector",
        "reproducible_required": "reproducible",
        "formal_final": "formal_final",
    }
    for request_key, capability_key in mapping.items():
        if requirements.get(request_key, False) and not capabilities.get(capability_key, False):
            failures.append(f"missing capability: {capability_key}")
    if requirements.get("formal_final", False) and provider.get("candidate_only", False):
        failures.append("candidate-only provider is not eligible for a formal final")
    return failures


def score_provider(provider: dict[str, Any], scenario: str, prefer_ai_candidate: bool = False) -> float:
    values = provider.get("scores", {})
    score = WEIGHTS["scenario_fit"] * provider.get("scenario_fit", {}).get(scenario, 0.0)
    for dimension, weight in WEIGHTS.items():
        if dimension != "scenario_fit":
            score += weight * values.get(dimension, 0.0)

    preferred = PREFERRED_ORDER.get(scenario, [])
    if provider["id"] in preferred:
        position = preferred.index(provider["id"])
        score += 0.15 * (len(preferred) - position) / len(preferred)
    if prefer_ai_candidate and provider.get("candidate_only") and provider.get("capabilities", {}).get("ai_generated"):
        score += 1.50
    return round(score, 3)


def rank_providers(
    scorecard: dict[str, Any],
    scenario: str,
    requirements: dict[str, bool] | None = None,
    prefer_ai_candidate: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requirements = requirements or {}
    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for provider in scorecard["providers"]:
        failures = eligibility_failures(provider, requirements)
        if failures:
            rejected.append({"id": provider["id"], "failures": failures})
            continue
        eligible.append(
            {
                "id": provider["id"],
                "display_name": provider["display_name"],
                "layer": provider["layer"],
                "score": score_provider(provider, scenario, prefer_ai_candidate),
                "evidence_confidence": provider["evidence_confidence"],
                "availability": provider["availability"],
                "candidate_only": bool(provider.get("candidate_only", False)),
                "notes": provider.get("notes", ""),
            }
        )
    eligible.sort(key=lambda item: (-item["score"], item["id"]))
    return eligible, rejected


def _print_table(rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        print("No eligible provider.")
        return
    print(f"{'rank':>4}  {'score':>6}  {'confidence':>10}  {'availability':>18}  provider")
    for index, row in enumerate(rows, 1):
        print(
            f"{index:>4}  {row['score']:>6.3f}  {row['evidence_confidence']:>10}  "
            f"{row['availability']:>18}  {row['id']}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, choices=sorted(PREFERRED_ORDER))
    parser.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD)
    parser.add_argument("--exact-numeric", action="store_true")
    parser.add_argument("--exact-text", action="store_true")
    parser.add_argument("--vector-required", action="store_true")
    parser.add_argument("--reproducible-required", action="store_true")
    parser.add_argument("--formal", action="store_true", help="Require a formal-final provider.")
    parser.add_argument("--prefer-ai-candidate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    requirements = {
        "exact_numeric": args.exact_numeric,
        "exact_text": args.exact_text,
        "vector_required": args.vector_required,
        "reproducible_required": args.reproducible_required,
        "formal_final": args.formal,
    }
    eligible, rejected = rank_providers(
        load_scorecard(args.scorecard), args.scenario, requirements, args.prefer_ai_candidate
    )
    if args.as_json:
        print(json.dumps({"eligible": eligible, "rejected": rejected}, ensure_ascii=False, indent=2))
    else:
        _print_table(eligible)
    return 0 if eligible else 2


if __name__ == "__main__":
    raise SystemExit(main())
