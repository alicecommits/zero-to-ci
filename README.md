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
    frontend/react-vite-ts.py   real logic for --frontend react-vite-ts
  cross-cutting/    logic shared across stacks, not owned by any one of them
    merge_package_json.py        deterministic package.json diff/merge
    test_merge_package_json.py   sibling unit tests, same dir
  preflight.py      asserts environment + config are sane

skills/           templates + SKILL.md files, grouped by concern
  frontend/         per-frontend-stack setup (linting, CI wiring)
  backend/          per-backend-stack setup       [not yet extracted]
  devops/           CI/CD, agents, review, infra
  cross-cutting/    stuff spanning frontend+backend  [not yet extracted]
  infra/            Terraform/Ansible                [Wave 8+]
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
  - `scripts/cross-cutting/merge_package_json.py`: deterministic augment-mode
    package.json diff — dependencies/devDependencies diffed by
    presence only (never overwrites a pinned version), scripts/
    lint-staged diffed by key with explicit CONFLICT flagging.
    Live-tested against the real money-disk-ui package.json.
  - `skills/frontend/react-vite-ts/package.json.tooling.snippet.json`
    is the reference this diffs against.
  - Backend (Ruff/Pyright), CI workflow, dependabot, Playwright:
    not yet extracted.
- Agent-driven implementation + review layers: not started — see
  `skills/devops/agent-lint-handling/SKILL.md` for an early sketch
  of the lint-handling policy those stages will need.
