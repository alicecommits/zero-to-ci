#!/usr/bin/env python3
"""
scripts/spin_up.py

Main orchestrator. Dispatch only — no stack-specific logic lives here.
Each stack's real logic is an atomic module at
  scripts/stacks/<category>/<stack>.py
addressed by convention from the flag value, so adding a new stack means
dropping one new file, not growing an if/elif chain in this file.

Usage so far:
  python3 scripts/spin_up.py --frontend react-vite-ts
"""
import argparse
import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILLS_DIR = SCRIPTS_DIR.parent / "skills"


def load_stack_module(category: str, stack: str):
    stack_file = SCRIPTS_DIR / "stacks" / category / f"{stack}.py"
    if not stack_file.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"stacks.{category}.{stack}", stack_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", default="")
    ap.add_argument("--agents", default="")  # stub — later stage
    args = ap.parse_args()

    if args.frontend:
        module = load_stack_module("frontend", args.frontend)
        if module is None:
            print(
                f"FRONTEND={args.frontend} not implemented yet "
                f"(no scripts/stacks/frontend/{args.frontend}.py)",
                file=sys.stderr,
            )
            sys.exit(1)
        module.run(SKILLS_DIR)

    if args.agents:
        print(f"==> AGENTS={args.agents} requested but not implemented yet.", file=sys.stderr)
        print("    This flag will eventually:", file=sys.stderr)
        print("      - generate implement.yml from template", file=sys.stderr)
        print("      - write LINT_FIX_MODE: supervised into its prompt section", file=sys.stderr)
        print("        (see skills/devops/agent-lint-handling/SKILL.md)", file=sys.stderr)
        print("    No implement.yml exists yet to write into — come back later.", file=sys.stderr)
        sys.exit(1)

    print(f"Done. FRONTEND={args.frontend} checklist plan printed above — nothing was written (plan only).")


if __name__ == "__main__":
    main()
