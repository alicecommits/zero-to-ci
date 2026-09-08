# zero-to-ci — tsconfig augment-mode handoff

Companion to the main `1_CHECKLIST_INTERPRETER_HANDOFF.md` (checklist-cluster engine, package.json
provisioning). This note is scoped to ONE new problem: extending the same
checklist-walkthrough pattern to non-package.json config files, starting
with `tsconfig.json`. Read the main handoff first — this assumes you
already know `dependency_presence`, `script_value`, `object_key_value`,
`install_if_absent_all`, `multi_presence_report`, `requires_flag`, and the
priority-ordered cluster model.

## Why tsconfig can't reuse the linter-baseline-remediation pattern as-is

`linter-baseline-remediation` gets away with installing a full baseline
into a void because "no linter at all" has one defensible default (ESLint).
tsconfig has no equivalent safe default — a legacy project's `tsconfig.json`
encodes real, load-bearing choices (`target`, `lib`, `module`,
`moduleResolution`) that a template can't guess. Dropping in a fresh
create-vite-shaped `target: es2023` config onto an `ES2020` legacy project
could silently change what code the compiler considers valid, or how it
transpiles — a correctness risk existing clusters don't carry. So tsconfig
needs a stricter split than linter remediation did, not the same policy
reused.

## The three-way split (this is the core design decision — don't collapse it)

**1. Structural/environment fields — diagnostic-only, PERMANENTLY. No flag
unlocks changing these, ever.**

Fields: `target`, `lib`, `module`, `moduleResolution`, `jsx`, `types`.
These encode real project constraints that no template can safely default
for an existing project. Unlike `linter-baseline-remediation`, do not add
a `requires_flag` escape hatch here — there is no version of "the human
explicitly asked for this" that makes guessing a `target` safe. Report
current values; never propose changing them. If this cluster's diagnostic
step is ever tempted to grow a remediation branch, that's a sign the
design is being violated, not a sign it needs updating.

**2. Hygiene/strictness flags — additive-only, flag-gated, same shape as
`linter-baseline-remediation`.**

Fields: `strict`, `noImplicitReturns`, `noUnusedLocals`,
`noUnusedParameters`, `noFallthroughCasesInSwitch`,
`exactOptionalPropertyTypes`, and similar. These are safety nets: turning
one on can surface new compile errors, but can't silently change runtime
behavior the way flipping `target` could. This is the legitimate use case
for `object_key_value` (already implemented, still needs real test
coverage — this cluster is a good place to finally exercise it for real).

Rules for this cluster:

- Only ever ADD a missing flag at its standard value.
- A flag that's present with a _different_ value than expected is a
  `conflicts` entry, same as everywhere else — never overwritten,
  regardless of flag state.
- Gate behind its own `requires_flag` (e.g. `augment_legacy_tsconfig`) —
  a legacy project may have relaxed strictness deliberately, and the file
  alone can't tell you "never configured" from "turned off on purpose."
  Don't reuse `augment_legacy_linting` for this; it's an unrelated concern
  and conflating flags removes the human's ability to opt into one
  without the other.

**3. File shape (single `tsconfig.json` vs. the triple
`tsconfig.json`+`tsconfig.app.json`+`tsconfig.node.json` split) —
diagnostic-only, never auto-migrate, no flag unlocks this either.**

Restructuring one shape into the other touches `vite.config.ts`
references and is genuinely invasive — multi-file, real risk of breaking
the build. Report which shape is present (`single` / `split` /
`unrecognized`) as a `multi_presence_report`-style diagnostic. Do not
attempt migration under any flag, current or future. If this ever needs
to change, it's a new, deliberately-scoped piece of work — not an
extension of this cluster.

## Concrete cluster layout to implement

