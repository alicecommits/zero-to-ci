# zero-to-ci — husky pre-commit provisioning handoff

Companion to `1_CHECKLIST_INTERPRETER_HANDOFF.md` and `2_TSCONFIG-HANDOFF.md`, and
`3_MODE-NEW-SIMPLIFICATION-HANDOFF.md` and `4_GITIGNORE-HANDOFF.md`. This
note covers a new step type, `ensure_line_in_precommit`, and the specific
cross-cluster ordering problem that makes it more than a copy of
`ensure_block_in_gitignore`.

## Why this is a SIBLING to `ensure_block_in_gitignore`, not the same

mechanism

Both step types share the surface goal ("append content to a file if not
already there, don't duplicate on re-run"), which is why folding them
together was considered and explicitly rejected in
`4_GITIGNORE-HANDOFF.md`. The reasons that split holds, restated for this
file specifically:

- `.gitignore` blocks are order-independent — patterns can appear in any
  sequence and the file still works correctly. `.husky/pre-commit` lines
  are **order-dependent** — it's a shell script executed top to bottom,
  and the order genuinely changes behavior (see below).
- Gitignore blocks are multi-line, comment-headed units with no
  structural relationship to each other. Pre-commit lines are single
  shell invocations with no comment structure, but a real sequencing
  constraint between them.
- Gitignore always targets exactly one fixed file. Pre-commit's target is
  also fixed (`.husky/pre-commit`), but unlike gitignore, a missing file
  entirely is a real, expected case this needs to handle (a project with
  no husky yet at all) — gitignore always assumes the file already
  exists (create-vite or git itself typically provides a starting one).

Build `ensure_line_in_precommit` as its own step type. Don't generalize
it and `ensure_block_in_gitignore` into one interface later just because
they end up looking similar in code — the semantic differences above are
real, not incidental.

## The actual problem: cross-cluster ordering

Two separate clusters each want to contribute a line to the same file,
and the correct **file order** is the reverse of their **evaluation
order**:

```
typescript-check     priority 0   wants to add: yarn typecheck
lint-staged-hooks     priority 4   wants to add: npx lint-staged
```

Desired final file content:

```bash
npx lint-staged
yarn typecheck
```

`lint-staged` first because it's the fast, staged-files-only check;
`typecheck` last because it's the slower, full-project gate (see the
earlier design discussion — lint-staged and full typecheck are NOT
redundant, both stay). But `lint-staged-hooks` is evaluated at priority 4,
_after_ `typescript-check` at priority 0 — if each step naively appended
its line the moment its cluster fired, the file would end up in the
wrong order (typecheck first, lint-staged second), silently, with no
error to signal it.

**This is a new category of cross-cluster coordination problem, distinct
from the one already flagged in `2_TSCONFIG-HANDOFF.md`** (one cluster
needing to _read_ another cluster's diagnostic outcome, e.g.
`lint-staged-hooks` branching on `linter-detection`'s result). This one
is about _write ordering_ between two clusters' outputs landing in the
same file, not about one cluster's logic depending on another's report.
Solve it with its own mechanism — don't try to force this into the
"read a prior rule's report" pattern, since there's no diagnostic being
read here, just two write proposals that need reconciling by position.

## The fix: decouple evaluation order from file order

`ensure_line_in_precommit` steps carry an explicit `order` field,
independent of the owning rule's `priority`:

```yaml
# inside lint-staged-hooks (priority 4)
- type: ensure_line_in_precommit
  command: "npx lint-staged"
  order: 10

# inside typescript-check (priority 0)
- type: ensure_line_in_precommit
  command: "yarn typecheck"
  order: 20
```

Interpreter contract:

- Do **not** write into `.husky/pre-commit` as each step fires. Instead,
  stage every proposed line into a new `plan["precommit_lines"]` list —
  each entry carrying its `command` and `order` — as rules are evaluated
  in their normal priority sequence.
- Only after **all** rules have been evaluated, sort
  `plan["precommit_lines"]` by `order` and produce the final proposed
  file content from that sorted list.
- This mirrors the existing "defer, then reconcile" pattern
  `dependency_presence` already uses via the `staged` dict for package
  presence — same idea, applied to line position instead of dependency
  state. Reuse that mental model rather than inventing a new one.

Ordering convention: leave gaps between values (10, 20, not 1, 2) so a
future third line can be inserted between two existing ones without
renumbering everything that already has an assigned `order`.

## The all-or-nothing gate — same conservatism as `install_if_absent_all`

Only auto-propose the fully-ordered block when `.husky/pre-commit`
contains **none** of the managed lines yet. This mirrors
`install_if_absent_all`'s "all absent" gate, applied here to file lines
instead of dependencies:

- **None of the managed lines present** → propose the full, correctly
  ordered block as one atomic write.
- **File doesn't exist at all** → same as above; this is `husky-setup`'s
  job to create the file first (see `2_TSCONFIG-HANDOFF.md`'s note on
  `husky-setup` needing to exist as a prerequisite cluster before
  anything can append into it — same dependency applies here).
- **Some but not all managed lines already present** (e.g. a human
  hand-added `yarn typecheck` before `lint-staged-hooks` ever ran) →
  **do NOT silently insert the missing line into "correct" position.**
  That means editing around existing, possibly hand-placed content —
  exactly the kind of mutation this project has refused to do
  everywhere else (never overwrite, never reorder existing content).
  Surface this as a `conflicts`- or `reports`-style entry instead:
  "pre-commit exists but managed-line set is incomplete or ordering
  doesn't match expected — resolve manually." Never guess where to
  splice a missing line into a file a human may have already edited.

## What NOT to do

- Don't let individual clusters write directly into
  `.husky/pre-commit` as a side effect of their own step evaluation.
  All pre-commit line proposals must flow through the same
  `plan["precommit_lines"]` staging list and get reconciled once, at the
  end of the run — never written incrementally, mid-pass.
- Don't collapse this into `ensure_block_in_gitignore` for code reuse.
  The ordering requirement and the "file may not exist yet" case are
  real behavioral differences, not styling differences.
- Don't auto-resolve the "some lines present, others missing" case by
  inserting at what seems like the statistically likely correct spot.
  If the interpreter can't be certain, it reports and stops — same
  "recognize the edge of your own competence" principle already applied
  to `tsconfig-file-shape-report`'s `unrecognized`/`absent` outcomes.

## Immediate next steps

1. Implement `ensure_line_in_precommit` in `checklist_interpreter.py`,
   including the `plan["precommit_lines"]` staging list and the
   end-of-run sort-by-`order` reconciliation step.
2. Add the `order: 10` / `order: 20` steps to `lint-staged-hooks` and
   `typescript-check` respectively (the only two managed lines that
   exist today).
3. Confirm `husky-setup` (priority 3, per the earlier ordering
   discussion) creates `.husky/pre-commit` as an empty or
   husky-default-content file before `lint-staged-hooks` (priority 4)
   ever attempts to append into it — this dependency already existed
   conceptually, this handoff just makes the shared file-existence
   precondition explicit for both consumers (gitignore's blocks don't
   have this problem, since `.gitignore` is assumed pre-existing).
4. Write a test case for the "some lines present, some missing" gate
   specifically — this is the one branch most likely to be implemented
   incorrectly by silently trying to be helpful instead of reporting.
