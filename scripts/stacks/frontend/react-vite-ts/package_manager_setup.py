#!/usr/bin/env python3
"""
scripts/stacks/frontend/react-vite-ts/package_manager_setup.py

Dedicated script for one concern only: given a chosen package manager
(npm / yarn / pnpm) and a freshly-scaffolded, not-yet-installed project,
make that package manager actually work and produce its own lockfile.
Invoked by ../react-vite-ts.py's bootstrap step (Step 1, the
create-vite branch) via subprocess — same pattern react-vite-ts.py
already uses for checklist_interpreter.py, not a plain function import.

Deliberately NOT a general "package manager abstraction" — this only
knows how to GET a package manager ready to run and RUN one install.
Rendering pm-correct command strings for the checklist plan (install
commands, script invocations) stays entirely inside
scripts/cross-cutting/checklist_interpreter.py's detect_package_manager
/ install_command / run_command trio, which reads the lockfile this
script produces — no overlap, no duplicated logic between the two.

Why this exists as its own script, not inline in react-vite-ts.py:
corepack activation is genuinely a distinct concern with its own
failure modes (missing binary, permission-denied shim writes, a bad
version pin) that deserves its own clear pass/fail boundary and its
own colored status output, not buried inside the stack dispatcher.

Location note, read before "helping" by moving this: as of 2026-09-08
this is the ONLY Node-based stack in the repo, so this script is
deliberately nested UNDER scripts/stacks/frontend/react-vite-ts/ rather
than scripts/cross-cutting/ — same "don't extract before a second
consumer forces it" discipline as everywhere else in this repo (see
CONFIG_OWNERSHIP_MATRIX.md's own "when to revisit" section). The day a
second Node-based stack (e.g. a nodejs-nestjs backend) needs the exact
same npm/yarn/pnpm setup logic, promote this file to
scripts/cross-cutting/package_manager_setup.py as a straight file move
— nothing about its internals is react-vite-ts-specific, it takes a
bare repo_dir and a pm string. See
major-evolutions/6_PACKAGE-MANAGER-CHOICE-HANDOFF.md for the full
corepack-vs-npm design record and the enable+prepare atomic-gate
diagram this implements.

Usage:
  python3 package_manager_setup.py --pm {npm,yarn,pnpm} [--repo-dir .]
"""
import argparse
import subprocess
import sys
from pathlib import Path

CROSS_CUTTING_DIR = Path(__file__).resolve().parent.parent.parent.parent / "cross-cutting"
sys.path.insert(0, str(CROSS_CUTTING_DIR))
from colors import BLUE, GREEN, RED_ORANGE, RESET  # noqa: E402

ALLOWED_PMS = ("npm", "yarn", "pnpm")
# Seed of a future cross-stack "which PM is valid for which stack" dict
# (discussed 2026-09-08, not built yet — see the handoff note above).
# For now this is simply every PM this ONE stack's ecosystem (Node)
# supports; a python/dotnet stack would need its own separate list, this
# one should never grow pip/conda/nuget entries bolted on.

# corepack's own version-pin syntax for each non-npm manager. "stable"
# for yarn (not a bare "latest") mirrors corepack's own documented
# convention — see major-evolutions/6_PACKAGE-MANAGER-CHOICE-HANDOFF.md.
COREPACK_VERSION_SPEC = {
    "yarn": "yarn@stable",
    "pnpm": "pnpm@latest",
}


def _run(cmd: list[str], repo_dir: Path) -> "subprocess.CompletedProcess | None":
    """subprocess.run wrapper that treats 'binary not found at all' the
    same as 'binary found but exited non-zero' — both are corepack-
    unavailable, from this script's point of view. Returns None (not a
    CompletedProcess with some sentinel code) on FileNotFoundError so
    the caller's `if result is None or result.returncode != 0` check
    stays a single, honest condition instead of two different flavors
    of failure to remember."""
    try:
        return subprocess.run(cmd, cwd=repo_dir)
    except FileNotFoundError:
        return None


def npm_install(repo_dir: Path) -> None:
    subprocess.run(["npm", "install"], cwd=repo_dir, check=True)


