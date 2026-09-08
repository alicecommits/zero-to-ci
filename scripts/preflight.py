#!/usr/bin/env python3
"""
scripts/preflight.py

Skeleton — checks the checklist-cluster engine itself is wired up
(interpreter present, react-vite-ts's rules present, pyyaml importable).
Does NOT assert specific outcomes like "eslint.config.js exists" —
under the checklist-cluster engine those are conditional/opt-in plan
proposals, not guaranteed side effects of running the tooling, so
there's nothing fixed to assert about the target repo's own files here.
Backend, CI, dependabot, Playwright checks land as those flags get extracted.
"""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def check_path(desc: str, path: Path) -> bool:
    ok = path.exists()
    print(f"  [{'ok' if ok else 'FAIL'}] {desc}")
    return ok


def check_pyyaml_importable() -> bool:
    try:
        import yaml  # noqa: F401
        ok = True
    except ImportError:
        ok = False
    print(f"  [{'ok' if ok else 'FAIL'}] pyyaml importable (pip install pyyaml, see requirements.txt)")
    return ok


def main():
    print("==> Checklist engine checks")
    results = [
        check_path(
            "checklist_interpreter.py present",
            SCRIPTS_DIR / "cross-cutting" / "checklist_interpreter.py",
        ),
        check_path(
            "react-vite-ts checklist-rules-react-vite-ts.yaml present",
            SCRIPTS_DIR.parent / "skills" / "frontend" / "react-vite-ts" / "checklist-rules-react-vite-ts.yaml",
        ),
        check_path(
            "react-vite-ts package_manager_setup.py present",
            SCRIPTS_DIR / "stacks" / "frontend" / "react-vite-ts" / "package_manager_setup.py",
        ),
        check_pyyaml_importable(),
    ]

    if not all(results):
        print("One or more checks failed.", file=sys.stderr)
        sys.exit(1)

    print("All checklist engine checks passed.")


if __name__ == "__main__":
    main()
