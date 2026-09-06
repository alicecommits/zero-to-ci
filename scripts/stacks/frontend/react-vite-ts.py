#!/usr/bin/env python3
"""
scripts/stacks/frontend/react-vite-ts.py

Atomic stack logic for --frontend react-vite-ts. Called by scripts/spin_up.py —
not meant to be invoked standalone (assumes cwd is the target repo).
"""
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent  # scripts/


def run(skills_dir: Path) -> None:
    tpl = skills_dir / "frontend" / "react-vite-ts"

    print("==> FRONTEND=react-vite-ts")

    print("  - copying eslint.config.js")
    shutil.copy(tpl / "eslint.config.js", "./eslint.config.js")

    print("  - running package.json diff (dry run — review before applying)")
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "cross-cutting" / "merge_package_json.py"),
            "--target", "./package.json",
            "--template", str(tpl / "package.json.tooling.snippet.json"),
        ],
        check=True,
    )

    print()
    print("    Review the gap report above. To apply:")
    print("      1. run the printed install command yourself (package-manager")
    print("         mutations are never run automatically by this script)")
    print("      2. re-run with --apply to merge non-conflicting scripts/")
    print("         lint-staged keys into package.json")
    print("      python3 scripts/cross-cutting/merge_package_json.py --target ./package.json \\")
    print(f"        --template {tpl}/package.json.tooling.snippet.json --apply")

    print("  - reminder: append lint-staged call into .husky/pre-commit")
    print("    (money-disk already has husky wired for tsc — ADD, don't replace)")
    print(f"    template: {tpl}/husky-pre-commit.snippet.sh")
