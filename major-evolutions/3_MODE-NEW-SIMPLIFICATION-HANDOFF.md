# zero-to-ci — collapsing MODE=new for Node/TS stacks

Companion to `0_FROM-PKG-DIFF-TO-CHECKLIST-RULES-PARADIGM.md`, `1_CHECKLIST_INTERPRETER_HANDOFF.md` and `2_TSCONFIG-HANDOFF.md`.
This note covers a simplification, not a new feature: for any Node/TS stack that has an
official, actively-maintained interactive scaffolder (currently:
`create-vite` for `react-vite-ts`), `MODE=new` stops being a distinct
code path. It becomes "run the bootstrap scaffolder, then run the exact
same augment-mode checklist pass" — not a parallel, separately-maintained
flow.

## The insight this is based on

Every remediation ambiguity in the checklist design so far — flag-gating
`linter-baseline-remediation`, flag-gating `tsconfig-hygiene-remediation`,
the `absent`/`unrecognized` outcomes in `tsconfig-file-shape-report` — exists
**specifically because augment-mode can't see a project's history.** A
`both_absent` linter result on an unknown, possibly-years-old project is
genuinely ambiguous. A `both_absent` result checked immediately after
`create-vite`'s own interactive prompt just answered that exact question
is not ambiguous at all — the scaffolder's own answer _is_ the ground
truth, with no history to be uncertain about. Same logic for tsconfig:
`create-vite` always writes a valid tsconfig shape, so `absent` and
`unrecognized` structurally cannot occur immediately after a fresh
scaffold.

Consequence: none of the flag-gated remediation clusters need a
"MODE=new" variant or exception. They simply never fire on this path,
because their firing condition (an unexplainable gap) can't be true right
after a scaffolder that just resolved that exact question interactively.
The checklist interpreter does not need to know which mode it's in.

## What to actually delete or simplify

**1. `SPIN_UP.md.template` — drop the `MODE: new | augment` field entirely**
for stacks with a maintained scaffolder. There is one pass, not two modes
to record.

**2. `spin_up.py` — remove the `MODE` variable and `--mode` flag.**
Currently a stub (`MODE="new"` default, `--mode) MODE="$2"...`) that
nothing meaningfully branches on. Delete rather than leave dormant.

**3. Do NOT build `package.json.full.template`.**
This was proposed in an earlier design pass (a hand-maintained,
pinned-version full manifest for brand-new projects, as a counterpart to
the augment-mode tooling snippet) but never committed to disk. Cancel it
outright — `create-vite`'s own scaffold output is the correct "full new
project" state, and it can't go stale the way a hand-copied template
would (see the oxlint switch: a hand-maintained full-template would have
required you to notice and manually update it; `create-vite` updated
itself). Only the tooling-snippet half of that split — `dependencies`/
`devDependencies`/`scripts` the checklist clusters install/add — remains
needed, and it already exists in the current design as the union of what
each cluster's `on_missing`/`on_all_absent` blocks specify. No separate
snippet file needed beyond what the clusters already encode inline.

**4. Retire `spin_up.py`'s existing `react-vite-ts` branch, which predates
`checklist_interpreter.py` and duplicates its job by an older, less safe
mechanism:**

```bash
cp "$TPL/eslint.config.js" ./eslint.config.js
xargs npm install -D < "$TPL/install.txt"
echo "! manual step: merge $TPL/lint-staged.snippet.json into package.json"
```

This has no conflict detection, no flag-gating, and installs from an
unpinned `install.txt` — every problem the checklist-cluster design was
built to fix. Replace the whole branch with a call into the interpreter
(see next section). Do not leave both mechanisms present in the repo —
having two ways to provision the same files is exactly the kind of
inconsistency the concern-cluster design exists to prevent.

## What `spin_up.py --frontend react-vite-ts` should do instead

Two steps, run in order, no mode flag needed:

