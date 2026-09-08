# zero-to-ci — package manager choice at bootstrap time

Companion to `1_CHECKLIST_INTERPRETER_HANDOFF.md` and
`3_MODE-NEW-SIMPLIFICATION-HANDOFF.md`. This note covers `--frontend-pm`,
the new bootstrap-time flag letting a fresh project be scaffolded with
yarn or pnpm instead of the previously-hardcoded npm, and the dedicated
script (`scripts/stacks/frontend/react-vite-ts/package_manager_setup.py`)
that implements it.

## What already existed, and what this adds

`scripts/cross-cutting/checklist_interpreter.py`'s `detect_package_manager()`
already reads whichever lockfile is on disk (yarn.lock / pnpm-lock.yaml /
package-lock.json) and renders every downstream command (install
proposals, the `ensure_line_in_precommit` typecheck line) in the right
pm's syntax. That part was never the gap — it's fully general, works for
any pm, unchanged by this note.

The actual gap: in the bootstrap branch (`react-vite-ts.py`'s
`if not Path("package.json").exists()` block, see
`3_MODE-NEW-SIMPLIFICATION-HANDOFF.md`), the install step that runs right
after `create-vite` scaffolds files was hardcoded to `npm install` —
always. `detect_package_manager()` had nothing to detect from yet at that
point; whatever install command ran first is what decided the lockfile,
and therefore the pm, for the rest of the project's life. Choosing yarn
or pnpm meant manually deleting `package-lock.json`/`node_modules` after
the fact and re-installing by hand. This note replaces that hardcoded
call with a real, validated choice.

## Why npm can't just be swapped for yarn/pnpm as a bare word substitution

Unlike npm (bundled with Node itself — always present), yarn and pnpm are
not guaranteed to exist on a fresh machine. This repo's whole premise
(see `0_FROM-PKG-DIFF-TO-CHECKLIST-RULES-PARADIGM.md`) is a "naive user,
nothing installed yet" target — so the script can't assume `yarn` or
`pnpm` resolve on PATH just because the user asked for one.

The fix is **corepack** — shipped with Node core since 14.19/16.9,
cross-platform (mac/Windows/Linux alike, since it's part of Node's own
distribution, not an OS-specific tool). Two real caveats, not
hypothetical:

