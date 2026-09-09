#!/usr/bin/env python3
"""Promote a populated manifest only after evidence validation; never synthesize QA."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from score_providers import load_scorecard
from validate_manifest import validate_manifest


def finalize(manifest: dict, base_dir: Path) -> tuple[dict | None, list[str], list[str]]:
    candidate = deepcopy(manifest)
    candidate["delivery_status"] = "ready"
    def promote(items):
        for figure in items:
            if figure.get("status") == "formal" and figure.get("pipeline_state") != "blocked":
                figure["pipeline_state"] = "verified"
            promote(figure.get("panels", []))
    promote(candidate.get("figures", []))
    errors, warnings = validate_manifest(candidate, load_scorecard(), strict=True, base_dir=base_dir)
    return (None if errors else candidate), errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.manifest.read_text(encoding="utf-8"))
    candidate, errors, warnings = finalize(source, args.manifest.parent)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print("BLOCKED: no output written; source manifest and existing assets preserved")
        return 1
    if args.out.resolve().parent != args.manifest.resolve().parent:
        parser.error("output must share the manifest directory so relative evidence paths remain valid")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(candidate, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(f"Verified: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
