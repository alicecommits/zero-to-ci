# devops/agent-lint-handling

**Status: sketch only. Depends on the agent-run stage (`implement.yml`
doesn't exist yet — that's when `--agents` first generates the file
this skill edits). Written now, while the ESLint decision is fresh,
so it's not re-derived from scratch later.**

## When

Editing the `claude` invocation step inside `implement.yml`
(the prompt section spin_up.py writes), specifically the part that
tells the agent what to do when ESLint reports errors/warnings on
code it just wrote or touched.

## The flag this eventually becomes

```
scripts/spin_up.py
  --agents on    add LINT_FIX_MODE: supervised as default
                 to implement.yml.template prompt section
                 (supervised = agent lists proposed fixes as PR
                  comments only, never applies them without approval)
```

`LINT_FIX_MODE` values:

```
supervised   agent runs eslint, reports errors/warnings + proposed
             fixes + reasoning as PR comments. Never edits files
             for lint reasons on its own.
autonomous   agent applies eslint --fix and any other fixes it's
             confident about, then reports what it changed and why
             in the PR description. No approval gate.
```

Default is `supervised`. That's the one non-obvious call worth
recording now: an agent silently rewriting lint fixes it just
introduced is a smaller blast radius than an agent silently
rewriting *logic* — but "smaller" isn't "zero," and the whole
point of the agent-run stage is watching what agents actually do
before trusting them further. Start conservative, loosen once
agent-run.sh has a track record.

## Judgment needed (why this isn't a script)

- How to phrase the report requirement so the agent produces a
  structured account (rule triggered, file/line, fix applied or
  proposed, one-line reasoning) instead of a vague "fixed some
  lint issues" summary. Reporting quality here is entirely a
  function of how the prompt frames the ask.
- Where the line sits between "eslint --fix would obviously do
  this" (autonomous-safe even in supervised mode, e.g. import
  ordering) and "this needs a human's eyes" (a `react-hooks/
  exhaustive-deps` violation that could hide a real bug) — if
  `supervised` ever gets a partial-autonomy carve-out, deciding
  which rules qualify is judgment, not a deterministic list you
  derive once.
- How the PR-comment format should look for *this* project's
  review style, once the adversarial-review stage exists —
  they'll likely share a comment-formatting convention and that
  convention isn't dictated by either skill alone.

## Not judgment (goes in a script instead)

- The eslint invocation itself and JSON-report parsing.
  → `scripts/lint-report.sh` (below): deterministic, always run
  the same way regardless of LINT_FIX_MODE.
- Whether to add the `LINT_FIX_MODE` field to the workflow_dispatch
  inputs when `--agents on` — deterministic spin_up.py branch.
- The default value (`supervised`) — decided once, hardcoded.

## Companion script (deterministic — not written yet)

```
scripts/lint-report.sh
  (no flag)   run `eslint . --format json`, parse into a compact
              markdown table: rule | file:line | message | fixable?
              Same script whether LINT_FIX_MODE is supervised or
              autonomous — only what implement.yml tells the agent
              to *do* with the report differs.
```

## Open question to resolve when this stage actually starts

Does the report/proposed-fix output live only in the PR body, or
does it also get written to a GH issue, per the original note
("in the future, in GH issues")? If GH issues, that's a second
deterministic script (`gh issue create` call from inside
implement.yml), not a change to this skill's judgment scope.
