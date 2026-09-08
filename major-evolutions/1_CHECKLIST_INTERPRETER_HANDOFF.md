# zero-to-ci — handoff note (checklist-cluster augment engine)

> **Where this landed in the repo** (added when this note was integrated
> from a staging folder into the real tree — content below is otherwise
> unedited, preserved as the historical design record):
> `checklist_interpreter.py` lives in `scripts/cross-cutting/` (this note
> itself lives in `major-evolutions/`, alongside its 5 companion handoff
> notes, since 2026-09-08 — see that folder's own ordering).
> `checklist-rules-react-vite-ts.yaml` lives at
> `skills/frontend/react-vite-ts/checklist-rules-react-vite-ts.yaml`
> (stack-specific data, not cross-cutting logic — filename carries the
> stack name so a second stack's rules file doesn't collide). A separate
> `skills/frontend/eslint-baseline/` location for `eslint.config.js.template`
> was tried and reverted — too much indirection for the one stack
> currently using it; it lives under `skills/frontend/react-vite-ts/`
> alongside `tsconfig.json.template` and `vitest.config.ts.template`
> instead, all stack-local for now. Package-manager detection
> (yarn/npm/pnpm by lockfile presence) and install-command rendering,
> present in iteration 1 below, were ported into `checklist_interpreter.py`
> — omitting them on the initial port was a real regression, caught and
> fixed after integration. Iteration 1 (`merge_package_json.py`) has been
> deleted per this note's own "do not resurrect" — see
> `CONFIG_OWNERSHIP_MATRIX.md` for the current state of every concern
> this engine now owns.

This note is written for a fresh Claude Code session picking up implementation
work. It exists because the design went through three iterations before
landing on the current one, and the reasoning behind abandoning the first two
matters as much as the current shape does — don't rebuild the earlier
designs from first principles, they were deliberately retired.

## What this project is

**zero-to-ci** (renamed from an earlier "project-skills" working name) is a
CI/CD scaffolding repo with two real purposes:

1. Fast bootstrap of new projects with CI/CD tooling baked in from commit one.
2. A visible portfolio artifact demonstrating CI/CD rigor to recruiters.

It's being extracted from a real project, **money-disk-ui** (React/Vite/TS),
which acts as the origin/testbed: features get implemented there manually
first, then generalized into zero-to-ci's scripts/templates. The methodology
behind _how_ this extraction happens (see "spiral roadmap" in the project
files) is a means to an end, not the point of the project — don't over-index
on the roadmap language if it starts to feel like the goal itself.

## Core project-wide rule (non-negotiable, stated explicitly, applies everywhere)

> deterministic answer exists → script or template, never a skill
> one correct answer per flag value → script case branch
> copying a file with placeholders → template, script fills it
> judgment required, context-dependent → SKILL.md

This rule was tested against a real temptation to abandon it (see below) and
held. Treat any request to make routine package.json provisioning "agentic"
or "skill-based" as a rule violation unless the state space has genuinely
grown non-enumerable.

## The specific problem: augment-mode package.json provisioning

**Augment mode** = running the scaffolding tool against an _existing_ project
(as opposed to a brand-new one) to bring it up to the current CI/CD
baseline without destroying what's already there. The hard part is always
package.json: deciding what to install, what to add, and — critically —
never silently overwriting something a human already customized.

### Iteration 1 — flat diff (RETIRED, do not resurrect)

`merge_package_json.py` diffed `dependencies`/`devDependencies` by presence
only, and `scripts`/`lint-staged` by key equality with explicit CONFLICT
flagging. It worked and was live-tested successfully against real
money-disk-ui data (found `lint-staged` as the only genuine gap out of ~19
already-matched entries). It was retired not because it was wrong, but
because it diffed by _JSON section_ rather than by _semantic ownership_ —
there was no way to say "everything ESLint provisions is one unit" as
opposed to "everything under devDependencies."

Established facts from this iteration that still hold:

- package.json only ever installs packages; it never configures anything —
  config always lives in separate files.
- `packageManager` and lockfile fields must never be templated (Corepack-
  stamped, environment-specific).
- TS-authored packages (vite, @vitejs/plugin-react, typescript-eslint,
  vitest) need no `@types/*` twin. JS-authored ones (react, react-dom) do.

### Iteration 2 — YAML rule-chain with layers (RETIRED, do not resurrect)

`provision_rules.py` + `provisioning-rules.yaml`. Rules gated by a `layer`
number plus `when: {always/all_present/any_present}`, evaluated against a
"staged" union of on-disk state + earlier rules' proposals within one pass.
Included a `supersedes` mechanism for e.g. a TS-flavored lint-staged glob
replacing a JS-only default.

This iteration is **incompatible** with the current one — it sorts by
`layer`, not `priority`, and its step shape doesn't match. Don't try to
merge them.

**Why it was retired — a real bug, not just a stylistic preference:** a
trimmed "MVP" version of this interpreter had an `object_keys` diff that
conflated "missing" and "present-but-different" into the same write-worthy
bucket. This meant it would **silently overwrite a human's customized
`lint-staged` value with no warning**. This was proven live: a target
package.json with a hand-customized `prettier` entry under `lint-staged`
produced a byte-identical plan whether that key was absent or customized.
`scripts` also used inconsistent safety semantics vs `object_keys`
(skip-if-present vs overwrite-if-different) in the same codebase. Both of
these were real, demonstrated defects — not hypothetical concerns.

### Iteration 3 — checklist / concern-clusters (CURRENT — this is what ships)

The fix for iteration 2's bug wasn't a patch, it was a structural change:
**gate on true on-disk presence, not staged/proposed state**, and **group
checks by semantic ownership cluster** (e.g. "everything ESLint provisions"
lives in one rule) rather than by JSON section. Concern-clustering also
solves the overwrite-safety problem _by construction_: because clusters are
drawn so only one cluster ever has authority to _create_ a given key, there
is no multi-rule race or ambiguity over who owns e.g. the `lint-staged`
glob — it's not a bolted-on conflict detector, it's the shape of the data.

**Policy, stated explicitly and load-bearing:** existing nested keys are
never overwritten. Present-but-different always becomes a `conflicts` entry,
surfaced for a human, never auto-resolved. There is genuinely no code path
in the interpreter from "present but different" to a write — this isn't a
runtime check, it's an absence of a code path.

## Formal schema (this is what's attached alongside this note)

Two files ship with this handoff:

- `checklist-rules.yaml` — clusters for `typecheck-script` (priority 0),
  `vitest-test-script` (priority 1), `linter-detection` (priority 2,
  diagnostic-only).
- `checklist_interpreter.py` — the interpreter that walks rules sorted by
  `priority`, dispatching per-step on a `type` field.

Four step `type`s exist in the interpreter:

| type                    | contract                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dependency_presence`   | silent pass if present; else stages an install and feeds it forward to later steps/rules in the same run                                                                                                                                                                                                                                                                                                                                                                   |
| `script_value`          | missing key → `add_scripts`; present-but-different → `conflicts`, never overwritten; matches → silent no-op                                                                                                                                                                                                                                                                                                                                                                |
| `object_key_value`      | same present/missing/conflict contract as `script_value`, for nested keys (e.g. lint-staged globs). **Implemented but NOT exercised by any current cluster — still untested. Validate this before trusting it with `lint-staged-hooks`.**                                                                                                                                                                                                                                  |
| `multi_presence_report` | pure diagnostic. Never produces `install`/`add_scripts`/`add_object_keys`/`files` output under any circumstance. Currently supports exactly 2 named checks (labels ending `_present`); derives outcome as both_absent/both_present/{label}\_only/mixed.                                                                                                                                                                                                                    |
| `install_if_absent_all` | checks a LIST of `{section,name}` pairs; only installs/adds scripts **and creates any listed `create_files`** if **every** listed pair is absent. Used for baseline remediation where a single `dependency_presence` check isn't enough — e.g. don't install eslint (or create its config file) if oxlint is already the project's chosen linter. Always pair this with a rule-level `requires_flag` unless you're certain the remediation is safe to run unconditionally. |
| `create_file`           | standalone step: checks existence on `repo_dir`; proposes `"skip"` if present, or `"create from template: <path>"` if missing. **Now tested** — see below.                                                                                                                                                                                                                                                                                                                 |

Rules may also carry a top-level `requires_flag` field. A rule with
`requires_flag` is skipped unless that flag is passed to the interpreter
via `--flag <name>` on the CLI (repeatable). This is the mechanism that
keeps opt-in remediation (see `linter-baseline-remediation` below) inert
on a plain run — skipped rules are recorded in a `skipped_rules` key in
the plan output, not silently dropped.

### Config-file creation — a gap that was missing entirely from the first draft

package.json only ever installs packages; it never configures anything.
That means every cluster that installs a tool which needs a config file
(vitest, eslint) has to separately propose _creating_ that file — the
original draft of this ruleset didn't do this at all, which was flagged
and fixed. Three files, three different treatments:

| file               | ships with create-vite react-ts?                  | how it's handled                                                                                                                                                                                           |
| ------------------ | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tsconfig.json`    | yes, either vintage                               | **defensive-only** `create_file` step in `typecheck-script` — same spirit as that cluster's `typescript` dependency check: expected to already exist, this just guards against it having been deleted      |
| `vitest.config.ts` | **no, never** — vitest isn't part of any scaffold | **genuine gap** `create_file` step in `vitest-test-script` — fires on essentially every project that hasn't already set vitest up by hand                                                                  |
| `eslint.config.js` | only if eslint was chosen at scaffold time        | a `create_files` entry **nested inside `linter-baseline-remediation`'s `on_all_absent` block**, sharing the exact same all-absent gate as the eslint package install — NOT a standalone `create_file` step |

That third row is the one that took a second pass to get right. `create_file`
as a standalone step only ever asks "does this file exist on disk?" — it
has no way to know _why_ the file might be missing. A bare `create_file`
step bolted onto `linter-baseline-remediation` would have proposed creating
`eslint.config.js` even in the run where oxlint is already present and the
install correctly no-ops — wrong, because there'd be no eslint installed to
configure. The fix: `install_if_absent_all`'s `on_all_absent` block now
accepts an optional `create_files` list alongside `install` and
`add_scripts`, so the config-file proposal is gated by the identical
condition as the package install, not a second independent check. This was
tested directly: flag on + oxlint present → neither the eslint packages nor
`eslint.config.js` are proposed; flag on + genuinely no linter → both the
packages and the config file are proposed together.

`create_file` and the `create_files` sub-block are both now exercised by
real test cases (see "Validated test results" below) — no longer an
untested code path.

### Baseline these rules deliberately never redeclare

Already present on any create-vite react-ts scaffold, regardless of vintage
(see linter note below for why "regardless of vintage" matters):

```
dependencies:    react, react-dom
devDependencies: typescript, vite, @vitejs/plugin-react,
                 @types/react, @types/react-dom, @types/node
scripts:         dev, build, preview
```

### linter-detection is diagnostic-only — but there's now a real remediation path

Researched and confirmed directly from vitejs/vite source (not from
training-data memory, which was stale here): as of `create-vite@9.1.0`
(2026-06-23, PR "use Oxlint for react templates and add ESLint option"),
the official react-ts template defaults to **oxlint**, not ESLint, though
the CLI now offers an interactive choice of ESLint / Oxlint / None at
scaffold time. money-disk-ui predates this switch and uses ESLint — it is
not outdated, it was simply scaffolded before June 2026.

Because of this fork, `linter-detection` itself **never** installs or picks
a linter — it only reports which of eslint/oxlint/neither/both is present.
That part didn't change. What changed: "never remediate, period" turned out
to be too strong, and was corrected after pushback.

**The problem with a flat "never remediate" rule:** a `both_absent` result
looks identical on disk whether it means (a) a **legacy** project —
scaffolded before the June 2026 switch, or hand-rolled — that simply never
had linting set up (neglect, and exactly the kind of gap augment mode
should be able to fix), or (b) a **fresh** create-vite scaffold where the
interactive prompt was answered with a deliberate "None" (a conscious
choice that must never be silently overridden). The interpreter cannot
tell these apart from the package.json alone — nothing on disk records
"a human was asked and declined" versus "this predates being asked."

**Resolution: a second, separate, opt-in cluster — `linter-baseline-
remediation` (priority 2 as of the 2026-09-07 reorder; was 3 originally).**
It is NOT part of `linter-detection` and does
not run on a plain invocation — it only fires when the interpreter is
explicitly invoked with `--flag augment_legacy_linting`. You decide, per
run, which situation you're in; the flag is the human judgment call the
package.json itself can't encode. When it fires, it installs an ESLint
baseline (matching money-disk-ui's own convention, the pre-June-2026
default) via a new step type, `install_if_absent_all`, which only acts if
**both** eslint and oxlint are absent — so it can never step on an existing
oxlint choice even when the flag is passed. This was tested directly:
flag-off leaves a linter-less project untouched (and now surfaces in a new
`skipped_rules` key in the plan output, so you can see the rule existed and
was intentionally skipped, not silently absent); flag-on installs the
eslint baseline on a genuinely linter-less project; flag-on against a
project that already has oxlint changes nothing, because the "all absent"
gate correctly fails.

The generic mechanism behind this — a rule carrying a top-level
`requires_flag` field, skipped unless that flag is passed via `--flag` on
the CLI — is reusable for any future cluster that needs the same kind of
"only when the human explicitly means it" gating. Don't build a
special-case mechanism per cluster; reuse `requires_flag`.

**Your stated sandbox-testing plan:** when you run `create-vite@latest`
yourself and choose **None** at the linter prompt, your test project lands
in the `both_absent` bucket and — correctly — nothing remediates it unless
you separately pass the flag. That's the intended behavior: a fresh,
deliberate "None" and a neglected legacy project produce the same on-disk
signal, and only you, per run, can tell the interpreter which one you mean.

> **2026-09-07 addendum, not a rewrite of the above:** the cluster's
> `concern:` text and `CONFIG_OWNERSHIP_MATRIX.md`'s row were reworded to
> name LEGACY projects as the primary, intended scope up front (matching
> the flag's own name, `augment_legacy_linting`), rather than presenting
> legacy-neglect and fresh-deliberate-None as two equally-weighted cases.
> The underlying mechanism is unchanged — still opt-in, still can't
> distinguish the two from package.json alone, still never the default —
> this only tightens which scenario the docs foreground as _why_ you'd
> reach for this flag. The fresh-deliberate-None case is now a footnote,
> not deleted: it's still real and still a reason not to pass the flag
> against a project where None was a conscious choice.

### Outlined, not yet built

> **2026-09-07 addendum:** `lint-staged-hooks` below is now BUILT —
> eslint branch only, oxlint branch deliberately not built (not needed
> by any stack this repo currently supports; don't add speculatively).
> Required a new interpreter mechanism not anticipated when this was
> outlined: `requires_present: {section, name}`, a rule-level gate
> mirroring `requires_flag` but keying off on-disk/staged state instead
> of a CLI flag — lets a cluster branch on "whichever linter ended up
> present" without guessing, without needing a human judgment call the
> way legacy-vs-fresh does. `object_key_value` (see the schema table
> above) is exercised for real now, no longer untested — validated
> against real money-disk-ui data (correctly proposes only the genuinely
> missing `lint-staged` key; `husky` + `prepare` script both already
> present, correctly reported done, not re-proposed) and against the
> combined case (both `linter-baseline-remediation` and
> `lint-staged-hooks` firing in the same run, via staged-state
> feed-forward — one consolidated install command for both).
> `CONFIG_OWNERSHIP_MATRIX.md`'s husky/pre-commit-content/lint-staged
> rows updated to match. See `CONFIG_OWNERSHIP_MATRIX.md` for exactly
> what's still a manual step (`.husky/pre-commit`'s content — still not
> modeled, `create_file` can't express "exists but needs appending to").

> **2026-09-07 follow-up addendum:** husky/`prepare`/`.husky/pre-commit`
> existence were pulled OUT of `lint-staged-hooks` into their own new
> cluster, `husky-setup` (priority 3, between linter-baseline-remediation
> and lint-staged-hooks). Reason: `.husky/pre-commit` has to exist before
> anything can append into it (see the 2026-09-07 second follow-up below
> for the cluster that actually does the appending) — a hard
> prerequisite, not a style ordering choice — and husky-setup itself
> doesn't need to know
> eslint-vs-oxlint at all (unconditional, no `requires_flag` or
> `requires_present`), unlike the cluster it unblocks. `create_file`'s
> exists-or-not semantics, which couldn't express `.husky/pre-commit`'s
> _content_ state, turned out to be the exactly right fit for its
> _existence_ — a genuinely binary question, unlike content. New template:
> `husky-pre-commit-base.template.sh` (empty base file, distinct from
> `husky-pre-commit.template.sh` which stays the append-only content).
> Priorities shifted: linter-baseline-remediation stays 2, husky-setup is
> new at 3, lint-staged-hooks moves 3→4, vitest-test-script moves 4→5.
> Live-tested both directions: money-disk-ui (husky/prepare/file all
> already present → all reported `done`, not re-proposed) and a fresh
> project with eslint but no husky at all (all three correctly staged
> together, feeding forward into lint-staged-hooks in the same run).

> **2026-09-07 second follow-up addendum:** the actual content-append gap
> — `.husky/pre-commit` existing but not yet calling lint-staged — is now
> closed too, by a new cluster `lint-staged-hook-wiring-into-pre-commit`
> (priority 5, right after lint-staged-hooks, before vitest-test-script
> which moves 5→6 at this point — see the third follow-up below for
> where it ends up finally). Required a SEVENTH step type not anticipated by the original
> schema table above: `file_content_present` — checks a real on-disk
> file for a distinctive `marker` substring (`"npx lint-staged"`), not a
> full diff against `template` (same never-reads-templates rule as
> `create_file`). Marker found → confirmed done. Marker absent (file
> missing entirely, or exists without it) → proposes
> `[staged] append content from template: husky-pre-commit.template.sh`.
> Deliberately a SEPARATE cluster from lint-staged-hooks, not folded in
> — different resource (`.husky/pre-commit`'s content vs. package.json),
> different step type, matches this whole ruleset's "group by semantic
> ownership" principle (iteration 3, above) rather than conflating two
> concerns that happen to be related. Same `requires_present: eslint`
> gate as lint-staged-hooks, same reasoning (the content is an
> eslint+tsc-files invocation, meaningless without eslint). Also caught
> and fixed in passing: `create_file` had been missing from the schema
> table this whole time — added. Live-tested: money-disk-ui's real
> pre-commit hook (marker absent) → correctly proposes appending;
> same file with the snippet manually pre-appended (marker present) →
> correctly reports `done`, not re-proposed. `react-vite-ts.py`'s old
> printed reminder for this gap is now dead code, removed — the
> interpreter's own plan output covers it.

> **2026-09-07 third follow-up addendum:** `lint-staged-hook-wiring`
> renamed to `lint-staged-hook-wiring-into-pre-commit` for clarity of
> intent, and split further — it only proposed the `npx lint-staged`
> line, but husky-pre-commit.template.sh has a SECOND line,
> `yarn typecheck`, with a genuinely different prerequisite: the
> `typecheck` script comes from typescript-check (priority 0,
> unconditional), not from eslint at all. Gating that line's proposal on
> eslint presence (the way lint-staged-hook-wiring-into-pre-commit
> correctly does for its own line) would wrongly suppress it on a
> project with no linter. Fix: a new sibling cluster,
> `typecheck-hook-wiring-into-pre-commit` (priority 6, right after,
> before vitest-test-script which moves 6→7), same `file_content_present`
> step type, different marker (`"yarn typecheck"`), UNCONDITIONAL — no
> requires_flag, no requires_present. Both clusters reference the same
> template file (husky-pre-commit.template.sh has both lines) but check
> and propose independently, so a partially-wired hook (one line
> present, not the other) is handled correctly — live-tested directly:
> a hook with only `npx lint-staged` already in it correctly reports
> that line `done` while still staging the `yarn typecheck` line
> separately. Known limitation surfaced, not fixed: the snippet's
> `yarn typecheck` line hardcodes yarn, unlike this ruleset's
> install-command rendering elsewhere (which correctly adapts to
> yarn/npm/pnpm via `detect_package_manager`) — flagged in both the new
> cluster's `concern:` and `CONFIG_OWNERSHIP_MATRIX.md`, not silently
> ignored, fix when actually asked for.

> **2026-09-07 fourth follow-up addendum:** the yarn-hardcoding
> limitation above is now fixed. `file_content_present` gained a second,
> optional way to specify its marker: `script: <name>` (instead of a
> literal `marker` string), rendered through a new function,
> `run_command(pm, script)`, using the same `plan['package_manager']`
> `install_command()` already relies on. NOT a bare find-and-replace of
> the word "yarn" — npm requires `run` for a custom script
> (`npm typecheck` fails outright), yarn and pnpm both support the bare
> form, so `run_command` branches per-pm the same way `install_command`
> already does. `typecheck-hook-wiring-into-pre-commit`'s step now uses
> `script: typecheck` instead of `marker: "yarn typecheck"` — both the
> presence check AND the `[staged]` proposal text use the real resolved
> command for whichever package manager was detected. `marker` stays
> exactly as it was for lines that don't invoke the package manager at
> all (lint-staged-hook-wiring-into-pre-commit's `"npx lint-staged"` is
> unaffected — npx is pm-agnostic, nothing to render). Live-tested
> against all 3 lockfiles: proposes `yarn typecheck` / `npm run
typecheck` / `pnpm typecheck` respectively; and confirmed the reverse
> — an npm project whose hook already has `npm run typecheck` correctly
> reports `done`, not re-proposed just because it isn't the yarn form.

```
lint-staged-hooks              priority: 4
  Branches on whichever linter ends up present after linter-detection
  and (optionally) linter-baseline-remediation:
    eslint present    -> wire eslint + tsc-files glob
    oxlint present     -> different CLI invocation
    still both_absent  -> don't fire at all
  This is also the natural place to finally exercise object_key_value
  for real, since lint-staged config lives under a nested key.

vitest-react-testing-library    priority: 5
  jsdom + @testing-library/react + @testing-library/jest-dom,
  built on vitest-test-script's presence being satisfied first.
```

## Why typescript-check comes before vitest-test-script

> **2026-09-07 addendum, updated:** this section originally said "priority 0
> (typecheck) before priority 1 (vitest)" — vitest-test-script is priority
> 7 now (after husky-setup, lint-staged-hooks, and both pre-commit-wiring
> clusters got built — see the addenda above — and linting was reordered
> ahead of vitest entirely, since linting is now considered part of the
> baseline; see `checklist-rules-react-vite-ts.yaml`'s own header comment
> and `CONFIG_OWNERSHIP_MATRIX.md`). The cluster itself is still priority
> 0, now named typescript-check (tried typecheck-script, then
> typescript-hygiene, settled on typescript-check — see its own `concern:`
> text for why); the reasoning below for why it precedes vitest-test-script
> is otherwise unchanged and still holds.

Not arbitrary ordering. `tsc-files` — the tool that will eventually type-check
only _staged_ files inside the future `lint-staged-hooks` pre-commit cluster —
assumes a working plain `tsc --noEmit` invocation already exists as a sanity
baseline. Confirm cheap, foundational checks before layering a test runner's
own type expectations (e.g. Vitest globals) on top, since a stray
`tsconfig.json` `types` array clash between the two is the classic failure
mode this ordering avoids.

## Validated test results (already run, don't re-litigate these)

Original three scenarios, run against the pre-config-file version of the
interpreter + rules:

1. **Real money-disk-ui package.json** → all three clusters resolve clean,
   zero installs/adds needed, `linter-detection` correctly reports
   `eslint_only`.
2. **Synthetic fresh project** (only react/react-dom/vite present) →
   correctly proposes installing typescript + vitest, adds both scripts,
   reports `both_absent` for the linter.
3. **Customized `typecheck` script** (`"tsc --noEmit --incremental"` instead
   of the expected `"tsc --noEmit"`) → correctly refuses to overwrite it,
   surfaces it in `conflicts` with both on-disk and expected values visible
   — **and** `linter-detection`'s independent report still fires correctly
   in the same run, proving one cluster's conflict never blocks another
   cluster's unrelated diagnostic.

Additional scenarios, run after adding config-file creation
(`create_file` and the `create_files` sub-block of `install_if_absent_all`): 4. **Fresh project, no config files at all on disk** → proposes creating
both `tsconfig.json` and `vitest.config.ts`. 5. **Project with `tsconfig.json` already present, missing `vitest.config.ts`**
→ `tsconfig.json` correctly reports `"skip"`, `vitest.config.ts` still
proposed — confirms the two `create_file` steps are independent and
don't share state. 6. **`--flag augment_legacy_linting`, no linter present, no `eslint.config.js`
on disk** → install, `lint` script, AND `eslint.config.js` all proposed
together in the same run. 7. **`--flag augment_legacy_linting`, oxlint already present** → confirms
the negative case that matters most: neither the eslint packages, the
`lint` script, nor `eslint.config.js` are proposed. The gate on
`install_if_absent_all` correctly suppresses all three as one unit,
proving config-file creation can't drift out of sync with the package
install it depends on.

### Your next manual step (not yet done as of this handoff)

> **2026-09-07 addendum, updated:** priority numbers below are from the
> original handoff and are now stale — current order (see
> `checklist-rules-react-vite-ts.yaml`'s header comment for the full
> ordering rationale): typescript-check (0), linter-detection (1),
> linter-baseline-remediation (2), husky-setup (3), lint-staged-hooks (4),
> lint-staged-hook-wiring-into-pre-commit (5),
> typecheck-hook-wiring-into-pre-commit (6), vitest-test-script (7).
> The spiral-validation _intent_ below — fresh
> scaffold, "None" chosen, validate cluster by cluster — is still valid
> and still not done; just re-map it onto current cluster IDs rather
> than the numbers as literally written.

Scaffold a genuinely fresh, non-money-disk sandbox project:

```
npx create-vite@latest my-app -- --template react-ts
yarn install
```

Choose **None** at the linter prompt. Run the interpreter against this
project's real package.json (and pass `--repo-dir` pointing at the real
project root, so the `create_file` checks see real files, not just the
package.json in isolation) to validate priority-0 (typecheck) and
priority-1 (vitest) clusters — including their config-file proposals —
against a truly fresh scaffold, in "spiral" fashion — validate 0 and 1
solidly before moving on to exercising cluster 2
(linter-detection) or building cluster 3.

## Execution / gating design (conceptual only — nothing here is implemented)

Separate concern from the interpreter above: right now, running the
interpreter only ever produces a `plan` — a passive report. The open
question is how a `plan` gets turned into actual file writes, and who
authorizes that, differently for a human at a terminal vs. a future
non-interactive context (Wave 3 agent-invoked runs, Wave 5 CI).

Three mechanisms sketched, **none built**:

**1. Policy file** — pre-authorizes categories of action rather than
individual actions:

```yaml
# augment-policy.yaml
autonomy: supervised # supervised | autonomous
allow_without_confirmation:
  - install_missing_dependency
  - add_missing_script
  - add_missing_object_key
never_auto_apply:
  - resolve_conflict # always human, regardless of autonomy
```

This maps directly onto the `LINT_FIX_MODE: supervised|autonomous` concept
already present in the Wave 1 roadmap addendum — don't invent a second,
competing vocabulary for the same idea.

**2. Thin dual-mode wrapper** — flattens `plan` into `Action` objects, then
either prompts (interactive) or checks policy (non-interactive):

```python
def apply(plan, policy, interactive: bool):
    for action in plan_to_actions(plan):
        if action.kind == "resolve_conflict":
            record(action, decision="skipped: never_auto_apply")
            continue
        allowed = action.kind in policy["allow_without_confirmation"]
        do_it = confirm(f"{action.kind}: {action.summary}?") if interactive else allowed
        if do_it:
            action.execute()
        record(action, decision="applied" if do_it else "skipped: policy")
```

The `plan` → `Action` translation table is fixed and uniform, not inferred
per-entry:

```
plan["install"]          -> kind: "install_missing_dependency"
plan["add_scripts"]      -> kind: "add_missing_script"
plan["add_object_keys"]  -> kind: "add_missing_object_key"
plan["conflicts"]        -> (no kind — never becomes an Action, at all)
plan["reports"]          -> (no kind — never becomes an Action, at all)
```

This is a stronger guarantee than "policy forbids touching conflicts/
reports" — there is no code path in `plan_to_actions()` capable of
producing an Action from those two keys in the first place. Don't weaken
this into a policy check; keep it structural.

**3. Audit record** — a JSON log of every action taken or skipped and why,
standing in for the accountability a human's real-time "yes" would
otherwise provide:

```json
{
  "run_id": "2026-09-06T22:14Z",
  "mode": "non_interactive",
  "policy": "supervised",
  "actions": [
    {
      "kind": "install_missing_dependency",
      "detail": "lint-staged@^15.2.0",
      "decision": "applied"
    },
    {
      "kind": "resolve_conflict",
      "detail": "scripts.typecheck differs",
      "decision": "skipped: never_auto_apply"
    }
  ]
}
```

This ties to the Wave 1 roadmap's existing expectation that eslint fixes
eventually get reported "in the future, in GH issues (Wave 3)" — the audit
record is the mechanism that makes that reporting possible.

## The one deliberate architectural stance worth restating for any future session

Package.json provisioning is fully enumerable (present / absent / present-
but-different, times a small, slow-changing stack). That is exactly the
shape of problem that belongs to a script, never a skill. An agent's
correct role here is **design-time**: drafting candidate clusters,
researching current ecosystem defaults (e.g. the oxlint switch), catching
bugs in the ruleset's own logic (as happened with iteration 2's overwrite
bug) — with a human reviewing every output before it becomes a committed
rule. Once a cluster is settled, it collapses into a checklist entry the
interpreter runs for free, forever, without asking a model anything. Do not
propose moving routine provisioning into a `SKILL.md` or an agentic loop;
that idea was raised, evaluated seriously, and explicitly rejected for
concrete reasons (non-determinism, loss of provability, no reduction in
cataloguing burden, added latency/cost for zero payoff on a problem with no
remaining judgment to exercise).

The **one legitimate exception**, worth actually building when you get to
it: a fallback for `package.json` shapes no cluster recognizes at all (a
monorepo with multiple manifests, an unfamiliar bundler, a linter that's
neither eslint nor oxlint nor absent). The interpreter should surface
"unclassified state, here's what I see" and stop, rather than guess or
crash — that's the interpreter recognizing the edge of its own competence
and handing off to a human (or later, an agent) to decide whether a new
cluster needs writing. This is narrower and more defensible than routing
routine remediation through an agent, and it's the only place in this
system where that kind of judgment actually belongs.

## 2026-09-08 addendum — `ensure_line_in_precommit`, cross-cluster write ordering

Implements what `5_PRECOMMIT-HANDOFF.md` sketched: a step type letting more
than one cluster each contribute one line to `.husky/pre-commit`, with a
correct combined line ORDER even though `.husky/pre-commit` is an
executed shell script (order changes behavior) and the clusters that own
each line evaluate in an order that's the REVERSE of the file order they
need to produce (`typescript-check`, priority 1, must land its line
LAST; `lint-staged-hooks`, priority 7, must land its line FIRST).

Solved with a two-phase pattern, new to this interpreter (every step type
before this one resolves fully within its own per-rule evaluation):

- **Phase 1, per-rule (unchanged loop):** each `ensure_line_in_precommit`
  step does almost nothing itself — it appends `{command, order}` into
  `plan["precommit_lines"]`, a staging list initialized alongside
  `plan["files"]`/`plan["confirmed"]`/`plan["conflicts"]` at the top of
  `run()`. `command` is either a literal (`npx lint-staged`) or a
  `script` name rendered through the existing `run_command(pm, script)`
  (so `yarn typecheck` / `npm run typecheck` / `pnpm typecheck` all
  resolve correctly — this is the same pm-awareness fix that was applied
  earlier to the now-retired `file_content_present` mechanism, carried
  forward rather than re-broken).
- **Phase 2, once, after the per-rule loop:** `reconcile_precommit_lines()`
  runs after every rule has evaluated, regardless of cluster priority
  order. It sorts the staged lines by their own `order` field (10 for
  lint-staged, 20 for typecheck — independent of cluster `priority`),
  reads `.husky/pre-commit` once, and applies an all-or-nothing gate that
  deliberately mirrors `install_if_absent_all`'s conservatism: none of
  the managed lines present (file missing or present-without-them) →
  propose the full ordered block as one atomic `[staged]` unit; all
  present → `confirmed` (done, not re-proposed); some present → a
  `conflicts` entry listing `present`/`missing`, never spliced into a
  file a human may have hand-edited. `precommit_lines` is popped off the
  plan before `run()` returns — it's internal staging, never rendered
  directly.

**Retires two clusters, deliberately, not layers alongside them:**
`lint-staged-hook-wiring-into-pre-commit` and
`typecheck-hook-wiring-into-pre-commit` (built earlier via
`file_content_present`, each proposing one line independently with no
ordering guarantee between them) are removed from
`checklist-rules-react-vite-ts.yaml` entirely — don't resurrect them.
Their job is folded as one `ensure_line_in_precommit` step each into
`lint-staged-hooks` and `typescript-check` respectively. This was flagged
as a real conflict, not silently implemented around: the two old clusters
did the same job the new mechanism does, just without any ordering
guarantee, so keeping both would mean two independent, occasionally
contradictory proposals for the same file.

Deliberately a sibling of `ensure_block_in_gitignore`, not a
generalization of it — don't merge the two step types. Gitignore blocks
are multi-line and order-independent (content-set matching is enough);
pre-commit lines are single, order-DEPENDENT shell invocations, and nothing
about gitignore's matching logic needed a two-phase, cross-cluster
reconciliation pass. `CONFIG_OWNERSHIP_MATRIX.md` gained two new columns
("what to `.gitignore`" / "what to trigger as pre-commit") so each
cluster's contribution to both mechanisms is visible at a glance without
needing its own standalone row — the two retired clusters' rows were
removed rather than updated, since the concern they described no longer
maps to any cluster on its own.

Live-tested: none-present → full ordered block proposed (lint-staged line
first despite `typescript-check` evaluating first at priority 1 vs.
`lint-staged-hooks` at priority 7); all-present → confirmed, not
re-proposed; some-present → `conflicts` entry, never auto-spliced;
pm-awareness confirmed across all 3 lockfiles. Full end-to-end regression
via `spin_up.py --frontend react-vite-ts` against a synthetic fresh
`package.json` passes (exit 0, correct plan output).
