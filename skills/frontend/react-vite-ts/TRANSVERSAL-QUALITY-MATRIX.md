# react-vite-ts — transversal quality matrix

Sibling reference to `checklist-rules-react-vite-ts.yaml`. Not a
replacement for `CONFIG_OWNERSHIP_MATRIX.md` (that tracks WHICH STACK
owns a concern); this tracks something narrower — for THIS stack, how
its checklist clusters (rows, priority order) each feed into the
**transversal quality gates** shared across all of them (columns):
`.gitignore`, pre-commit, and CI once that exists. "Transversal" = the
gate isn't owned by any one cluster — `.gitignore` and
`.husky/pre-commit` are each one shared file/script any cluster can
contribute to.

**A tick means technical participation, not execution order.**
`typescript-check` evaluates at priority 1 but its pre-commit line lands
LAST in the actual file (`major-evolutions/5_PRECOMMIT-HANDOFF.md`) —
this table only answers "does this cluster contribute here," not when.
For actual sequencing, read the yaml's `priority`/`order` fields.

## Legend

| Mark      | Meaning                                                                                                                                                                                                                         |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ✓         | Direct mechanical step — this cluster carries its own `ensure_block_in_gitignore` / `ensure_line_in_precommit` step for this gate.                                                                                              |
| •         | Enabling participation only — this cluster installs the tool, or creates the file, that the gate depends on, but doesn't itself emit a block/line into it (the actual step lives in a different cluster, or doesn't exist yet). |
| _(blank)_ | No participation, direct or enabling.                                                                                                                                                                                           |

## The matrix

```
              transversal quality gates ────────────────────────▶
clusters
   │
   ▼
```

| Cluster (priority order)                                                                              | `.gitignore` | pre-commit | CI jobs _(not built yet)_ |
| ----------------------------------------------------------------------------------------------------- | :----------: | :--------: | :-----------------------: |
| Initial scaffold<br>`package_manager_setup.py`<br>+ `vite-baseline-gitignore`<br>_(bootstrap moment)_ |      ✓       |            |                           |
| `typescript-check`                                                                                    |      ✓       |     ✓      |                           |
| `tsconfig-file-shape-report`                                                                          |              |            |                           |
| `tsconfig-environment-report`                                                                         |              |            |                           |
| `linter-detection`                                                                                    |              |            |                           |
| `linter-baseline-remediation`                                                                         |      ✓       |     •      |                           |
| `husky-setup`                                                                                         |      ✓       |     •      |                           |
| `lint-staged-hooks`                                                                                   |              |     ✓      |                           |
| `vitest-test-script`                                                                                  |      ✓       |            |                           |
| `tsconfig-hygiene-remediation`                                                                        |              |            |                           |

CI column left blank on purpose — no CI workflow exists yet
(`README.md`'s "Current status"). Present so the axis is visible as a
whole; fill cells in later, no redesign needed.

## About the Initial Scaffold row (first table row)

**`package_manager_setup.py` isn't a checklist cluster at all** — a separate
script (`major-evolutions/6_PACKAGE-MANAGER-CHOICE-HANDOFF.md`) invoked
during bootstrap, before `checklist_interpreter.py` (and therefore
`vite-baseline-gitignore`, the first real cluster) ever runs. Merged
into one row with `vite-baseline-gitignore` because both belong to the
same bootstrap moment — package manager setup produces the lockfile,
`vite-baseline-gitignore` fills the `.gitignore` gap create-vite's own
scaffold leaves, and neither is meaningfully separable from "the project
just got scaffolded." No pre-commit tick: package manager choice affects
HOW pre-commit lines get _rendered_ later (pm-correct syntax), not
whether they exist — that's true of nearly every cluster indirectly and
isn't a distinguishing participation, so it doesn't earn a mark here.

## Meaning of the `•` marks

Both are cells a plain grep for `ensure_line_in_precommit` would miss:

- **`linter-baseline-remediation` → pre-commit:** installs `eslint` +
  `eslint.config.js`, never proposes a pre-commit line itself — but the
  line that does (`npx lint-staged`, in `lint-staged-hooks`) runs
  `eslint --fix` under the hood. Nothing to invoke without this install.
- **`husky-setup` → pre-commit:** its `create_file` step is what
  produces `.husky/pre-commit` at all. Every other cluster's
  `ensure_line_in_precommit` line gets appended INTO that file —
  nothing to append into without it.

Both real, load-bearing participants without carrying the mechanical
step themselves.

## Known gap

`vitest-test-script` has no pre-commit participation, direct or
enabling — deliberate, not an oversight. A full `vitest run` is often
too slow for a pre-commit default; pending its own decision (same
framing as `CONFIG_OWNERSHIP_MATRIX.md`'s pre-commit column).

## Keeping this in sync

Update this table whenever a cluster gains/loses a gitignore or
pre-commit step, or a new transversal gate (CI) gets built — same
discipline `CONFIG_OWNERSHIP_MATRIX.md` holds itself to.
