#!/usr/bin/env python3
"""
scripts/cross-cutting/checklist_interpreter.py

Walks rules sorted by priority; within each rule, walks checklist
steps top to bottom. Dispatches on each step's "type". Only two
outcomes ever produce a write proposal (on_missing / on_missing_key);
everything else is diagnostic-only, by construction — there is no
code path from "present but different" to a write.

This interpreter only ever produces a passive `plan` — it never writes
a file itself. Turning a plan into actual writes (policy file / dual-mode
wrapper / audit record) is deliberately not built yet — see
major-evolutions/1_CHECKLIST_INTERPRETER_HANDOFF.md's "Execution / gating
design" section.

Usage:
  python3 checklist_interpreter.py --target package.json --rules checklist-rules.yaml [--repo-dir .] [--flag NAME] [--json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from colors import BLUE, CYAN, GREEN, RED_ORANGE, YELLOW, RESET  # noqa: E402

PLACEHOLDER_RE = re.compile(r"^<([\w@/.-]+)\.version>$")


def resolve_placeholders(obj, versions: dict):
    """Recursively walks a parsed rules structure (dicts/lists/scalars)
    replacing any string that's ENTIRELY a "<package.version>" placeholder
    with that package's pinned version from a companion package-versions.yaml
    (see that file's own header for the full rationale). YAML itself has
    no variable/templating support — a placeholder string is just inert
    text to any YAML parser, PyYAML included; this function is what makes
    it behave like one, applied once, right after the rules file is
    parsed and before any rule is evaluated.

    Fails LOUD, not silently, on an unresolvable placeholder — same
    "never guess, surface it" discipline as every other ambiguous case in
    this file (tsconfig's unrecognized/absent shapes, etc.). A silently
    unresolved placeholder would otherwise become a literal, useless
    string like "<typescript.version>" fed straight into an install
    command — a confusing failure at the worst possible point (a human
    copy-pasting a broken command) instead of here, immediately, with a
    clear cause."""
    if isinstance(obj, dict):
        return {k: resolve_placeholders(v, versions) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_placeholders(v, versions) for v in obj]
    if isinstance(obj, str):
        m = PLACEHOLDER_RE.match(obj)
        if not m:
            return obj
        pkg = m.group(1)
        entry = versions.get(pkg)
        if not entry or "version" not in entry:
            raise KeyError(
                f"placeholder {obj!r} has no matching '{pkg}: version:' entry "
                f"in package-versions.yaml"
            )
        return entry["version"]
    return obj


def detect_package_manager(repo_dir: Path) -> str:
    """Ported unchanged from the retired merge_package_json.py — lockfile
    presence, never assumed. Needed so the staged install proposal below
    can render an actual copy-pasteable command, not just a package list."""
    if (repo_dir / "yarn.lock").exists():
        return "yarn"
    if (repo_dir / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (repo_dir / "package-lock.json").exists():
        return "npm"
    return "unknown"


def install_command(pm: str, packages: dict) -> str:
    """Ported unchanged from the retired merge_package_json.py."""
    args = [f'{name}@"{ver}"' for name, ver in packages.items()]
    if pm == "yarn":
        return "yarn add -D " + " ".join(args)
    if pm == "npm":
        return "npm install -D " + " ".join(args)
    if pm == "pnpm":
        return "pnpm add -D " + " ".join(args)
    return "# unknown package manager - no lockfile found, resolve manually"


def run_command(pm: str, script: str) -> str:
    """Renders a real, pm-correct invocation of a package.json script —
    NOT a bare word-swap of 'yarn' for the detected pm. npm requires
    `run` for a custom script (`npm typecheck` fails); yarn and pnpm
    both support the bare form directly."""
    if pm == "yarn":
        return f"yarn {script}"
    if pm == "npm":
        return f"npm run {script}"
    if pm == "pnpm":
        return f"pnpm {script}"
    return f"# unknown package manager - no lockfile found, resolve manually (script: {script})"


def read_json_file(path: Path) -> dict:
    """Best-effort JSON/JSONC reader — NOT a full JSONC parser. tsconfig.json
    commonly carries `//` and /* */ comments and trailing commas (tsc itself
    tolerates these; json.loads doesn't), so a real-world target file is
    likely to trip a plain json.loads. Tries strict JSON first; on failure,
    strips block comments, then line comments (guarded by a crude negative
    lookbehind so "http://" inside a string survives), then trailing commas,
    and retries. This can still mishandle a `//` that appears legitimately
    inside a string value elsewhere — known limitation, not silently
    pretended away. Returns {} if the file doesn't exist or never parses."""
    if not path.exists():
        return {}
    text = path.read_text()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    stripped = re.sub(r"(?<!:)//.*", "", stripped)
    stripped = re.sub(r",(\s*[}\]])", r"\1", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return {}


def get_report_outcome(plan, rule_id):
    """Looks up the `outcome` a given rule's diagnostic step already
    reported earlier in this SAME run — the generic mechanism for a later
    cluster to depend on an earlier cluster's finding without re-deriving
    it. Reuses plan['reports'] as-is (no new plan key), since every
    diagnostic step already appends there. Returns None if that rule
    hasn't run yet (wrong priority order — a real config error, not a
    normal outcome) or reported nothing. Written generically on purpose:
    tsconfig-environment-report and tsconfig-hygiene-remediation are the
    first callers, but lint-staged-hooks' still-informal dependency on
    linter-detection's outcome (currently a requires_present shortcut on
    the eslint dependency directly, not the diagnostic's own conclusion)
    could reuse this same lookup later instead of solving it twice."""
    for r in plan["reports"]:
        if r["rule"] == rule_id:
            return r["outcome"]
    return None


def eval_tsconfig_file_shape_report(step, repo_dir, plan, rule_id):
    """Bespoke 4-way filesystem classification, not a multi_presence_report
    variant — multi_presence_report's outcome logic is hardcoded around
    checking 2 named `staged[section]` dependency entries; this checks 2
    named FILES on disk instead, with its own distinct combinatorics
    (single/split/unrecognized/absent). Forcing it into multi_presence_report
    would mean overloading that step's contract rather than reusing it."""
    root = (Path(repo_dir) / "tsconfig.json").exists()
    app = (Path(repo_dir) / "tsconfig.app.json").exists()
    if not root and not app:
        outcome = "absent"
    elif app and not root:
        outcome = "unrecognized"
    elif app and root:
        outcome = "split"
    else:
        outcome = "single"
    message = step.get("report", {}).get(outcome, f"tsconfig shape: {outcome}")
    plan["reports"].append({"rule": rule_id, "outcome": outcome, "message": message})


def eval_tsconfig_environment_report(step, repo_dir, plan, rule_id):
    """Diagnostic-only, PERMANENTLY — no flag, now or ever, unlocks turning
    this into a remediation. Reports `fields` verbatim from whichever file
    tsconfig-file-shape-report identified as the compilerOptions holder;
    silently contributes nothing if that shape was absent/unrecognized,
    since the shape report already explained why, no need to duplicate
    the message here."""
    shape = get_report_outcome(plan, "tsconfig-file-shape-report")
    filename = step.get("target_file_by_shape", {}).get(shape)
    if filename is None:
        return
    data = read_json_file(Path(repo_dir) / filename)
    compiler_options = data.get("compilerOptions", {})
    values = {f: compiler_options.get(f, "not set") for f in step["fields"]}
    summary = ", ".join(f"{k}={v!r}" for k, v in values.items())
    plan["reports"].append({
        "rule": rule_id,
        "outcome": shape,
        "message": f"{filename} ({shape} shape) — {summary}",
    })


def eval_install_if_absent_all(step, staged, plan, repo_dir="."):
    """Only remediates if EVERY listed {section,name} pair is absent.
    Used for 'bring a neglected project to baseline' rules where a
    single dependency_presence check isn't enough — e.g. don't install
    eslint if oxlint is already the project's chosen linter.

    create_files (if present under on_all_absent) share this SAME gate:
    a config file for the thing being installed should only be proposed
    when the install itself actually fires, not on every run of the
    rule regardless of outcome. This is deliberate — a separate,
    ungated create_file step would create eslint.config.js even when
    oxlint is already present and the install correctly no-ops."""
    all_absent = all(c["name"] not in staged[c["section"]] for c in step["checks"])
    if not all_absent:
        return
    on = step.get("on_all_absent", {})
    for sec, pkgs in on.get("install", {}).items():
        for n, v in pkgs.items():
            if n not in staged[sec]:
                plan["install"][n] = v
                staged[sec][n] = v
    for k, v in on.get("add_scripts", {}).items():
        plan["add_scripts"].setdefault(k, v)
    for f in on.get("create_files", []):
        exists = (Path(repo_dir) / f["target"]).exists()
        plan["files"].append({
            "target": f["target"],
            "status": "skip" if exists else f"create from template: {f['template']}",
        })


def eval_dependency_presence(step, staged, plan):
    section, name = step["section"], step["name"]
    if name in staged[section]:
        plan["confirmed"].append(f"{section}.{name} already present")
        return
    for sec, pkgs in step.get("on_missing", {}).get("install", {}).items():
        for n, v in pkgs.items():
            if n not in staged[sec]:
                plan["install"][n] = v
                staged[sec][n] = v   # feeds forward to later steps/rules


def eval_script_value(step, target, plan):
    key, expected = step["key"], step["expected"]
    current = target.get("scripts", {}).get(key)
    if current is None:
        plan["add_scripts"][key] = expected
    elif current != expected:
        plan["conflicts"].append({"scripts": key, "on_disk": current, "expected": expected})
    else:
        plan["confirmed"].append(f"scripts.{key} already matches")


def eval_object_key_value(step, target, plan, repo_dir="."):
    """`target` is package.json by default (unchanged behavior — every
    existing caller before tsconfig-hygiene-remediation relies on this).
    A step carrying `target_file_by_shape` (a {shape: filename} map)
    points this at a DIFFERENT on-disk JSON file instead — the file whose
    name depends on tsconfig-file-shape-report's outcome (looked up via
    get_report_outcome), resolved fresh at eval time since the YAML can't
    statically know which filename applies. No entry for the current
    shape (absent/unrecognized, or shape report hasn't run) -> silent
    no-op, same reasoning as tsconfig-environment-report: nothing safe to
    check, and the shape report already explained why."""
    parent, subkey, expected = step["parent_key"], step["subkey"], step["expected"]
    if "target_file_by_shape" in step:
        shape = get_report_outcome(plan, "tsconfig-file-shape-report")
        filename = step["target_file_by_shape"].get(shape)
        if filename is None:
            return
        file_target = read_json_file(Path(repo_dir) / filename)
        # Label carries the filename — plan["add_object_keys"]/conflicts have
        # no separate "which file" field, and every existing caller of this
        # step implicitly means package.json, so an unlabeled "compilerOptions"
        # key here would leave a human guessing which of tsconfig.json /
        # tsconfig.app.json to actually edit.
        label = f"{filename}:{parent}"
    else:
        file_target = target
        label = parent
    current = file_target.get(parent, {}).get(subkey)
    if current is None:
        plan["add_object_keys"].setdefault(label, {})[subkey] = expected
    elif current != expected:
        plan["conflicts"].append({label: subkey, "on_disk": current, "expected": expected})
    else:
        plan["confirmed"].append(f"{label}.{subkey} already matches")


def eval_file_content_present(step, repo_dir, plan):
    """Checks a real on-disk file for a distinctive marker substring —
    not a full byte-for-byte diff against `template` (the interpreter
    never reads template files, same as create_file; a human copies the
    exact content when applying). Missing entirely (file doesn't exist,
    e.g. husky-setup's proposal from an earlier cluster hasn't actually
    been applied yet) and present-without-the-marker both propose the
    same 'append' action — this is an ensure-content-exists check, not a
    replace check; it never proposes overwriting what's already there.

    Two ways to specify the marker:
    - `marker`: a literal, pm-agnostic substring (e.g. "npx lint-staged" —
      npx works the same regardless of package manager, no rendering needed).
    - `script`: a package.json script name — rendered through run_command()
      into the pm-correct invocation (e.g. "yarn typecheck" / "npm run
      typecheck" / "pnpm typecheck") using plan['package_manager'], same
      detected-pm this file already uses for install_command(). Use this
      when the line to append actually invokes the package manager, not
      a pm-agnostic binary like npx."""
    target = Path(repo_dir) / step["target"]
    current = target.read_text() if target.exists() else ""
    if "script" in step:
        marker = run_command(plan["package_manager"], step["script"])
        append_status = f"append {marker!r} (see {step['template']} for full context/comments)"
    else:
        marker = step["marker"]
        append_status = f"append content from template: {step['template']}"
    if marker in current:
        plan["confirmed"].append(f"{step['target']} already contains {marker!r}")
    else:
        plan["files"].append({"target": step["target"], "status": append_status})


def eval_ensure_block_in_gitignore(step, repo_dir, plan):
    """Content-based, NOT position-based: checks whether every MEANINGFUL
    line of `block` (patterns — comments and blank lines don't count) is
    already present ANYWHERE in .gitignore, in any order, possibly
    interspersed with unrelated content. A human's hand-added entry,
    differently formatted or positioned, still causes a correct no-op —
    this deliberately does not require exact block-shape or contiguous
    placement, only that every pattern line already exists somewhere.

    If ANY meaningful line is missing, proposes appending the ENTIRE
    block verbatim (comment header included) as one atomic unit — never
    a partial append of just the missing lines, and never touching or
    reordering whatever's already in the file. `block` is inline YAML
    content (no `template:` file reference the way create_file/
    file_content_present use — gitignore blocks are short enough to
    carry directly in the rules file, per major-evolutions/4_GITIGNORE-HANDOFF.md), so the
    full text is included in the staged status itself for the human to
    copy, not just a path pointing at it.

    Deliberately a SEPARATE step type from any future pre-commit
    line-append mechanism, despite the surface-level similarity — see
    major-evolutions/4_GITIGNORE-HANDOFF.md and major-evolutions/5_PRECOMMIT-HANDOFF.md for why: gitignore
    blocks are order-independent and multi-line; pre-commit lines are
    order-dependent single invocations in an executed shell script.
    Don't generalize the two into one interface."""
    gitignore_path = Path(repo_dir) / ".gitignore"
    current_lines = {
        line.strip() for line in gitignore_path.read_text().splitlines()
    } if gitignore_path.exists() else set()

    block = step["block"]
    meaningful = [
        line.strip() for line in block.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    missing = [line for line in meaningful if line not in current_lines]

    if not missing:
        plan["confirmed"].append(f".gitignore already contains: {', '.join(meaningful)}")
        return

    indented_block = "\n".join(f"      {line}" for line in block.rstrip("\n").splitlines())
    plan["files"].append({
        "target": ".gitignore",
        "status": f"append block verbatim, as one unit (missing: {', '.join(missing)}):\n{indented_block}",
    })


def eval_ensure_line_in_precommit(step, plan):
    """Deliberately does almost nothing by itself — see major-evolutions/5_PRECOMMIT-HANDOFF.md
    for why this needs a two-phase design, unlike every other step type
    in this file. This function ONLY stages the proposed {command, order}
    pair into plan['precommit_lines'] during normal per-rule evaluation.
    It does NOT read .husky/pre-commit or decide presence/conflicts here,
    because that decision needs the FULL set of managed lines across
    every cluster that contributes one — not knowable until every rule
    has been evaluated, since clusters fire in priority order but the
    correct FILE order is independent of (often the reverse of) that
    evaluation order. See reconcile_precommit_lines(), called once after
    the main per-rule loop in run(), for the actual all-or-nothing gate.

    Two ways to specify the line, same convention as file_content_present:
    - `command`: a literal, pm-agnostic string (e.g. "npx lint-staged").
    - `script`: a package.json script name, rendered through run_command()
      into the pm-correct invocation — same mechanism file_content_present
      already uses, reused here rather than losing that fix by going back
      to a hardcoded string."""
    if "script" in step:
        command = run_command(plan["package_manager"], step["script"])
    else:
        command = step["command"]
    plan["precommit_lines"].append({"command": command, "order": step["order"]})


def reconcile_precommit_lines(repo_dir, plan):
    """All-or-nothing gate, mirroring install_if_absent_all's "all absent"
    conservatism — applied here to file LINES instead of dependencies:
    - File doesn't exist, or exists with NONE of the managed commands
      present -> propose the full, correctly-ordered (sorted by `order`)
      block as ONE atomic staged entry. A missing file is treated
      identically to "none present," not a special case — husky-setup's
      own create_file proposal for that same file may itself still be
      unapplied at this point (the interpreter never writes anything),
      and this reconciliation reads real on-disk state regardless of
      cluster evaluation order, so it doesn't need to coordinate with
      husky-setup's own timing.
    - ALL managed commands already present -> confirmed, no-op. Doesn't
      re-verify their relative order in the existing file — same
      presence-not-position spirit as ensure_block_in_gitignore.
    - SOME but not all present (e.g. a human hand-added one line before
      any cluster ran) -> never guess where to splice the missing ones
      into a file a human may have already edited. Surface as a
      conflicts entry and stop — same "recognize the edge of your own
      competence" principle as tsconfig-file-shape-report's
      unrecognized/absent outcomes.

    Removes plan['precommit_lines'] from the final plan before returning
    — it's internal staging only, same as the `staged` dict never
    leaking into the final plan structure either."""
    lines = plan.pop("precommit_lines")
    if not lines:
        return
    lines_sorted = sorted(lines, key=lambda entry: entry["order"])
    commands = [entry["command"] for entry in lines_sorted]

    precommit_path = Path(repo_dir) / ".husky" / "pre-commit"
    current = precommit_path.read_text() if precommit_path.exists() else ""
    present = [cmd for cmd in commands if cmd in current]

    if not present:
        indented = "\n".join(f"      {c}" for c in commands)
        plan["files"].append({
            "target": ".husky/pre-commit",
            "status": f"append block verbatim, in this exact order (never re-derive order per-cluster):\n{indented}",
        })
    elif len(present) == len(commands):
        plan["confirmed"].append(f".husky/pre-commit already contains all managed lines: {', '.join(commands)}")
    else:
        missing = [c for c in commands if c not in present]
        plan["conflicts"].append({
            ".husky/pre-commit": "managed-line set incomplete or hand-edited",
            "present": present,
            "missing": missing,
            "resolution": "resolve manually — never auto-spliced into existing content",
        })


def eval_multi_presence_report(step, staged, plan, rule_id):
    results = {label: spec["name"] in staged[spec["section"]] for label, spec in step["checks"].items()}
    true_labels = [l for l, v in results.items() if v]

    def short(label):
        return label[:-8] if label.endswith("_present") else label

    if len(true_labels) == 0:
        outcome = "both_absent" if len(results) == 2 else "none_present"
    elif len(true_labels) == len(results):
        outcome = "both_present" if len(results) == 2 else "all_present"
    elif len(true_labels) == 1:
        outcome = f"{short(true_labels[0])}_only"
    else:
        outcome = "mixed"

    message = step.get("report", {}).get(outcome, f"unrecognized combination: {results}")
    plan["reports"].append({"rule": rule_id, "outcome": outcome, "message": message})


def run(target_path, rules_path, repo_dir=".", flags=None):
    flags = set(flags or [])
    target = json.loads(Path(target_path).read_text())
    rules = yaml.safe_load(Path(rules_path).read_text())

    # Companion versions file: same directory as the rules file, filename
    # convention (package-versions.yaml), no CLI flag needed. Optional —
    # a rules file with no "<pkg.version>" placeholders at all works fine
    # with no companion file present.
    versions_path = Path(rules_path).parent / "package-versions.yaml"
    versions = yaml.safe_load(versions_path.read_text()) if versions_path.exists() else {}
    rules = resolve_placeholders(rules, versions)

    staged = {
        "dependencies": dict(target.get("dependencies", {})),
        "devDependencies": dict(target.get("devDependencies", {})),
    }
    plan = {"install": {}, "add_scripts": {}, "add_object_keys": {},
            "conflicts": [], "reports": [], "files": [], "skipped_rules": [],
            "confirmed": [], "package_manager": detect_package_manager(Path(repo_dir)),
            "precommit_lines": []}

    for rule in sorted(rules, key=lambda r: r["priority"]):
        needed_flag = rule.get("requires_flag")
        if needed_flag and needed_flag not in flags:
            plan["skipped_rules"].append({
                "rule": rule["id"],
                "reason": f"requires_flag '{needed_flag}' not passed — pass --flag {needed_flag} to run this rule",
            })
            continue
        needed_presence = rule.get("requires_present")
        if needed_presence:
            sec, name = needed_presence["section"], needed_presence["name"]
            if name not in staged[sec]:
                plan["skipped_rules"].append({
                    "rule": rule["id"],
                    "reason": f"requires_present {sec}.{name}, not found on disk — this cluster only "
                              f"fires once that dependency is present (e.g. via linter-detection "
                              f"reporting it, or a remediation cluster installing it first)",
                })
                continue
        for step in rule.get("checklist", []):
            t = step["type"]
            if t == "dependency_presence":
                eval_dependency_presence(step, staged, plan)
            elif t == "script_value":
                eval_script_value(step, target, plan)
            elif t == "object_key_value":
                eval_object_key_value(step, target, plan, repo_dir)
            elif t == "multi_presence_report":
                eval_multi_presence_report(step, staged, plan, rule["id"])
            elif t == "install_if_absent_all":
                eval_install_if_absent_all(step, staged, plan, repo_dir)
            elif t == "create_file":
                exists = (Path(repo_dir) / step["target"]).exists()
                plan["files"].append({
                    "target": step["target"],
                    "status": "skip" if exists else f"create from template: {step['template']}",
                })
            elif t == "file_content_present":
                eval_file_content_present(step, repo_dir, plan)
            elif t == "tsconfig_file_shape_report":
                eval_tsconfig_file_shape_report(step, repo_dir, plan, rule["id"])
            elif t == "tsconfig_environment_report":
                eval_tsconfig_environment_report(step, repo_dir, plan, rule["id"])
            elif t == "ensure_block_in_gitignore":
                eval_ensure_block_in_gitignore(step, repo_dir, plan)
            elif t == "ensure_line_in_precommit":
                eval_ensure_line_in_precommit(step, plan)
            else:
                plan.setdefault("unknown_step_types", []).append(t)

    reconcile_precommit_lines(repo_dir, plan)
    return plan


def print_report(plan) -> None:
    """Colored, human-readable rendering of a plan. Convention (shared
    with scripts/cross-cutting/colors.py usage elsewhere in this repo):
    BLUE = staged (proposed, not yet applied — this interpreter never
    writes), GREEN = done (already satisfied, nothing to do), RED_ORANGE
    = needs a human decision (conflicts, or a rule that's currently
    skipped pending a --flag). CYAN stays reserved for section headers,
    same neutral role it had in the retired merge_package_json.py.
    YELLOW carries pure diagnostic reports (no action implied either way)."""
    print(f"{CYAN}==> checklist plan{RESET}\n")

    if plan["confirmed"]:
        print(f"{CYAN}-- already satisfied --{RESET}")
        for line in plan["confirmed"]:
            print(f"  {GREEN}[done]{RESET} {line}")
        print()

    staged_lines = []
    for name, ver in plan["install"].items():
        staged_lines.append(f"install {name}@{ver}")
    for key, val in plan["add_scripts"].items():
        staged_lines.append(f"add scripts.{key} = {val!r}")
    for parent, subkeys in plan["add_object_keys"].items():
        for subkey, val in subkeys.items():
            staged_lines.append(f"add {parent}.{subkey} = {val!r}")
    for f in plan["files"]:
        if f["status"] != "skip":
            staged_lines.append(f"{f['target']}: {f['status']}")
        else:
            plan["confirmed"].append(f"{f['target']} already exists")

    if staged_lines:
        print(f"{CYAN}-- staged (not applied — plan only) --{RESET}")
        for line in staged_lines:
            print(f"  {BLUE}[staged]{RESET} {line}")
        print()

    if plan["install"]:
        print(f"{CYAN}-- proposed install ({plan['package_manager']}) --{RESET}")
        print(f"  {BLUE}{install_command(plan['package_manager'], plan['install'])}{RESET}")
        print()

    file_skips = [f for f in plan["files"] if f["status"] == "skip"]
    if file_skips:
        print(f"{CYAN}-- files already present --{RESET}")
        for f in file_skips:
            print(f"  {GREEN}[done]{RESET} {f['target']}")
        print()

    if plan["conflicts"]:
        print(f"{CYAN}-- conflicts (never auto-resolved) --{RESET}")
        for c in plan["conflicts"]:
            print(f"  {RED_ORANGE}[MISSING decision]{RESET} {c}")
        print()

    if plan["reports"]:
        print(f"{CYAN}-- diagnostics --{RESET}")
        for r in plan["reports"]:
            print(f"  {YELLOW}[{r['rule']}]{RESET} {r['message']}")
        print()

    if plan["skipped_rules"]:
        print(f"{CYAN}-- skipped rules (opt-in, not run) --{RESET}")
        for s in plan["skipped_rules"]:
            print(f"  {RED_ORANGE}[skipped]{RESET} {s['rule']}: {s['reason']}")
        print()

    if not staged_lines and not plan["conflicts"]:
        print(f"{GREEN}Nothing to do — all checked concerns already satisfied.{RESET}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--repo-dir", default=".")
    ap.add_argument("--flag", action="append", default=[],
                     help="Enable an opt-in rule gated by requires_flag. "
                          "Repeatable. E.g. --flag augment_legacy_linting")
    ap.add_argument("--json", action="store_true",
                     help="Print the raw plan as JSON instead of the colored report "
                          "(for programmatic consumption — e.g. a future execution/gating layer).")
    args = ap.parse_args()
    result = run(args.target, args.rules, args.repo_dir, args.flag)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)
