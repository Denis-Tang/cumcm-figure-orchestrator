#!/usr/bin/env python3
"""Compare independently recomputed values with values read from plotted artists."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def compare_tables(expected: Path, actual: Path, keys: list[str], columns: list[str],
                   atol: float = 1e-9, rtol: float = 1e-7) -> dict:
    errors: list[str] = []
    if not keys or not columns or set(keys) & set(columns):
        raise ValueError("non-overlapping key and numeric columns are required")
    if not all(math.isfinite(x) and x >= 0 for x in (atol, rtol)):
        raise ValueError("tolerances must be finite and nonnegative")

    def read(path: Path) -> dict:
        rows = {}
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not set(keys + columns).issubset(reader.fieldnames or []):
                raise ValueError(f"{path}: missing key/numeric columns")
            for index, row in enumerate(reader, 2):
                key = tuple(row[k] for k in keys)
                if any(x is None or not x.strip() for x in key) or key in rows:
                    raise ValueError(f"{path}:{index}: empty or duplicate key {key}")
                values = tuple(float(row[c]) for c in columns)
                if not all(math.isfinite(x) for x in values):
                    raise ValueError(f"{path}:{index}: non-finite numeric value")
                rows[key] = values
        if not rows:
            raise ValueError(f"{path}: empty table")
        return rows

    left, right = read(expected), read(actual)
    if left.keys() != right.keys():
        errors.append(f"key mismatch: missing={len(left.keys()-right.keys())}, extra={len(right.keys()-left.keys())}")
    maximum = 0.0
    mismatches = 0
    for key in left.keys() & right.keys():
        for column, e, a in zip(columns, left[key], right[key]):
            maximum = max(maximum, abs(e-a))
            if abs(e-a) > atol + rtol * abs(e):
                mismatches += 1
                if len(errors) < 20:
                    errors.append(f"{key}/{column}: expected={e}, plotted={a}")
    return {"status": "fail" if errors else "pass",
            "method": "Key-aligned independent-reference versus plotted-value comparison",
            "reference_rows": len(left), "plotted_rows": len(right),
            "max_absolute_error": maximum, "mismatches": mismatches,
            "atol": atol, "rtol": rtol, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("--keys", nargs="+", required=True)
    parser.add_argument("--columns", nargs="+", required=True)
    parser.add_argument("--atol", type=float, default=1e-9)
    parser.add_argument("--rtol", type=float, default=1e-7)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare_tables(args.expected, args.actual, args.keys, args.columns, args.atol, args.rtol)
    except (OSError, ValueError, TypeError) as exc:
        result = {"status": "fail", "method": "numeric comparison", "errors": [str(exc)]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(result["status"])
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