```
tsconfig-environment-report     (new, diagnostic-only, always runs)
  reads whichever tsconfig shape is present (single or split; use the
  file-shape diagnostic's result to know which file(s) to read)
  reports target/lib/module/moduleResolution/jsx/types values verbatim
  NEVER produces install/add_scripts/add_object_keys/conflicts output —
  same guarantee as linter-detection's report-only contract

tsconfig-file-shape-report      (new, diagnostic-only, always runs)
  reports: single | split | unrecognized | absent
  "unrecognized" = neither shape matches (e.g. only tsconfig.app.json
  exists without the pointer tsconfig.json) — surface this and stop,
  same "recognize the edge of your own competence" principle already
  used elsewhere; do not guess
  "absent" = no tsconfig file at all found. KNOWN LIMITATION, BY DESIGN:
  no remediation exists for this outcome, under any flag. If typescript
  is already a devDependency (checked by typescript-check's priority-0
  step), a total absence of any tsconfig file is a rare, near-broken-repo
  edge case, not a normal augment target — there's no non-arbitrary way
  to choose "create 1 file" vs "create 3," so this cluster deliberately
  reports and stops rather than picking one. Treat this the same as
  "unrecognized": a human decides, the interpreter doesn't guess.

tsconfig-hygiene-remediation    (new, requires_flag: augment_legacy_tsconfig)
  object_key_value steps, one per hygiene flag listed above, targeting
  whichever file(s) tsconfig-file-shape-report identified as the actual
  compilerOptions holder (app.json in the split case, tsconfig.json in
  the single case — do not assume a fixed filename)
```

Keep these as three separate clusters, not one. Same single-responsibility
reasoning already applied to `linter-detection` vs.
`linter-baseline-remediation`: different remediation risk profiles
(none / none / additive-safe) should never share a rule just because
they're all "tsconfig-related."

## Priority placement

Slot these alongside the existing tsconfig-adjacent work
(`typecheck-script`, since renamed `typescript-check` in your local
copy) rather than at the very top — they're refinements of an established
concern, not a new foundational check:

```
0  typescript-check              (existing — package presence + typecheck script)
   tsconfig-environment-report  <- new, sits right after, same concern
   tsconfig-file-shape-report   <- new, same concern
1  linter-detection
2  linter-baseline-remediation
3  husky-setup
4  lint-staged-hooks
5  vitest-test-script
6  tsconfig-hygiene-remediation <- new, LAST — deliberately late.
                                    it's opt-in remediation with real
                                    "surprise new compile errors" blast
                                    radius, so it should run after every
                                    diagnostic-only cluster has already
                                    reported, not compete for early
                                    attention alongside them
```

The two diagnostic reports can safely sit at priority 0 (no risk, pure
information). The remediation cluster goes last for the same reason
`linter-baseline-remediation` isn't priority 0: opt-in, higher-consequence
clusters shouldn't front-run the cheap, always-safe diagnostics.

## Explicit non-goals for this pass — do not generalize preemptively

Do **not** build equivalent content-inspecting clusters for
`vite.config.ts` or `eslint.config.js` right now. Reasoning: tsconfig is
JSON — cheap, safe, purely declarative to inspect and diff. Those two are
executable JS/TS modules; checking "does this config already have X" means
parsing an AST, not a JSON key lookup, and safely patching one is a much
larger and riskier undertaking than anything built so far. For those two
files, existence-only checks (`create_file` if entirely absent — already
covered by the existing `vitest-test-script` and defensive `tsconfig.json`
steps) are the current ceiling. Only build deeper content-aware clusters
for them later if a real, specific gap is actually hit in practice — same
"don't build until you hit it" discipline already applied to the
Terraform-conflict skill in the main roadmap.

## Implementation note on file-shape branching

Every step in `tsconfig-environment-report` and
`tsconfig-hygiene-remediation` needs to know which physical file actually
holds `compilerOptions` before it can read or write anything — that's
determined by `tsconfig-file-shape-report`'s result, not assumed. This
means these two clusters have a real, in-code dependency on a prior
cluster's output, which is a new pattern: nothing in the current
interpreter passes one rule's `reports` entry into a later rule's step
config. Whatever mechanism you build for this — reading `plan["reports"]`
from within `run()` before evaluating later rules, most likely — should
be written generically enough that `lint-staged-hooks`'s existing,
already-designed-but-unbuilt dependency on `linter-detection`'s outcome
can reuse the same mechanism, rather than solving this twice.