def setup_and_install(pm: str, repo_dir: Path) -> None:
    """The whole corepack-vs-npm decision in one place. npm needs no
    corepack step at all — it's the package manager Node already ships
    with, this is just today's unconditional subprocess.run(["npm",
    "install"]) moved here so BOTH branches (npm and non-npm) live in
    one script instead of splitting npm-handling back into
    react-vite-ts.py while yarn/pnpm handling lives here.

    For yarn/pnpm: `corepack enable` and `corepack prepare <pm>@<spec>
    --activate` are treated as ONE atomic gate — both must exit 0
    before this is considered "corepack worked". Checking `enable`
    alone is not enough: enable only wires up the interception shim,
    it does not fetch or pin a version, so a failure in the actual
    fetch (prepare) would otherwise surface late, deep inside the
    install call, instead of here with a clear cause. Single attempt,
    no retry loop — any failure in either step falls through to the
    same npm fallback, loudly, not silently."""
    if pm == "npm":
        npm_install(repo_dir)
        return

    if pm not in COREPACK_VERSION_SPEC:
        raise ValueError(f"unsupported package manager: {pm!r} (allowed: {ALLOWED_PMS})")

    enable = _run(["corepack", "enable"], repo_dir)
    prepare = None
    if enable is not None and enable.returncode == 0:
        prepare = _run(
            ["corepack", "prepare", COREPACK_VERSION_SPEC[pm], "--activate"],
            repo_dir,
        )

    corepack_ready = enable is not None and enable.returncode == 0 and prepare is not None and prepare.returncode == 0

    if not corepack_ready:
        reason = (
            "corepack not found on PATH"
            if enable is None
            else "corepack enable failed"
            if enable.returncode != 0
            else "corepack unavailable (missing binary) during prepare"
            if prepare is None
            else f"corepack prepare {COREPACK_VERSION_SPEC[pm]} --activate failed"
        )
        print(f"{RED_ORANGE}WARNING:{RESET} {reason} — falling back to npm install "
              f"(package.json will be installed via npm, not {pm}; "
              f"no {pm}.lock will be produced)")
        npm_install(repo_dir)
        return

    print(f"{GREEN}corepack ready{RESET} ({COREPACK_VERSION_SPEC[pm]}, activated)")

    touched_yarn_lock = False
    if pm == "yarn":
        # Yarn Berry walks UP from repo_dir looking for the nearest
        # enclosing "project" (any ancestor package.json/workspace
        # config) and refuses to install in a directory it doesn't
        # recognize as its own project root, UNLESS a yarn.lock already
        # pins that exact directory as the root. Any ancestor directory
        # with its own package.json is enough to trigger this — e.g. a
        # hand-set-up "mock repo" folder holding several trial scaffolds
        # as siblings/parents. Reproduced directly (2026-09-08, see
        # major-evolutions/6_PACKAGE-MANAGER-CHOICE-HANDOFF.md) rather
        # than assumed. Pre-creating an empty yarn.lock pins repo_dir as
        # its own root before yarn ever looks upward, exactly what
        # yarn's own error message recommends. No-op when repo_dir
        # already is the nearest project — yarn install still populates
        # it normally either way.
        yarn_lock_path = repo_dir / "yarn.lock"
        if not yarn_lock_path.exists():
            yarn_lock_path.touch()
            touched_yarn_lock = True

    # Corepack activating successfully does NOT guarantee the actual
    # `<pm> install` call will succeed — found live: a corrupted local
    # corepack pnpm cache passed `prepare` cleanly but then crashed on
    # the real `pnpm install` invocation with a raw MODULE_NOT_FOUND.
    # Same fallback treatment as the enable/prepare gate above: any
    # failure here falls through to npm, loudly, never a raw traceback.
    install_result = _run([pm, "install"], repo_dir)
    if install_result is None or install_result.returncode != 0:
        if touched_yarn_lock:
            # Don't leave a stray empty yarn.lock behind pointing
            # detect_package_manager() at yarn when npm is what's
            # actually about to be used.
            yarn_lock_path.unlink(missing_ok=True)
        print(f"{RED_ORANGE}WARNING:{RESET} {pm} install failed after corepack activation "
              f"succeeded — falling back to npm install (package.json will be installed "
              f"via npm, not {pm}; no {pm} lockfile will be produced)")
        npm_install(repo_dir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pm", required=True, choices=ALLOWED_PMS)
    ap.add_argument("--repo-dir", default=".")
    args = ap.parse_args()

    repo_dir = Path(args.repo_dir)
    print(f"{BLUE}INFO:{RESET} setting up package manager: {args.pm}")
    setup_and_install(args.pm, repo_dir)


if __name__ == "__main__":
    main()
