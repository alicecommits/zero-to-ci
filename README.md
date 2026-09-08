# zero-to-ci

Turn a brand-new (or existing) repo into one with CI/CD best practices
wired in from commit zero — linting, type checking, pre-commit hooks,
branch protection, dependency updates, and (later) agent-driven
implementation with quality gates. Stack-agnostic by design.

## Why this exists

Two purposes, in order:

1. **Speed.** Every new project should start with the same baseline
   of quality tooling without re-deriving it from scratch — copy
   templates, run a script, done.
2. **A visible, referenceable base.** This repo is also the place
   that shows — to me later, and to anyone evaluating my work — what
   "good CI/CD setup" looks like when I build it. The scripts and
   SKILL.md judgment calls in here are meant to be read, not just run.

The build process (money-disk as the real-world testbed, implement
manually → extract here → verify by re-running against money-disk)
is documented in `spiral-roadmap-v2.md` (kept in Notion). That process
is a means to an end — the roadmap is how this repo gets built
correctly, not the point of the repo itself.

## Layout

```
scripts/          entry points, invoked directly
  spin_up.py        dispatch only — routes each flag to its stack script
  stacks/           atomic per-stack logic, one file per <category>/<stack>
    frontend/react-vite-ts.py   thin pointer: calls the checklist engine
                                 with this stack's checklist-rules-react-vite-ts.yaml
  cross-cutting/    logic shared across stacks, not owned by any one of them
    checklist_interpreter.py         concern-cluster engine — reads a
                                      checklist-rules-react-vite-ts.yaml, prints a
                                      colored PLAN (never writes files)
    colors.py                        shared ANSI palette
  preflight.py      asserts environment + config are sane

major-evolutions/ 6 ordered handoff notes, the design-history record this
                  repo is built from — read before touching the engine or
                  any checklist-rules-react-vite-ts.yaml:
                  0_FROM-PKG-DIFF-TO-CHECKLIST-RULES-PARADIGM.md (origin
                  context), 1_CHECKLIST_INTERPRETER_HANDOFF.md (canonical
                  engine design rationale), 2_TSCONFIG-HANDOFF.md,
                  3_MODE-NEW-SIMPLIFICATION-HANDOFF.md,
                  4_GITIGNORE-HANDOFF.md, 5_PRECOMMIT-HANDOFF.md

skills/           templates + SKILL.md files, grouped by concern
  frontend/
    react-vite-ts/    checklist-rules-react-vite-ts.yaml (10 clusters) +
                       package-versions.yaml (single source of truth for
                       every version pin, resolved via <package.version>
                       placeholders) + templates/ (tsconfig.json.template,
                       vitest.config.ts.template, eslint.config.js.template,
                       husky-pre-commit-base.template.sh, plus 2 human-
                       reference-only files no longer wired into any
                       proposal: husky-pre-commit.template.sh and
                       .gitignore.template)
  backend/           per-backend-stack setup       [not yet extracted]
  devops/            CI/CD, agents, review, infra
  cross-cutting/     stuff spanning frontend+backend  [not yet extracted]
  infra/             Terraform/Ansible                [Wave 8+]
```

## Skill vs script — the rule this repo follows

```
deterministic answer exists          → script or template, never a skill
one correct answer per flag value    → script case branch
copying a file with placeholders     → template, script fills it
judgment required, context-dependent → SKILL.md
```

Most flags should produce zero skills. Before writing a SKILL.md,
check whether it's actually just an unwritten script — that
discipline is part of what makes this repo worth pointing someone to.

## Current status

- **Quality Foundation stage — in progress.**
  - Frontend ESLint (flat config, typescript-eslint, react-hooks):
    extracted from money-disk, first manual pass fixes applied.
  - `scripts/cross-cutting/checklist_interpreter.py`: the checklist-cluster
    augment engine (3rd design iteration — 2 earlier ones retired, see
    `major-evolutions/1_CHECKLIST_INTERPRETER_HANDOFF.md`). Reads a stack's `checklist-rules-react-vite-ts.yaml`,
    evaluates concern clusters (grouped by semantic ownership, e.g.
    "everything ESLint provisions" as one unit, not by JSON section),
    prints a colored plan. Never writes a file itself — turning a plan
    into an actual write is a deliberately deferred "execution/gating"
    design, not built yet. Two step types propose more than a single
    key/value diff: `ensure_block_in_gitignore` (per-cluster, content-
    based `.gitignore` block matching — any order/formatting, see
    `major-evolutions/4_GITIGNORE-HANDOFF.md`) and `ensure_line_in_precommit`
    (cross-cluster, two-phase: each owning cluster stages one
    `.husky/pre-commit` line, a single centralized reconciliation pass
    orders and proposes them together — see
    `major-evolutions/5_PRECOMMIT-HANDOFF.md`).
  - `skills/frontend/react-vite-ts/checklist-rules-react-vite-ts.yaml`: this
    stack's 10 clusters — `vite-baseline-gitignore`, package.json-level
    (`typescript-check`, `linter-detection`, `linter-baseline-remediation`
    opt-in, `husky-setup`, `lint-staged-hooks`, `vitest-test-script`), and
    tsconfig.json-level (`tsconfig-file-shape-report` and
    `tsconfig-environment-report`, both permanently diagnostic-only —
    never remediate, under any flag; `tsconfig-hygiene-remediation`, opt-in
    via its own `--flag augment_legacy_tsconfig`, additive-only). See
    `major-evolutions/2_TSCONFIG-HANDOFF.md` for why tsconfig needed a stricter 3-way risk
    split than the linting clusters. Live-tested against the real
    money-disk-ui package.json (clean — zero installs needed), a synthetic
    fresh scaffold, and all 4 tsconfig shape outcomes (single/split/
    unrecognized/absent). `CONFIG_OWNERSHIP_MATRIX.md` tracks, per cluster,
    what each one contributes to `.gitignore` and to the pre-commit hook;
    `skills/frontend/react-vite-ts/TRANSVERSAL-QUALITY-MATRIX.md` is the
    same idea narrowed to this one stack, laid out as a cluster ×
    transversal-gate table.
  - This repo is otherwise stdlib-only by policy; PyYAML is the one
    explicit exception (`requirements.txt`) — see that file for why.
  - Backend (Ruff/Pyright), CI workflow, dependabot, Playwright:
    not yet extracted.
- Agent-driven implementation + review layers: not started — see
  `skills/devops/agent-lint-handling/SKILL.md` for an early sketch
  of the lint-handling policy those stages will need.
