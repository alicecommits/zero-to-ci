#!/usr/bin/env python3
"""
scripts/preflight.py

Skeleton — frontend/eslint checks only. Backend, CI, dependabot,
Playwright checks land as those flags get extracted.
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def check(desc: str, *cmd: str) -> bool:
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        ok = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        ok = False
    print(f"  [{'ok' if ok else 'FAIL'}] {desc}")
    return ok


def check_path(desc: str, path: Path) -> bool:
    ok = path.exists()
    print(f"  [{'ok' if ok else 'FAIL'}] {desc}")
    return ok


def check_node_resolve(desc: str, module_name: str) -> bool:
    return check(desc, "node", "-e", f"require.resolve('{module_name}')")


def main():
    print("==> Frontend checks")
    results = [
        check_path("eslint.config.js present", Path("eslint.config.js")),
        check("eslint installed", "npx", "--no-install", "eslint", "--version"),
        check_node_resolve("typescript-eslint installed", "typescript-eslint"),
        check_node_resolve("eslint-plugin-react-hooks installed", "eslint-plugin-react-hooks"),
        check(
            "lint script wired in package.json", "node", "-e",
            "process.exit(require('./package.json').scripts.lint ? 0 : 1)",
        ),
        check(
            "lint-staged config present", "node", "-e",
            "process.exit(require('./package.json')['lint-staged'] ? 0 : 1)",
        ),
        check_node_resolve("lint-staged package installed", "lint-staged"),
        check_path(".husky/pre-commit exists", Path(".husky/pre-commit")),
        check_path("merge_package_json.py present", SCRIPTS_DIR / "cross-cutting" / "merge_package_json.py"),
    ]

    if not all(results):
        print("One or more checks failed.", file=sys.stderr)
        sys.exit(1)

    print("All frontend checks passed.")


if __name__ == "__main__":
    main()