- Corepack's own bundling-by-default status has been shifting in newer
  Node majors (movement toward requiring a separate
  `npm install -g corepack` rather than assuming it's always there) —
  don't assume it exists, verify.
- `corepack enable` writes shim executables. On a user-writable Node
  install (nvm, fnm, homebrew) this needs no elevation. On a Node
  installed system-wide (Windows into `Program Files`, Linux via `apt`
  into `/usr/lib`) it can need admin/sudo — a real friction point for
  the "fresh machine" persona this repo targets, not an edge case to
  wave away.

`npm install -g yarn` was considered and rejected as the activation
mechanism: it only ever gets you Yarn Classic (1.x) — Yarn's own docs
steer away from it for modern (Berry, 2/3/4) installs. Corepack is the
only mechanism that gets the actual currently-recommended version of
either yarn or pnpm without guessing.

## `enable` and `prepare` are different commands — both are required

- `corepack enable` — wires up the interception shim only. Downloads
  nothing.
- `corepack prepare <pm>@<spec> --activate` — the actual fetch + pin
  step. Without it, the first real `yarn install` call would still work,
  but would silently fetch whatever version on the fly, mid-install —
  non-deterministic and invisible, in a repo that otherwise pins every
  version explicitly (`skills/frontend/react-vite-ts/package-versions.yaml`).

Both are treated as **one atomic gate** — checking `enable`'s exit code
alone isn't enough, since `enable` can succeed while the version fetch in
`prepare` still fails (network, bad pin, registry down). A single
attempt, no retry loop: any failure in either step falls straight
through to an npm fallback, loudly, not silently.

```
corepack enable
    │
    ├─ exit ≠ 0 (or corepack binary not found at all) ──┐
    │                                                    │
    ▼ exit 0                                             │
corepack prepare <pm>@<spec> --activate                  │
    │                                                    │
    ├─ exit ≠ 0 (or corepack binary vanished) ───────────┤
    │                                                    ▼
    ▼ exit 0                                    print RED_ORANGE warning:
<pm> install                                     "<reason> — falling back
    (chosen pm; produces                          to npm install"
    <pm>'s own lockfile)                                   │
                                                            ▼
                                                     npm install
                                                (package-lock.json,
                                                 not <pm>'s lockfile —
                                                 stated explicitly in
                                                 the warning, not left
                                                 implicit)
```

If the npm fallback itself then fails, that's not caught specially — it
propagates as a normal `subprocess.CalledProcessError` and crashes loud,
same as every other `check=True` call in this repo's stack scripts. A
broken npm on a machine that's supposed to have Node bundled with it is
a genuinely broken environment, not something to paper over.

## Where this lives, and why

`scripts/stacks/frontend/react-vite-ts/package_manager_setup.py` — a
dedicated script, invoked by `react-vite-ts.py`'s bootstrap step via
`subprocess.run`, the same pattern `react-vite-ts.py` already uses to
invoke `checklist_interpreter.py`. Not a plain function import: corepack
activation is a genuinely distinct concern with its own failure modes and
its own colored status output, and — same as `checklist_interpreter.py`
— keeping it a separate process means it's independently runnable and
testable without dragging in `react-vite-ts.py`'s own state.

**Deliberately nested under `react-vite-ts/`, not promoted to
`scripts/cross-cutting/`, as of 2026-09-08** — same "don't extract before
a second consumer forces it" discipline as everywhere else in this repo
(`CONFIG_OWNERSHIP_MATRIX.md`'s own "when to revisit" section makes the
same call for its NOT YET EXTRACTED rows). This is the only Node-based
stack in the repo right now. Nothing inside `package_manager_setup.py` is
actually react-vite-ts-specific — it takes a bare `repo_dir` and a `pm`
string, knows nothing about React, Vite, or this stack's clusters — so
the day a second Node-based stack lands (a `nodejs-nestjs` backend is the
likely first candidate), promoting it to
`scripts/cross-cutting/package_manager_setup.py` is a straight file move,
not a rewrite. `skills/frontend/react-vite-ts/NOTES.md` carries the same
flag inline, next to this stack's other "not yet extracted" notes.

## The flag itself: `--frontend-pm`, registered in `spin_up.py`

Unlike `augment_legacy_linting`/`augment_legacy_tsconfig` (deliberately
**not** wired through `spin_up.py` — manual-invoke only, opt-in
remediation of an already-existing legacy project, a judgment call a
human should trigger deliberately), `--frontend-pm` **is** registered in
`spin_up.py`'s dispatcher and forwarded to the stack module's `run()`.
Reason for the split: package manager choice is a structural decision at
project-**creation** time — literally which subprocess commands run
during bootstrap — not a remediation flag layered onto an existing
project. It belongs in the main dispatch path the same way `--frontend`
itself does.

`spin_up.py` still stays dispatch-only in the sense that matters: it
registers the flag and forwards its raw string value, nothing more. It
does **not** carry a `choices=["npm", "yarn", "pnpm"]` constraint — that
validation lives in `package_manager_setup.py`'s own `ALLOWED_PMS`, so
the dispatcher never embeds any one stack's ecosystem knowledge. Passing
garbage to `--frontend-pm` surfaces as a clear argparse error one level
down, not a silent no-op or a hardcoded list duplicated in two places.

`ALLOWED_PMS = ("npm", "yarn", "pnpm")` inside that script is also
deliberately just this one stack's own list, not yet a cross-stack
dict — the idea raised during design (a `{stack: [allowed pms]}` mapping,
since a future python stack would never pair with pnpm, and a real
project might reasonably want yarn on the frontend and pnpm on a Node
backend) is sound but premature: only one stack exists, so there is
nothing yet to force a shared mapping into existence. Revisit this the
same moment `CONFIG_OWNERSHIP_MATRIX.md` says to revisit its own NOT YET
EXTRACTED rows — when a second stack actually needs it.

## What has been verified for now

Live-tested against a real fresh directory on my machine (`corepack
--version` confirmed present, nvm-managed Node — no elevation needed):
`--frontend-pm npm` (unchanged default path, produces `package-lock.json`,
downstream plan correctly prints `-- proposed install (npm) --` and
`npm run typecheck`) and `--frontend-pm yarn` (corepack enable + prepare
both succeed, `corepack ready (yarn@stable, activated)` printed, `yarn
install` produces `yarn.lock` with no stray `package-lock.json` left
behind, downstream plan correctly prints `-- proposed install (yarn) --`
and `npx lint-staged` / `yarn typecheck` in the right order). The
corepack-missing and enable-succeeds-prepare-fails fallback branches were
exercised with the real subprocess calls stubbed out (no way to actually
uninstall corepack from a working machine to prove this end-to-end) —
both correctly print the `RED_ORANGE` warning naming the exact failure
and fall through to `npm install`.

## 2026-09-08 follow-up — two real bugs found running against a real mock repo, both fixed

The version above claimed "verified end-to-end" based on a target
directory sitting directly under `/tmp` — no parent directory above it
had its own `package.json`. Running against an actual mock-repo layout
(a `mock_spinup_repo/` folder holding several trial scaffolds as
siblings, itself carrying a `package.json`) surfaced two real failures
neither of which was hit by the narrower `/tmp` test:

**Bug 1 — Yarn Berry refuses to install in a directory it doesn't
recognize as its own project root.** Reproduced directly: scaffold
`trial5/` inside a parent directory that itself has any `package.json`,
run `yarn install` inside `trial5/` with no `yarn.lock` there yet — Yarn
walks UP looking for the nearest enclosing "project," finds the parent's
`package.json`, and refuses:

```
Usage Error: The nearest package directory (.../trial5) doesn't seem to
be part of the project declared in .../mock_spinup_repo.
```

Yarn's own error message names the fix: pre-create an empty `yarn.lock`
in the target directory before the first `yarn install`, which pins that
exact directory as its own root regardless of what's above it. Now done
in `setup_and_install()` — `repo_dir / "yarn.lock"` is touched (only if
absent) immediately before the `yarn install` call, for `pm == "yarn"`
only (not reproduced for pnpm — see Bug 2's very different failure mode
for why that wasn't a clean test either way). No-op when `repo_dir`
already is the nearest project.

**Bug 2 — corepack activating successfully does not guarantee the actual
install call will succeed.** Found while checking whether pnpm shared
Bug 1's failure mode — it didn't reproduce that one, but hit a different,
real failure: `corepack prepare pnpm@latest --activate` reported success,
yet the subsequent `pnpm install` crashed with a raw
`Error: Cannot find module '.../corepack/v1/pnpm/12.3.4/bin/pnpm.cjs'`
— a corrupted local corepack pnpm cache, invisible to the enable/prepare
gate since both of those genuinely did exit 0. This means the
enable+prepare atomic gate described above was necessary but not
sufficient — a third failure mode existed between "corepack says it's
ready" and "the package manager actually runs," and it previously hit a
raw `subprocess.CalledProcessError` traceback, the exact kind of ungraceful
crash this whole design was supposed to avoid.

Fixed by extending the same fallback treatment to the install call itself:
`[pm, "install"]` now runs through `_run()` (the same helper used for
`enable`/`prepare`, tolerant of both "binary not found" and "non-zero
exit") instead of a raw `check=True` call. Any failure there — same as an
enable/prepare failure — prints the `RED_ORANGE` warning and falls
through to `npm install`, never a raw traceback. One subtlety this
required: if `touched_yarn_lock` was set (Bug 1's fix ran) and the
install call still fails for some unrelated reason, the just-created
empty `yarn.lock` is deleted before falling back — otherwise it would be
left behind, empty, and `detect_package_manager()` (which checks
`yarn.lock` first) would wrongly report "yarn" on a project that was
actually installed via npm.

Both fixes verified against the exact reproducing scenarios: the real
`mock_spinup_repo/trial5` layout with `--frontend-pm yarn` now completes
cleanly (`yarn.lock` produced, no crash); `--frontend-pm pnpm` against
this same broken-cache machine now prints the `RED_ORANGE` warning and
produces `package-lock.json` via the npm fallback instead of crashing.
Neither of these was exercised by the original (narrower) verification
pass above — left uncorrected here rather than rewritten, per this
repo's own "don't edit frozen prior verification claims, add a dated
follow-up instead" convention (see `1_CHECKLIST_INTERPRETER_HANDOFF.md`'s
own addenda for the same pattern).
