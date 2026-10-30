"""Offline checker regressions; fixtures live exclusively in temporary directories."""

import ast
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import check_repository as checks


class RepositoryChecksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "--quiet")
        self.write("research-bot/research_bot/config.py", 'import os\nTOKEN = os.getenv("TOKEN")\n')
        self.write("research-bot/.env.example", "# TOKEN=\n")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def test_checker_does_not_execute_runtime_or_read_env_or_databases(self):
        self.write("research-bot/.env", "TOKEN=PRIVATE_SENTINEL\n")
        database = self.write("research-bot/data/bot.sqlite", "database bytes must stay unchanged")
        self.git("add", "research-bot/data/bot.sqlite")
        before = database.read_bytes()
        self.write("research-bot/research_bot/config.py", (
            'import os\nTOKEN = os.getenv("TOKEN")\n'
            'raise RuntimeError("runtime must never execute")\n'
        ))
        original_read = Path.read_text

        def guarded_read(path, *args, **kwargs):
            if path.name == ".env" or path.suffix == ".sqlite":
                raise AssertionError("checker tried to read protected data")
            return original_read(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded_read), \
                patch("socket.socket", side_effect=AssertionError("network access")), \
                patch("sqlite3.connect", side_effect=AssertionError("database connection")):
            errors, notes = checks.check_repository(self.root)
        self.assertEqual(errors, [])
        self.assertTrue(any("database file(s) remain tracked" in note for note in notes))
        self.assertEqual(database.read_bytes(), before)
        self.assertNotIn("PRIVATE_SENTINEL", "\n".join(notes))

    def test_tracked_private_env_files_fail_without_reading_their_contents(self):
        for name in (".env", "nested/.env.production"):
            self.write(name, "TOKEN=PRIVATE_SENTINEL\n")
            self.git("add", name)
        errors, notes = checks.check_repository(self.root)
        self.assertTrue(any("2 private .env file(s)" in error for error in errors))
        self.assertNotIn("PRIVATE_SENTINEL", "\n".join(errors + notes))

    def test_example_files_are_allowed_in_index(self):
        self.write("nested/.env.production.example", "# TOKEN=\n")
        self.git("add", "research-bot/.env.example", "nested/.env.production.example")
        self.assertEqual(checks.check_repository(self.root)[0], [])

    def test_python_in_other_worktrees_venvs_and_symlinks_is_not_parsed(self):
        for name in (
            "worktrees/other/scripts/bad.py", "research-bot/research_bot/.venv/bad.py",
            "scripts/venv/bad.py", "tests/worktrees/other/bad.py",
        ):
            self.write(name, "this is invalid python !!!")
        outside = self.write("outside/bad.py", "this is invalid python !!!")
        (self.root / "research-bot/research_bot/symlink.py").symlink_to(outside)
        errors, notes = checks.check_repository(self.root)
        self.assertEqual(errors, [])
        self.assertIn("parsed 1 Python files", notes[-1])

    def test_missing_configuration_variable_fails(self):
        self.write("research-bot/research_bot/extra.py", 'import os\nx = os.getenv("EXTRA")\n')
        errors, _ = checks.check_repository(self.root)
        self.assertIn("configuration template is missing: EXTRA", errors)

    def test_unknown_or_duplicate_configuration_variable_fails(self):
        self.write("research-bot/.env.example", "# TOKEN=\n# TOKEN=\n# UNKNOWN=\n")
        errors, _ = checks.check_repository(self.root)
        self.assertTrue(any("duplicate assignment" in error for error in errors))
        self.assertIn("configuration template has unsupported names: UNKNOWN", errors)

    def test_template_values_and_active_assignments_fail_without_value_output(self):
        self.write("research-bot/.env.example", "# TOKEN=PRIVATE_SENTINEL\n")
        with patch.object(checks, "ROOT", self.root), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(checks.main(), 1)
        self.assertNotIn("PRIVATE_SENTINEL", output.getvalue())
        self.write("research-bot/.env.example", "TOKEN=\n")
        errors, _ = checks.check_repository(self.root)
        self.assertTrue(any("commented empty assignments" in error for error in errors))

    def test_template_symlink_is_rejected_without_reading_target(self):
        private = self.write("research-bot/.env", "TOKEN=PRIVATE_SENTINEL\n")
        example = self.root / "research-bot/.env.example"
        example.unlink()
        example.symlink_to(private)
        with patch.object(Path, "read_text", side_effect=AssertionError("must not read symlink")):
            names, errors = checks.template_names(example)
        self.assertEqual(names, set())
        self.assertIn("configuration template must not be a symlink", errors)

    def test_syntax_failure_does_not_print_source_line(self):
        self.write("research-bot/research_bot/bad.py", 'value = "PRIVATE_SENTINEL\n')
        errors, _ = checks.check_repository(self.root)
        self.assertTrue(any("invalid Python syntax at line 1" in error for error in errors))
        self.assertNotIn("PRIVATE_SENTINEL", "\n".join(errors))

    def test_aliased_environment_access_is_inventoried(self):
        tree = ast.parse(
            'import os as system\nfrom os import getenv as env, environ as values\n'
            'system.getenv("A")\nenv(key="B")\nsystem.environ.get("C")\nvalues["D"]\n'
        )
        self.assertEqual(checks.environment_names(tree), {"A", "B", "C", "D"})

    def test_dynamic_environment_name_requires_explicit_inventory(self):
        tree = ast.parse('import os\nos.getenv(variable_name)\n')
        with self.assertRaisesRegex(ValueError, "literal uppercase variable name"):
            checks.environment_names(tree)

    def test_missing_git_checkout_or_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            errors, _ = checks.check_repository(Path(directory))
        self.assertTrue(any("cannot inspect the Git index" in error for error in errors))
        (self.root / "research-bot/research_bot/config.py").unlink()
        errors, _ = checks.check_repository(self.root)
        self.assertIn("no runtime Python source found in research-bot/research_bot", errors)


if __name__ == "__main__":
    unittest.main()
