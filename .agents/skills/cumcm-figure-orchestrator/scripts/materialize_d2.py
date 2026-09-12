#!/usr/bin/env python3
"""Materialize a D2 template from the active V02 palette JSON.

D2 has no JSON import facility. Templates therefore use ``{{colors.blue}}`` or
``{{soft_fills.blue}}`` tokens and must be rendered through this adapter rather
than carrying copied hexadecimal values.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def materialize(source: Path, output: Path, palette_path: Path) -> dict[str, str]:
    palette = json.loads(palette_path.read_text(encoding="utf-8"))
    used: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        family, role = match.group(1) or match.group(3), match.group(2)
        if family in {"canvas", "text"}:
            if role:
                raise ValueError(f"palette token {match.group(0)} does not take a role")
            value = palette[family]
            used[match.group(0)] = value
            return value
        try:
            value = palette[family][role]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"unknown palette token {match.group(0)}") from exc
        used[match.group(0)] = value
        return value

    rendered, count = re.subn(r"\{\{(?:(colors|large_area_fills|soft_fills)\.([a-z]+)|(canvas|text))\}\}", replace, source.read_text(encoding="utf-8"))
    unresolved = re.findall(r"\{\{[^}]+\}\}", rendered)
    if unresolved:
        raise ValueError(f"unresolved D2 palette token(s): {', '.join(unresolved)}")
    if not count:
        raise ValueError("D2 template has no palette tokens; refusing a hard-coded color path")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return used


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--palette", required=True, type=Path)
    args = parser.parse_args()
    used = materialize(args.source, args.out, args.palette)
    print(json.dumps({"source": str(args.source), "palette": str(args.palette), "used": used}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
