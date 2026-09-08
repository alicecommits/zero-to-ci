# frontend/react-vite-ts

Not a SKILL.md — this stage of the roadmap is explicitly fully
deterministic. This file is reference notes for the flag, read by
you (or an agent) when editing this stack's checklist rules, not
judgment content.

## What FRONTEND=react-vite-ts unpacks

```
spin_up.py --frontend react-vite-ts [--frontend-pm npm|yarn|pnpm]
  → scripts/stacks/frontend/react-vite-ts.py (thin dispatch pointer)
      → Step 1 (only if ./package.json doesn't exist yet — this ONE
        file-existence check is the entire former MODE=new/augment
        distinction, collapsed 2026-09-07, see
        major-evolutions/3_MODE-NEW-SIMPLIFICATION-HANDOFF.md):
        npx create-vite@latest . --template react-ts
        → then scripts/stacks/frontend/react-vite-ts/package_manager_setup.py
          --pm <frontend_pm> --repo-dir . (2026-09-08 — see
          major-evolutions/6_PACKAGE-MANAGER-CHOICE-HANDOFF.md. npm:
          unconditional `npm install`, unchanged default. yarn/pnpm:
          corepack enable + prepare --activate as one atomic gate, falls
          back to npm install loudly on any failure)
      → Step 2, always, new project or old:
        scripts/cross-cutting/checklist_interpreter.py
          --target ./package.json
          --rules  skills/frontend/react-vite-ts/checklist-rules-react-vite-ts.yaml
  → prints a colored PLAN only — nothing is written to disk by Step 2.
    See major-evolutions/1_CHECKLIST_INTERPRETER_HANDOFF.md
    for the full design history and why "plan only, no --apply" is a
    deliberate current limitation, not an oversight.
```

## Full design history lives elsewhere — don't duplicate it here

`major-evolutions/1_CHECKLIST_INTERPRETER_HANDOFF.md` is the
canonical record: why the two earlier iterations (flat package.json
diff; layered YAML rule-chain) were retired, the concern-cluster
schema, the step `type`s, the linter-detection/oxlint fork, and the
still-conceptual "execution / gating design" for turning a plan into
actual writes. It's part of `major-evolutions/`, this repo's 6 ordered
handoff notes (`0_FROM-PKG-DIFF-TO-CHECKLIST-RULES-PARADIGM.md` through
`5_PRECOMMIT-HANDOFF.md`); the 4 companions this stack's own wiring
draws on most directly are `2_TSCONFIG-HANDOFF.md` (the tsconfig
clusters — three-way risk split: structural fields never remediate,
hygiene flags additive/flag-gated, file shape diagnostic/never
migrate), `3_MODE-NEW-SIMPLIFICATION-HANDOFF.md` (why MODE=new
collapsed into "bootstrap if missing, then the same checklist pass" —
see this file's own top section for what that means concretely for
react-vite-ts), `4_GITIGNORE-HANDOFF.md` (the `ensure_block_in_gitignore`
step type and its Tier 1/2/3 classification of what gets a cluster,
built), and `5_PRECOMMIT-HANDOFF.md` (`ensure_line_in_precommit`'s
cross-cluster write-ordering problem — built, 2026-09-08, retiring the
2 former `*-hook-wiring-into-pre-commit` clusters, see below). Read all
of `major-evolutions/` for rationale — this file only tracks what's
specific to _this stack's_ wiring in _this repo's_ tree.

## Files this stack owns

