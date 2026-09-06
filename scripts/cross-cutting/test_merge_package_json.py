#!/usr/bin/env python3
"""
scripts/cross-cutting/test_merge_package_json.py

Covers merge_package_json.py's core guarantees:
- dependency version drift: reported, never written, dry run or --apply
  (script has no "enforce template version" mode — drift is always kept
  as-is; these tests prove that absence, not a toggle)
- dependency version identical: reported without a drift warning
- brand-new top-level key (e.g. lint-staged) inserted per SECTION_ORDER,
  not appended after whatever key happened to be last

Run: python3 -m unittest discover -s scripts/cross-cutting -v
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import merge_package_json as mpj  # noqa: E402


def run_main(target_path: Path, template_path: Path, apply: bool = False) -> str:
    """Invoke merge_package_json.main() in-process, capturing stdout."""
    argv = ["merge_package_json.py", "--target", str(target_path), "--template", str(template_path)]
    if apply:
        argv.append("--apply")
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(buf):
        mpj.main()
    return buf.getvalue()


class MergePackageJsonTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo_dir = Path(self._tmpdir.name)
        self.target_path = self.repo_dir / "package.json"
        self.template_path = self.repo_dir / "template.json"

    def write(self, target: dict, template: dict) -> None:
        self.target_path.write_text(json.dumps(target, indent=2) + "\n")
        self.template_path.write_text(json.dumps(template, indent=2) + "\n")

    def test_version_drift_dry_run_reports_and_does_not_write(self):
        self.write(
            target={"dependencies": {"react": "^17.0.0"}},
            template={"dependencies": {"react": "^18.3.1"}},
        )
        before = self.target_path.read_bytes()

        output = run_main(self.target_path, self.template_path, apply=False)

        self.assertIn("WARN", output)
        self.assertIn("react@^17.0.0", output)
        self.assertIn("template wants ^18.3.1", output)
        self.assertIn("dry run only", output)
        self.assertEqual(self.target_path.read_bytes(), before, "dry run must never write")

    def test_version_drift_apply_keeps_original_not_template(self):
        # No "apply template version" mode exists — --apply only ever
        # writes scripts/lint-staged keys, deps are excluded outright.
        self.write(
            target={"dependencies": {"react": "^17.0.0"}},
            template={"dependencies": {"react": "^18.3.1"}},
        )

        run_main(self.target_path, self.template_path, apply=True)

        result = json.loads(self.target_path.read_text())
        self.assertEqual(result["dependencies"]["react"], "^17.0.0")

    def test_version_drift_never_flagged_as_conflict(self):
        # Drift is categorized as "present, untouched" (diff_deps path),
        # never routed through the CONFLICT machinery that scripts/
        # lint-staged use (diff_config_object path) — different
        # guarantee, different code path, must stay that way.
        self.write(
            target={"dependencies": {"react": "^17.0.0"}},
            template={"dependencies": {"react": "^18.3.1"}},
        )

        output = run_main(self.target_path, self.template_path, apply=False)

        self.assertNotIn("CONFLICT", output)
        self.assertIn("[present, untouched", output)

    def test_version_identical_no_drift_warning(self):
        self.write(
            target={"dependencies": {"react": "^18.3.1"}},
            template={"dependencies": {"react": "^18.3.1"}},
        )

        output = run_main(self.target_path, self.template_path, apply=False)

        self.assertNotIn("WARN", output)
        self.assertNotIn("template wants", output)
        self.assertIn("[present, untouched, same version as in template] react@^18.3.1", output)

    def test_missing_section_inserted_in_canonical_order(self):
        # Shape modeled on the real money-disk package.json: lint-staged
        # doesn't exist yet, packageManager is the last existing key.
        self.write(
            target={
                "name": "money-disk-ui",
                "private": True,
                "version": "0.1.0",
                "type": "module",
                "scripts": {"typecheck": "tsc --noEmit", "lint": "eslint .", "test": "vitest run", "prepare": "husky"},
                "dependencies": {"react": "^18.3.1"},
                "devDependencies": {"eslint": "^10.10.0"},
                "packageManager": "yarn@1.22.22",
            },
            template={
                "scripts": {"typecheck": "tsc --noEmit"},
                "lint-staged": {"*.{ts,tsx}": ["eslint --fix", "tsc-files --noEmit"]},
                "dependencies": {"react": "^18.3.1"},
                "devDependencies": {"eslint": "^10.10.0"},
            },
        )

        run_main(self.target_path, self.template_path, apply=True)

        keys = list(json.loads(self.target_path.read_text()).keys())
        self.assertEqual(keys.index("lint-staged"), keys.index("scripts") + 1)
        self.assertLess(keys.index("lint-staged"), keys.index("dependencies"))
        self.assertEqual(keys[-1], "packageManager")

    def test_two_missing_sections_inserted_relative_to_each_other(self):
        # MODE=new-like case (not built yet, per NOTES.md): target has
        # neither `scripts` nor `lint-staged` at all. reorder_new_keys
        # inserts one key at a time via keys.insert() — this proves the
        # two-key case still lands scripts before lint-staged, not just
        # the single-key case the previous test covers.
        self.write(
            target={
                "name": "fresh-repo",
                "dependencies": {"react": "^18.3.1"},
                "devDependencies": {"eslint": "^10.10.0"},
                "packageManager": "yarn@1.22.22",
            },
            template={
                "scripts": {"typecheck": "tsc --noEmit"},
                "lint-staged": {"*.{ts,tsx}": ["eslint --fix", "tsc-files --noEmit"]},
                "dependencies": {"react": "^18.3.1"},
                "devDependencies": {"eslint": "^10.10.0"},
            },
        )

        run_main(self.target_path, self.template_path, apply=True)

        keys = list(json.loads(self.target_path.read_text()).keys())
        self.assertEqual(keys.index("lint-staged"), keys.index("scripts") + 1)
        self.assertLess(keys.index("scripts"), keys.index("dependencies"))
        self.assertEqual(keys[-1], "packageManager")


if __name__ == "__main__":
    unittest.main()
