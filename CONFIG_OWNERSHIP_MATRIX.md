# Config ownership matrix

Tracks, per configuration concern, whether it's a common denominator
across multiple stacks (belongs in `scripts/cross-cutting/` or a shared
template) or genuinely stack-specific (belongs in one `skills/<category>/<stack>/`
folder only). Referenced from `CLAUDE.md`'s DRY-architecture note — read
this before adding a new stack, to catch a concern that should be
extracted instead of duplicated.

Status legend:

- **LIVE** — implemented, currently wired into a real stack.
- **STACK-SPECIFIC (by design)** — correctly scoped to one stack; the
  concern itself varies per stack, extracting it would be wrong DRY.
- **NOT YET EXTRACTED** — genuinely common across stacks per its own
  definition, but only one stack exists so far, so it's still living
  inside that stack's files. Flag to revisit once a second stack lands.
- **NOT STARTED** — stack it would apply to doesn't exist in this repo yet.

## Matrix

| Config concern | Intent (why it exists — dev/devops best-practice synopsis) | Common to (by nature) | Currently wired in | Owner (file/script) | Status |
| --- | --- | --- | --- | --- | --- |
| package.json dependency/script/lint-staged diff+merge | 4 distinct Node-ecosystem roles, each with its own convention: `dependencies` = packages shipped to production, needed at runtime; `devDependencies` = tools needed only to build/lint/test, never shipped; `scripts` = named shortcuts (`npm run <name>`) standardizing how the team invokes dev/build/test/lint, so everyone (and CI) runs the same command instead of memorizing flags; `lint-staged` = restricts a pre-commit tool to only the files actually staged, not the whole repo. This merge script's own job is orthogonal to those 4 roles: bring a repo's baseline up to date in all of them without clobbering a dev's manual customizations — augment, never silently overwrite. | any Node-based stack, frontend or backend | react-vite-ts.py | `scripts/cross-cutting/merge_package_json.py` | **LIVE** — already extracted, stack-agnostic (diffs whatever `dependencies`/`scripts`/`lint-staged` keys a template declares, no react-specific logic in the script itself) |
| TypeScript type-checking (`tsc --noEmit`) | Catch type errors before they reach runtime or CI — standard gate in any TS pipeline, independent of whichever bundler runs the code. | any TS-based stack — react-vite-ts, future vue-vite-ts/svelte-vite-ts, future nodejs-nestjs backend | react-vite-ts.py | `typecheck` script inside `skills/frontend/react-vite-ts/package.json.tooling.snippet.json` | **NOT YET EXTRACTED** — CLAUDE.md's own example of a cross-stack concern; lives stack-locally only because no second TS stack exists yet to force the extraction |
| ESLint (flat config, v9+) | Static analysis to catch bugs and enforce consistent style before code review — near-universal JS/TS quality gate. | any JS/TS stack | react-vite-ts.py | `skills/frontend/react-vite-ts/eslint.config.js` | **NOT YET EXTRACTED / mixed** — the file currently bakes react-specific plugins (`eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`) together with the generic flat-config + `typescript-eslint` wiring; splitting the ECMAScript-generic half out is the next DRY candidate here |
| husky (git hook runner, as a dependency) | Run quality checks locally before a commit ever reaches CI — "shift-left," catch problems at the cheapest possible point. | any Node-based stack | react-vite-ts.py | devDependency in `package.json.tooling.snippet.json` | **NOT YET EXTRACTED** — the dependency itself is stack-agnostic; only the specific hook _content_ below is stack-specific |
| pre-commit hook content | The concrete decision of which checks actually block a commit — deliberately stack-owned, since the right gate depends on the stack's own toolchain. | stack-specific by nature (which checks run pre-commit varies per stack) | react-vite-ts.py | `skills/frontend/react-vite-ts/husky-pre-commit.snippet.sh` | **STACK-SPECIFIC (by design)** |
| lint-staged glob + command config | Only lint/typecheck files actually staged for commit, not the whole repo — keeps the pre-commit hook fast enough that devs don't bypass it. | stack-specific by nature (globs depend on the stack's file extensions) | react-vite-ts.py (`*.{ts,tsx}`) | `package.json.tooling.snippet.json` | **STACK-SPECIFIC (by design)** |
| vitest (unit test runner) | Fast, Vite-native unit-test feedback loop — part of the baseline "quality foundation" every project should start with. | vite-based stacks (react-vite-ts now; future vue-vite-ts, svelte-vite-ts) | react-vite-ts.py | `package.json.tooling.snippet.json` | **LIVE**, not yet generalized — only one vite stack exists so nothing forces extraction yet |
| Backend type-checking / linting (e.g. Pyright/Ruff for a Python stack, or `tsc`/ESLint again for nodejs-nestjs) | Same static-analysis and type-safety guarantee as the frontend row above, applied to server-side code. | backend stacks | none | not yet extracted | **NOT STARTED** — no backend stack exists in this repo yet |

## Scripts this matrix should stay in sync with

- `scripts/spin_up.py` — dispatcher; routes `--frontend <stack>` to `scripts/stacks/frontend/<stack>.py`.
- `scripts/stacks/frontend/react-vite-ts.py` — only atomic stack script that exists so far.
- `scripts/cross-cutting/merge_package_json.py` — the one concern already proven cross-stack; template for what "extracted" looks like for the NOT YET EXTRACTED rows above.
- `scripts/preflight.py` — verifies the react-vite-ts wiring landed; will need a matching check per stack as more get added.

## When to revisit this file

- Adding a second frontend stack (vue-vite-ts, svelte-vite-ts, etc.) — check every NOT YET EXTRACTED row above; if the new stack needs the same concern, that's the forcing function to actually move it into `scripts/cross-cutting/` or a shared template.
- Adding a first backend stack — same check, plus fills in the NOT STARTED row.
- Any time a concern's row would need a new "stack-specific" entry that's actually identical to an existing one — that's a live DRY violation, not just a future one.