```
skills/frontend/react-vite-ts/
  checklist-rules-react-vite-ts.yaml        the actual cluster definitions, in
                               priority order: vite-baseline-gitignore (fills
                               the one gap create-vite's own scaffold leaves
                               in .gitignore, confirmed against real scaffold
                               output), typescript-check, tsconfig-file-shape-
                               report, tsconfig-environment-report, linter-
                               detection, linter-baseline-remediation, husky-
                               setup, lint-staged-hooks, vitest-test-script,
                               tsconfig-hygiene-remediation (deliberately
                               last — see 2_TSCONFIG-HANDOFF.md). 2026-09-08:
                               the former lint-staged-hook-wiring-into-pre-
                               commit and typecheck-hook-wiring-into-pre-
                               commit clusters are RETIRED — don't resurrect.
                               Their job is now done by ensure_line_in_precommit
                               steps folded directly into lint-staged-hooks
                               (order: 10) and typescript-check (order: 20),
                               reconciled centrally by
                               reconcile_precommit_lines() after every rule
                               has evaluated — see 5_PRECOMMIT-HANDOFF.md.
                               Four clusters (typescript-check, linter-
                               baseline-remediation, husky-setup, vitest-
                               test-script) also each carry one
                               ensure_block_in_gitignore step — see
                               4_GITIGNORE-HANDOFF.md
  package-versions.yaml       single source of truth for every version pin
                               the rules file references via
                               "<package.version>" placeholders — resolved
                               by resolve_placeholders() right after the
                               rules file is parsed, plain YAML has no
                               templating of its own. Scoped narrowly:
                               only packages THIS repo's clusters install
                               (typescript, eslint+its plugins, husky,
                               lint-staged, tsc-files, vitest) — never
                               package.json's own scaffolder-provided
                               baseline, per 3_MODE-NEW-SIMPLIFICATION-HANDOFF.md's whole premise.
  templates/
    tsconfig.json.template      human reference only as of 2026-09-07 — no
                               longer wired into any create_file proposal
                               (typescript-check's old step for it was
                               removed; see that cluster's own concern text
                               for why). Still what tsconfig-hygiene-
                               remediation's `single`-shape branch checks
                               against.
    vitest.config.ts.template   proposed by vitest-test-script's create_file step
    eslint.config.js.template   proposed by linter-baseline-remediation's create_files
                               sub-block. A separate skills/frontend/eslint-baseline/
                               location was tried and reverted — too much indirection
                               for the one stack currently using it.
    husky-pre-commit-base.template.sh  proposed by husky-setup's create_file step —
                               an empty base .husky/pre-commit, for when the file
                               doesn't exist at all yet. Distinct from the file
                               below (base file vs. reference content).
    husky-pre-commit.template.sh  2026-09-08: human reference only, no longer
                               wired into any proposal. Used to be referenced by
                               the 2 now-retired *-hook-wiring-into-pre-commit
                               clusters' file_content_present steps; both lines
                               it shows (npx lint-staged, then yarn typecheck)
                               are now generated INLINE by ensure_line_in_precommit
                               from lint-staged-hooks' and typescript-check's own
                               command/script fields — no template file needed for
                               that, same reason ensure_block_in_gitignore's blocks
                               don't need one either. Still shows the correct final
                               order and the "may already run tsc" append-don't-
                               replace caveat, useful context even though nothing
                               reads it automatically anymore.
    .gitignore.template          human reference only — a full generic Node
                               .gitignore, not wired into any proposal. No
                               cluster reads this file; each owning cluster's
                               ensure_block_in_gitignore step carries its own
                               block inline instead (see 4_GITIGNORE-HANDOFF.md).
                               Useful as the source for entries not yet owned
                               by any cluster — Tier 3 in that handoff
                               (.env/.env.*, .claude//CLAUDE.md) are both
                               present here but still deliberately unbuilt.
```

## Executable logic this stack owns, outside skills/ (scripts/ side)

```
scripts/stacks/frontend/
  react-vite-ts.py             thin dispatch pointer (see top of this file)
  react-vite-ts/
    package_manager_setup.py   2026-09-08 — handles the corepack-vs-npm
                               decision for --frontend-pm (npm/yarn/pnpm)
                               at bootstrap time. Invoked by
                               react-vite-ts.py via subprocess, same
                               pattern as its checklist_interpreter.py
                               call. See
                               major-evolutions/6_PACKAGE-MANAGER-CHOICE-
                               HANDOFF.md for the full corepack
                               enable+prepare atomic-gate design and the
                               npm-fallback behavior.
                               NOT YET EXTRACTED, same status as several
                               skills/ rows in CONFIG_OWNERSHIP_MATRIX.md
                               — nothing inside it is react-vite-ts-
                               specific (takes a bare repo_dir + pm
                               string), it's nested here only because
                               this is still the only Node-based stack.
                               The day a second one lands (nodejs-nestjs
                               backend, most likely), promote this file
                               to scripts/cross-cutting/
                               package_manager_setup.py as a straight
                               file move — don't do it preemptively.
```

`package.json.tooling.snippet.json` — REMOVED 2026-09-07, per
3_MODE-NEW-SIMPLIFICATION-HANDOFF.md point 3: a hand-maintained "full
template" for a from-scratch project can only go stale (the same
oxlint switch that would have required manually updating it required
nothing here, since `create-vite`'s own scaffold output updates
itself). The tooling-snippet half doesn't need a separate file either
— the `dependencies`/`devDependencies`/`scripts` each cluster's
`on_missing`/`on_all_absent` block specifies already ARE that data,
inline, spread across `checklist-rules-react-vite-ts.yaml`. No
separate snippet file needed beyond what the clusters already encode.

## Known current gap, not covered by any cluster yet

If a project already has `eslint` installed but its `eslint.config.js`
was deleted or never committed, no cluster restores it:
`linter-detection` is diagnostic-only, and `linter-baseline-remediation`
only fires on `both_absent` (neither eslint nor oxlint present) — a
present-eslint-but-missing-config case falls through the gap between
them. Not addressed in the original handoff either; flagged here so
it isn't silently lost.

## Neither opt-in flag is wired through `spin_up.py`

Same "manual step, not automatic" spirit the old `--apply` flag had —
`spin_up.py`'s dispatch (`module.run(skills_dir)`) doesn't forward
CLI flags to stack modules. Two flags exist now, deliberately separate
(see `tsconfig-hygiene-remediation`'s concern text for why
`augment_legacy_tsconfig` isn't just reused as `augment_legacy_linting`).
To exercise either, invoke the interpreter directly:

```
python3 scripts/cross-cutting/checklist_interpreter.py \
  --target ./package.json \
  --rules skills/frontend/react-vite-ts/checklist-rules-react-vite-ts.yaml \
  --repo-dir . --flag augment_legacy_linting --flag augment_legacy_tsconfig
```

(`--flag` is repeatable — pass one, the other, both, or neither.)