```python
# scripts/stacks/frontend/react-vite-ts.py (excerpt) — inside run(), the
# stack-specific atomic module scripts/spin_up.py dispatches into. NOT
# scripts/spin_up.py itself, deliberately: spin_up.py is dispatch-only —
# this repo's own standing rule is that adding a new stack must never
# require editing it. "npx create-vite@latest --template react-ts" is
# react-vite-ts-specific (a future vue-vite-ts stack needs a different
# template flag; a Python backend stack wouldn't call create-vite at
# all), so hardcoding it into the shared dispatcher would reintroduce
# exactly the per-stack branching that rule exists to prevent.
#
# Step 1: bootstrap, only if package.json doesn't already exist. This is
# the ONLY place "new vs augment" still matters, and it's now just a
# file-existence check, not a persistent mode carried through the rest
# of the run.
#
# Two-part bootstrap, confirmed by live testing (create-vite 9.2.0) —
# NOT a single call. --no-interactive scaffolds files only, and does
# NOT run install or start the dev server on its own, interactive or
# not — the CLI's own output after this flag is literally "Now run:
# npm install / npm run dev," never runs them itself. Splitting the
# scaffold from the install is actually convenient here: `npm install`
# is a bounded, well-understood step with no interactivity of its own,
# so there's no ambiguity about whether a hung dev server is masking a
# real failure — unlike the interactive path, which does offer to
# install-and-start in one go if answered "yes."
import subprocess
from pathlib import Path

if not Path("package.json").exists():
    subprocess.run(
        [
            "npx", "--yes", "create-vite@latest", ".",
            "--template", "react-ts",
            "--eslint",          # opt into ESLint over the post-June-2026
                                  # oxlint default — matches this stack's
                                  # convention, doesn't silently pick oxlint
            "--overwrite",       # suppresses the non-empty-target-directory
                                  # prompt that would otherwise hang a
                                  # subprocess with no stdin wired up
            "--no-interactive",  # confirmed: scaffolds only, no install,
                                  # no dev-server start, no other prompts
        ],
        check=True,
    )
    subprocess.run(["npm", "install"], check=True)

# Step 2: same checklist pass, every time, new project or old. Actual
# implementation subprocess-calls checklist_interpreter.py's CLI (same
# invocation the augment-only path already used before this handoff)
# rather than importing run() directly — that keeps the existing colored
# print_report() terminal output (staged/done/conflict, etc.) instead of
# trading it for a raw JSON dump. --json is still available on that CLI
# for programmatic consumption if something ever needs the plan as data.
import sys

subprocess.run(
    [
        sys.executable, "scripts/cross-cutting/checklist_interpreter.py",
        "--target", "./package.json",
        "--rules", "skills/frontend/react-vite-ts/checklist-rules-react-vite-ts.yaml",
        "--repo-dir", ".",
    ],
    check=True,
)
```

**One thing this leaves open, worth testing before relying on it further:**
whether `--eslint`/`--overwrite`/`--no-interactive` behave identically
across the other stack templates you might add later (`vue-ts`, etc.) —
these were confirmed specifically against `react-ts` on create-vite 9.2.0.
Don't assume the flag set generalizes without re-checking against a real
empty target directory for each new template, the same way this one was
verified rather than assumed.

`create-vite`'s interactive prompts (framework/variant/linter) still run
normally in Step 1 when it fires — nothing about that needs automating or
suppressing. Step 2 then reports whatever gap, if any, remains — which
on a same-day fresh scaffold should be close to nothing, since the
checklist clusters' "bare minimum baseline" section already matches
current `create-vite` output by design.

## What does NOT change

- The checklist interpreter itself (`checklist_interpreter.py`) needs no
  new flag, mode parameter, or code path. It has never known about MODE
  and doesn't need to learn.
- All existing clusters (`typescript-check`, `linter-detection`,
  `linter-baseline-remediation`, `husky-setup`, `lint-staged-hooks`,
  `vitest-test-script`, the tsconfig clusters) are unaffected — they run
  identically whether the package.json they're reading is five minutes
  or five years old.
- `requires_flag`-gated clusters remain exactly as designed. They just
  correctly never fire in practice on a same-session fresh scaffold,
  which is a confirmation of the design, not a change to it.

## The one explicit boundary worth restating

This simplification is scoped to **stacks with an official, actively-
maintained interactive scaffolder** — currently only `create-vite` for
`react-vite-ts`. It is NOT a general claim that MODE=new is unnecessary
architecture. A future stack without an equivalent canonical bootstrapper
(the Python backend case, discussed separately) still needs someone —
you — to author and maintain what "minimal skeleton" means, and that
bootstrap becomes a real, versioned artifact you're responsible for, not
a one-line existence check delegating to a subprocess. Don't generalize
"just shell out to the ecosystem's installer" as a universal pattern
without first confirming that ecosystem actually has a `create-vite`-
equivalent to shell out to.
