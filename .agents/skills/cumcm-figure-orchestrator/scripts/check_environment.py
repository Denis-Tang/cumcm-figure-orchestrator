#!/usr/bin/env python3
"""Probe local command and Python-module dependencies for scored providers."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from score_providers import DEFAULT_SCORECARD, load_scorecard

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def find_command(name: str) -> str | None:
    system_path = shutil.which(name)
    if system_path:
        return system_path
    if name.lower() == "msedge":
        for known in (
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        ):
            if known.is_file():
                return str(known)
    for suffix in (".exe", ".cmd", ".bat", ""):
        candidate = PROJECT_ROOT / ".tools" / "bin" / f"{name}{suffix}"
        if candidate.is_file():
            return str(candidate)
    return None


def provider_status(provider: dict[str, Any]) -> dict[str, Any]:
    requirements = provider.get("requirements", {})
    commands = {name: find_command(name) for name in requirements.get("commands", [])}
    modules = {
        name: importlib.util.find_spec(name) is not None
        for name in requirements.get("python_modules", [])
    }
    r_packages: dict[str, bool] = {}
    rscript = commands.get("Rscript") or find_command("Rscript")
    for package in requirements.get("r_packages", []):
        if not rscript:
            r_packages[package] = False
            continue
        try:
            probe = subprocess.run(
                [rscript, "--vanilla", "-e", f"quit(status=ifelse(requireNamespace('{package}', quietly=TRUE),0,1))"],
                capture_output=True, text=True, timeout=20, check=False,
            )
            r_packages[package] = probe.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            r_packages[package] = False
    if provider.get("availability") == "installed_skill":
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        skill_exists = (codex_home / "skills" / provider["id"] / "SKILL.md").is_file()
    else:
        skill_exists = None
    checks = [value is not None for value in commands.values()] + list(modules.values()) + list(r_packages.values())
    if skill_exists is not None:
        checks.append(skill_exists)
    if provider.get("availability") == "session_skill":
        status = "session-dependent"
    elif not checks:
        status = "declared"
    else:
        status = "available" if all(checks) else "missing-dependency"
    return {
        "id": provider["id"],
        "status": status,
        "commands": commands,
        "python_modules": modules,
        "r_packages": r_packages,
        "installed_skill": skill_exists,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    rows = [provider_status(provider) for provider in load_scorecard(args.scorecard)["providers"]]
    if args.as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"{row['id']:<26} {row['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
