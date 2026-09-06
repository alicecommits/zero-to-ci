# frontend/react-vite-ts

Not a SKILL.md — this stage of the roadmap is explicitly fully
deterministic. This file is reference notes for the flag, read by
you (or an agent) when editing `scripts/stacks/frontend/react-vite-ts.py`
(the atomic logic file `scripts/spin_up.py` dispatches to), not
judgment content.

## What FRONTEND=react-vite-ts unpacks

```
spin_up.py --frontend react-vite-ts
  → copy eslint.config.js                        (no placeholders, drop-in)
  → run cross-cutting/merge_package_json.py (dry run) against
    package.json.tooling.snippet.json            (gap report, no writes)
  → you review, run the printed install command yourself,
    re-run cross-cutting/merge_package_json.py --apply (merges scripts +
                                                     lint-staged keys only —
                                                     never touches deps,
                                                     dependency installs are
                                                     a separate manual step)
  → append husky-pre-commit.snippet.sh into .husky/pre-commit
    (money-disk already has husky wired for tsc — this ADDS
    lint-staged to the existing hook, doesn't replace it)
```

## package.json: two files, two modes — not one

- `package.json.tooling.snippet.json` is the **augment-mode** reference:
  quality tooling only (eslint/husky/vitest/lint-staged + react/vite core,
  since any realistic augment target already has those). It's diffed
  against an _existing_ package.json — never overwrites present entries,
  regardless of version skew, only reports genuine gaps.
- No `dev`,`preview` or `build` in package json templates since these get created upon `npm create vite` default scaffolding.

A `package.json.full.template` for **MODE=new** (igniting from zero)
doesn't exist yet — that one would be copied wholesale into an empty
project, no diff needed, and would additionally carry the _feature_
stack choices (router, charting lib, etc.) that don't belong in the
generic tooling snippet. Not built yet; only the augment path is proven.

## The merge script's guarantees (validated against real money-disk-ui data)

- Diffs `dependencies` and `devDependencies` by name only — present
  entries are reported but never touched, no matter how far their
  pinned version has drifted from the template's. Version reconciliation
  is explicitly out of scope; an older pin can be a deliberate choice.
- Diffs `scripts` and `lint-staged` by key: missing → proposed merge,
  present-and-matching → skip, present-and-different → **CONFLICT,
  flagged, never silently overwritten.**
- Package manager (yarn/npm/pnpm) detected from the lockfile already
  in the repo, never assumed.
- Live-tested against the actual money-disk-ui package.json: 13/13
  devDependencies + 2/2 dependencies + 4/4 scripts already matched;
  `lint-staged` was the one genuine gap the report surfaced.

## @types/\* rule (easy to get wrong when extending to other stacks)

TS-authored packages ship their own `.d.ts` and need no `@types/*`
entry (`vite`, `@vitejs/plugin-react`, `typescript-eslint`, `vitest`
— none have or need a DefinitelyTyped twin). JS-authored packages
need a separate `@types/*` entry only if one exists on DefinitelyTyped
(`react` → `@types/react`, `react-dom` → `@types/react-dom`). Check
this explicitly per-package when adding a new stack template — don't
assume symmetry with react's pattern.

## Money-disk-specific facts worth remembering while generalizing

- Money-disk already had `tsc` + husky pre-commit before this flag
  was applied. The template assumes tsc is already there and adds
  eslint alongside it via lint-staged, rather than owning the whole
  pre-commit file. If a future project has neither, this atomic script
  needs a branch that writes `.husky/pre-commit` from scratch instead
  of appending — not built yet, only the "append" path is proven.
- ESLint flat config (v9+) assumed. If a project pins ESLint 8,
  this template is wrong wholesale (`.eslintrc.cjs` shape, different
  package names) — that's a different flag value, not a variant of
  this one, if it ever comes up.
- First manual pass on money-disk surfaced the initial noise/fix
  round. Whatever specific rule violations you fixed → Notion
  cluster candidate, not this file. This file stays generic.

## Boundary with agent-lint-handling

This flag makes ESLint exist and run in CI/pre-commit.
It says nothing about what an _agent_ does when ESLint fails on
code the agent wrote — that's `skills/devops/agent-lint-handling/`,
which depends on a later stage (`implement.yml` doesn't exist yet).
