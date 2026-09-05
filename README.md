# zero-to-ci

Scaffolds new projects, or augments existing ones, with CI/CD best practices and an agentic AI workflow — quality gates, linting, and agent-assisted implementation, wired in from commit one.

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

The build process of this repo starts from an existing repo of mine, money-disk. money-disk is m real-world testbed, I implement
manually there → extract here → verify by re-running against money-disk that there is no gap.

I progress on this project per a documented spiral roadmap. I start here focusing on the core practices for a starter project, for a few tech stacks I have experience with, and then enrich with practices/stacks in time.

## Layout

```
scripts/          entry points, invoked directly
  spin-up.sh        dispatches on flags, scaffolds a new/augmented project
  preflight.sh      asserts environment + config are sane

skills/           templates + SKILL.md files, grouped by concern
  frontend/         per-frontend-stack setup (linting, CI wiring)
  backend/          per-backend-stack setup       [not yet extracted]
  devops/           CI/CD, agents, review, infra
  cross-cutting/    stuff spanning frontend+backend  [not yet extracted]
  infra/            Terraform/Ansible                [mid-term goal]
```

## Skill vs script — the rule this repo follows

```
deterministic answer exists          → script or template, never a skill
one correct answer per flag value    → script case branch
copying a file with placeholders     → template, script fills it
judgment required, context-dependent → SKILL.md
```

Most flags should produce zero skills. Before writing a SKILL.md,
I check whether it's actually just an unwritten script — that discipline is part of what makes this repo worth pointing someone to.

## Current status

- **Quality Foundation stage — in progress.**
  - Frontend ESLint (flat config, typescript-eslint, react-hooks):
    extracted from money-disk, first manual pass fixes applied.
    `skills/frontend/react-vite-ts/` covers this.
  - Backend (Ruff/Pyright), CI workflow, dependabot, Playwright:
    not yet extracted.
- Agent-driven implementation + review layers: not started — see
  `skills/devops/agent-lint-handling/SKILL.md` for an early sketch
  of the lint-handling policy those stages will need.
