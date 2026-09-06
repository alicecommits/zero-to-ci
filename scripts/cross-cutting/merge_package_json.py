#!/usr/bin/env python3
"""
scripts/merge-package-json.py

Deterministic augment-mode diff for package.json. No judgment calls:
- missing dependency  -> proposed install, at template's pinned version
- present dependency  -> untouched, regardless of version skew
- missing config key  -> proposed merge, verbatim from template
- present config key, same value      -> skip
- present config key, different value -> CONFLICT, flagged, never overwritten

Usage:
  python merge_package_json.py --target <package.json> --template <snippet.json> [--apply]

Without --apply: prints the gap report only (dry run).
With --apply:    writes merged keys into target's package.json IN PLACE
                  for non-conflicting entries only. Conflicts are always
                  left for manual resolution regardless of --apply.
"""
import argparse
import json
import subprocess
from pathlib import Path

YELLOW = "\033[33m"
RED_ORANGE = "\033[38;5;202m"
GREEN = "\033[32m"
BLUE = "\033[38;5;39m"
RESET = "\033[0m"

DEP_FIELDS = ["dependencies", "devDependencies"]
CONFIG_OBJECT_FIELDS = ["scripts", "lint-staged"]

# Canonical top-level key order this repo writes brand-new keys into,
# matching community convention (sort-package-json): tooling/config
# objects before dependency blocks. Only used to POSITION a key that
# didn't exist in target at all before this merge — existing keys keep
# whatever order they already had, never reordered.
SECTION_ORDER = ["scripts", "lint-staged", "dependencies", "devDependencies"]


def detect_package_manager(repo_dir: Path) -> str:
    if (repo_dir / "yarn.lock").exists():
        return "yarn"
    if (repo_dir / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (repo_dir / "package-lock.json").exists():
        return "npm"
    return "unknown"


def diff_deps(target: dict, template: dict, field: str):
    t_deps = target.get(field, {})
    tpl_deps = template.get(field, {})
    missing = {name: ver for name, ver in tpl_deps.items() if name not in t_deps}
    present = {name: tpl_deps[name] for name in tpl_deps if name in t_deps}
    return missing, present


def diff_config_object(target: dict, template: dict, field: str):
    t_obj = target.get(field, {})
    tpl_obj = template.get(field, {})
    missing, same, conflicts = {}, {}, {}
    for key, tpl_val in tpl_obj.items():
        if key not in t_obj:
            missing[key] = tpl_val
        elif t_obj[key] == tpl_val:
            same[key] = tpl_val
        else:
            conflicts[key] = {"existing": t_obj[key], "template": tpl_val}
    return missing, same, conflicts


def reorder_new_keys(d: dict, new_keys: list, order: list) -> dict:
    """Rebuild `d` so each brand-new key in `new_keys` lands at its
    canonical position from `order`, instead of Python dict's default
    append-at-end. Keys that existed in `d` before the merge keep
    their original relative order untouched."""
    keys = [k for k in d if k not in new_keys]
    for key in new_keys:
        idx = order.index(key)
        insert_at = len(keys)
        for i, existing in enumerate(keys):
            if existing in order and order.index(existing) > idx:
                insert_at = i
                break
        keys.insert(insert_at, key)
    return {k: d[k] for k in keys}


def install_command(pm: str, packages: dict) -> str:
    args = [f'{name}@"{ver}"' for name, ver in packages.items()]
    if pm == "yarn":
        return "yarn add -D " + " ".join(args)
    if pm == "npm":
        return "npm install -D " + " ".join(args)
    if pm == "pnpm":
        return "pnpm add -D " + " ".join(args)
    return "# unknown package manager - no lockfile found, resolve manually"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    target_path = Path(args.target)
    target = json.loads(target_path.read_text())
    template = json.loads(Path(args.template).read_text())
    pm = detect_package_manager(target_path.parent)

    print(f"==> package manager detected: {pm}\n")

    # --- dependencies ---
    all_missing_deps = {}
    for field in DEP_FIELDS:
        missing, present = diff_deps(target, template, field)
        if not missing and not present:
            continue
        print(f"-- {field} --")
        for name, ver in present.items():
            t_ver = target[field][name]
            if t_ver == ver:
                print(f"  [present, untouched, same version as in template] {name}@{t_ver}")
            else:
                print(f"  [present, untouched, {YELLOW}⚠ WARN version drift from template{RESET} ] {name}@{t_ver}  (template wants {ver}, not enforced)")
        for name, ver in missing.items():
            print(f"  {RED_ORANGE}[MISSING]{RESET}            {name}@{ver}")
        all_missing_deps.update(missing)
        print()

    if all_missing_deps:
        print("-- proposed install --")
        print(" ", install_command(pm, all_missing_deps))
        print()

    # --- config objects (scripts, lint-staged, ...) ---
    merged_target = json.loads(json.dumps(target))  # deep copy
    new_top_level_keys = []  # fields absent from target entirely, need positioning
    any_conflict = False
    for field in CONFIG_OBJECT_FIELDS:
        missing, same, conflicts = diff_config_object(target, template, field)
        if not missing and not same and not conflicts:
            continue
        print(f"-- {field} --")
        for key in same:
            print(f"  [present, matches]   {key!r}")
        for key, val in missing.items():
            print(f"  {RED_ORANGE}[MISSING]{RESET}            {key!r}: {val!r}")
        for key, diff in conflicts.items():
            any_conflict = True
            print(f"  [CONFLICT]           {key!r}")
            print(f"                       existing: {diff['existing']!r}")
            print(f"                       template: {diff['template']!r}")
            print(f"                       -> not touched, resolve manually")
        print()

        if missing:
            if field not in merged_target:
                new_top_level_keys.append(field)
            merged_target.setdefault(field, {})
            merged_target[field].update(missing)

    if new_top_level_keys:
        merged_target = reorder_new_keys(merged_target, new_top_level_keys, SECTION_ORDER)

    if args.apply:
        if all_missing_deps:
            print("!! --apply set, but dependency installation is a real package-manager")
            print("   call, not a file edit — run the printed install command yourself,")
            print("   then re-run this script to merge the resulting config keys.")
            print()
        target_path.write_text(json.dumps(merged_target, indent=2) + "\n")
        print(f"{GREEN}==> wrote merged config keys (deps excluded) to {target_path}{RESET}")
    else:
        print(f"{BLUE}==> dry run only. Re-run with --apply to write non-conflicting config keys.{RESET}")

    if any_conflict:
        print("\n!! one or more CONFLICTs found — these are never auto-resolved.")


if __name__ == "__main__":
    main()
