#!/usr/bin/env python3
"""
scripts/stacks/frontend/react-vite-ts.py

Atomic stack logic for --frontend react-vite-ts. Called by scripts/spin_up.py —
not meant to be invoked standalone (assumes cwd is the target repo).

As of the checklist-cluster engine (see
major-evolutions/1_CHECKLIST_INTERPRETER_HANDOFF.md), this stack's
actual logic is entirely data — skills/frontend/react-vite-ts/checklist-rules-react-vite-ts.yaml
— evaluated by the generic scripts/cross-cutting/checklist_interpreter.py.
This file is now just the convention-dispatched pointer from spin_up.py to
that rules file, same "one file per stack" shape as before, thinner content.

As of major-evolutions/3_MODE-NEW-SIMPLIFICATION-HANDOFF.md,
MODE=new is collapsed into this same run rather than a separate code path:
if ./package.json doesn't exist yet, bootstrap via create-vite first (Step 1),
then run the exact same checklist pass either way (Step 2). The checklist
interpreter itself never learns about "mode" — the file-existence check
below is the only place new-vs-augment still exists at all, and it's a
one-line check, not a persistent flag threaded through anything.

Opt-in remediation clusters (e.g. linter-baseline-remediation, gated by
`requires_flag: augment_legacy_linting`) are NOT wired through here — same
"manual step, not automatic" spirit the old --apply flag had. Run
checklist_interpreter.py directly with --flag if you want one of those.
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent  # scripts/
sys.path.insert(0, str(SCRIPTS_DIR / "cross-cutting"))
from colors import BLUE, RESET  # noqa: E402


def run(skills_dir: Path) -> None:
    stack_dir = skills_dir / "frontend" / "react-vite-ts"

    print("==> FRONTEND=react-vite-ts")

    if not Path("package.json").exists():
        print("  - no package.json found — bootstrapping via create-vite (react-ts template)")
        print(f"    {BLUE}INFO:{RESET} this custom bootstrapping will auto-run npm install, NOT npm run dev")
        # Live-confirmed against create-vite 9.2.0, react-ts template ONLY.
        # Two separate subprocess calls, not one: --no-interactive scaffolds
        # files only, it does NOT run install or start the dev server —
        # create-vite's own post-scaffold output literally says "Now run:
        # npm install / npm run dev" rather than running them itself. Do not
        # collapse this back into a single call assuming install happens
        # for free.
        subprocess.run(
            [
                "npx", "--yes",              # skip npx's own "Ok to proceed?" prompt (separate from create-vite's own flags)
                "create-vite@latest", ".",
                "--template", "react-ts",
                "--eslint",                  # opt into ESLint over the post-June-2026 oxlint default
                "--overwrite",                # suppress the non-empty-target-dir prompt — would otherwise hang this subprocess, no stdin wired up
                "--no-interactive",           # confirmed to skip all remaining prompts, scaffold-only
            ],
            check=True,
        )
        subprocess.run(["npm", "install"], check=True)
        # WARNING: this exact flag combination was verified only against
        # the react-ts template on create-vite 9.2.0. A future stack flag
        # adding another create-vite template (vue-ts, etc.) must NOT
        # assume these flags behave identically — re-verify against a real
        # empty target directory the same way this one was confirmed,
        # don't just copy the flags over.

    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "cross-cutting" / "checklist_interpreter.py"),
            "--target", "./package.json",
            "--rules", str(stack_dir / "checklist-rules-react-vite-ts.yaml"),
            "--repo-dir", ".",
        ],
        check=True,
    )
    # No trailing manual reminder needed here anymore — .husky/pre-commit's
    # content gap (append lint-staged's invocation into it) is now a real
    # [staged] plan entry from lint-staged-hook-wiring, not a print()
    # bolted on outside the interpreter.
