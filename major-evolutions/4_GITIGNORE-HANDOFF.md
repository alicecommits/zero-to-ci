# zero-to-ci — gitignore provisioning handoff

Companion to `1_CHECKLIST_INTERPRETER_HANDOFF.md` and `2_TSCONFIG-HANDOFF.md`, and
`3_MODE-NEW-SIMPLIFICATION-HANDOFF.md`. This note covers a new concern:
each cluster that introduces a tool should also own that tool's
`.gitignore` footprint, rather than gitignore being handled as one
separate, late-stage cluster trying to reconstruct ownership from
outside.

## Why this needs its own step type, not `object_key_value` or a naive

line-by-line check

`.gitignore` entries come in **semantic blocks** — a comment header plus
one or more related patterns that only make sense together (e.g. `# Husky
internal helpers` + `.husky/_`). A line-by-line presence check risks two
failure modes: proposing a block's patterns without its header (context
lost), or proposing only some of a multi-line block because one pattern
happened to already exist for an unrelated reason. Neither is acceptable.

**New step type: `ensure_block_in_gitignore`.**
Contract: check whether the block's _meaningful_ lines (patterns, not
comments) are already present anywhere in `.gitignore`, in any order,
possibly interspersed with unrelated content. If **any** meaningful line
is missing, propose appending the **entire block**, verbatim, comment
header included, as one atomic unit. If **all** are already present
(anywhere in the file, not necessarily contiguous), no-op — this is what
lets a block "instantly grey out" when a human has already added it by
hand, without demanding exact formatting or position parity.

**Deliberately NOT shared with `husky-setup`'s pre-commit line-appending
need**, despite the surface similarity ("append content to a file if not
already there"). That's a conscious split, not an oversight: gitignore
blocks are always multi-line-capable, comment-headed, and target exactly
one fixed file (`.gitignore`), whereas the husky case is a single
invocation line with no comment structure, appended into a shell script
whose target filename varies less but whose semantics (must go at a
specific point in an executable script, not just "anywhere in the file")
differ enough to not be worth forcing into one interface. Build
`ensure_block_in_gitignore` scoped to `.gitignore` only — no `target`
field needed, it's implicit — and give husky's pre-commit append its own,
separately-named step type when that cluster gets built. Don't retrofit
one to serve both.

Step shape (no `target` field — always `.gitignore`, by design):

```yaml
- type: ensure_block_in_gitignore
  block: |
    # TypeScript build cache
    *.tsbuildinfo
```

## Ground rule: drop generic Node.gitignore cruft, don't template it

The reference "money-disk" gitignore pasted for comparison reads like
generic `gitignore.io`-style Node output, not a curated list for this
stack — Nuxt, Gatsby, Docusaurus, SvelteKit, VuePress, Serverless,
DynamoDB, Firebase, FuseBox, Bower, Grunt, Snowpack entries included, none
of which this stack (or any future stack this repo targets) will ever
use. **Do not template any of it.** Every block that ships in a cluster
must be traceable to a specific tool that specific cluster actually
installs. Cruft copied forward because "it was in the old file" undermines
the same "every line here is deliberate" discipline already enforced on
the dependency and script side of this project — gitignore doesn't get an
exception.

## Three-tier classification (do this triage before writing any block)

**Tier 1 — already written by `create-vite`'s own scaffold. No cluster
needed, ever.** Logs, `node_modules`, `dist`, `.local`, editor
directories. Same "bare minimum, don't redeclare" principle already
applied to the dependency baseline (`react`, `react-dom`, `vite`, etc.) —
these never need a checklist step because the scaffolder already writes
them, on every vintage.

**Tier 2 — genuinely owned by an existing cluster. Attach directly, no
new cluster.**

| block           | owning cluster                | content                                                               |
| --------------- | ----------------------------- | --------------------------------------------------------------------- |
| TS build cache  | `typescript-check`            | `*.tsbuildinfo`                                                       |
| test coverage   | `vitest-test-script`          | `coverage`, `*.lcov`                                                  |
| eslint cache    | `linter-baseline-remediation` | `.eslintcache`                                                        |
| husky internals | `husky-setup`                 | `.husky/_` only — **not** `.husky/` itself, which must stay committed |

Add one `ensure_block_in_gitignore` step to each of these four clusters'
existing `checklist:` list. No priority changes — the gitignore step
rides along with whatever priority the cluster already has, since it's
part of "does this tool's setup look complete," not a separate concern.

**Tier 3 — genuinely ambiguous. Needs a decision or its own cluster,
not an assumption.**

- **`vite.config.*.timestamp-*`, `.vite/`** — Vite's own runtime cache
  files. Notably **absent** from the official baseline pasted for
  comparison, which is suspicious enough to warrant verification rather
  than templating: check whether a _current_ `create-vite` scaffold
  writes these itself (possible they moved into Tier 1 in a version more
  recent than the reference baseline). Do not add this block to any
  cluster until that's confirmed one way or the other.
- **`.env`, `.env.*`, `!.env.example`** — real and worth having, but not
  owned by any _tooling_ cluster in the current design; it's a
  general-hygiene concern orthogonal to "which package/script did I just
  install." Give it its own small cluster (`env-gitignore`) rather than
  force-fitting it under an unrelated one just because a home needs to
  be found for it.
- **`.claude/`, `CLAUDE.md`** — specific to your own workflow, not a
  `react-vite-ts` stack concern at all. If you want this templated,
  it belongs in a separate, cross-stack cluster (or cross-stack skill),
  not inside any stack-specific rules file.

## What NOT to do

- Do not build a single monolithic `gitignore-setup` cluster that owns
  all blocks centrally. That recreates exactly the ownership-ambiguity
  problem concern-clustering was built to avoid elsewhere in this
  project — multiple tools' gitignore needs colliding in one place with
  no single clear owner per key (here, per block).
- Do not attempt exact-match / exact-position checking for blocks
  already present. A human who added `*.tsbuildinfo` by hand, differently
  formatted or in a different spot in the file, should still cause the
  step to no-op — the presence check is content-based, not
  position-based.
- Do not add Tier 1 content to any cluster "just in case." If it's ever
  found missing on a real project (an old scaffold predating some
  addition, or a hand-rolled non-create-vite project), that's a signal
  to reconsider the tiering for that specific line, not a reason to
  defensively template everything.

## Immediate next steps

1. Implement `ensure_block_in_gitignore` in `checklist_interpreter.py`,
   scoped to `.gitignore` only (see above — deliberately not shared with
   husky's pre-commit append, which needs its own step type later).
2. Add the four Tier 2 blocks to their respective existing clusters.
3. Verify the Vite runtime-cache question against a real, current
   `create-vite` scaffold before deciding where (or whether) it belongs.
4. Decide whether `env-gitignore` and any `.claude/`-specific cluster are
   in scope now or deferred — neither is urgent, unlike the four Tier 2
   blocks, which have a clear, already-existing owner and no open
   questions blocking them.
