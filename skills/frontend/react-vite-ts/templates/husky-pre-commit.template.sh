# Human reference only, as of 2026-09-08 — no longer wired into any
# proposal. The two lines below used to be proposed via a
# file_content_present step referencing this file; that mechanism
# (lint-staged-hook-wiring-into-pre-commit / typecheck-hook-wiring-into-
# pre-commit) is retired — see major-evolutions/5_PRECOMMIT-HANDOFF.md. Both lines are now
# proposed by ensure_line_in_precommit steps folded directly into
# typescript-check and lint-staged-hooks, which generate the block
# content INLINE from their own `command`/`script` fields (same reason
# ensure_block_in_gitignore's gitignore blocks don't need a template
# file either — short enough to carry directly, no separate file to
# keep in sync). This file still shows the correct final order
# (lint-staged first, typecheck last) and the "may already run tsc"
# append-don't-replace caveat, useful context even though nothing reads
# it automatically anymore.

npx lint-staged # fast, staged-only: eslint --fix + tsc-files
yarn typecheck # full project tsc --noEmit — the real check