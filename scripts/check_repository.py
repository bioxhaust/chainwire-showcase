#!/usr/bin/env python3
"""Offline source/index checks. Never import the bot or read its .env/databases."""

from __future__ import annotations

import ast
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("research-bot/research_bot", "scripts", "tests")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "worktrees", ".worktrees", "node_modules", "site-packages"}
ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]*\Z")
ASSIGNMENT = re.compile(r"(?:#\s*)?([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\Z")


def python_files(root: Path):
    """Inspect only source zones; never descend into worktrees, venvs or symlinks."""
    for zone in SOURCE_DIRS:
        start = root / zone
        if not start.is_dir() or start.is_symlink():
            continue
        for directory, dirs, files in os.walk(start, followlinks=False):
            base = Path(directory)
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (base / d).is_symlink())
            for name in sorted(files):
                path = base / name
                if path.suffix == ".py" and not path.is_symlink():
                    yield path


def environment_names(tree: ast.AST) -> set[str]:
    """Recognize literal os.getenv / os.environ access, including import aliases."""
    os_names, getenv_names, environ_names = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            os_names.update(alias.asname or alias.name for alias in node.names if alias.name == "os")
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            getenv_names.update(alias.asname or alias.name for alias in node.names if alias.name == "getenv")
            environ_names.update(alias.asname or alias.name for alias in node.names if alias.name == "environ")

    def os_attribute(node: ast.AST, attribute: str) -> bool:
        return (isinstance(node, ast.Attribute) and node.attr == attribute
                and isinstance(node.value, ast.Name) and node.value.id in os_names)

    def is_environ(node: ast.AST) -> bool:
        return (isinstance(node, ast.Name) and node.id in environ_names) or os_attribute(node, "environ")

    result = set()
    for node in ast.walk(tree):
        key = None
        if isinstance(node, ast.Call):
            is_getenv = ((isinstance(node.func, ast.Name) and node.func.id in getenv_names)
                         or os_attribute(node.func, "getenv"))
            is_get = isinstance(node.func, ast.Attribute) and node.func.attr == "get" and is_environ(node.func.value)
            if is_getenv or is_get:
                key = node.args[0] if node.args else next((kw.value for kw in node.keywords if kw.arg == "key"), None)
                if key is None:
                    raise ValueError("environment access needs a literal variable name")
        elif isinstance(node, ast.Subscript) and is_environ(node.value):
            key = node.slice
        if key is not None:
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str) or not ENV_NAME.fullmatch(key.value):
                raise ValueError("environment access needs a literal uppercase variable name")
            result.add(key.value)
    return result


def template_names(path: Path) -> tuple[set[str], list[str]]:
    if path.is_symlink():
        return set(), ["configuration template must not be a symlink"]
    names, issues = set(), []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = ASSIGNMENT.fullmatch(line.strip())
        if not match:
            continue
        name, value = match.groups()
        if name in names:
            issues.append(f"configuration template has a duplicate assignment at line {number}")
        names.add(name)
        if value or not line.lstrip().startswith("#"):
            issues.append(f"configuration template requires commented empty assignments at line {number}")
    return names, issues


def tracked_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "-z"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return [path for path in result.stdout.decode("utf-8", errors="surrogateescape").split("\0") if path]


def is_private_env(path: str) -> bool:
    name = PurePosixPath(path).name
    return (name == ".env" or name.startswith(".env.")) and not name.endswith(".example")


def check_repository(root: Path) -> tuple[list[str], list[str]]:
    errors, notes = [], []
    try:
        tracked = tracked_paths(root)
    except (OSError, subprocess.CalledProcessError):
        return ["cannot inspect the Git index; run inside a Git checkout with Git installed"], []

    private_envs = [path for path in tracked if is_private_env(path)]
    if private_envs:
        # Do not read contents or print paths/values from sensitive files.
        errors.append(f"Git index contains {len(private_envs)} private .env file(s); remove them from tracking")
    databases = [path for path in tracked if PurePosixPath(path).suffix.lower() in {".sqlite", ".sqlite3", ".db"}]
    if databases:
        notes.append(f"{len(databases)} database file(s) remain tracked; runtime commands can modify them and they require a separate access audit")

    names, count = set(), 0
    runtime_count = 0
    for path in python_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except SyntaxError as error:
            errors.append(f"{relative}: invalid Python syntax at line {error.lineno}")
            continue
        except (OSError, UnicodeError):
            errors.append(f"{relative}: source cannot be read as UTF-8")
            continue
        count += 1
        if relative.startswith("research-bot/research_bot/"):
            runtime_count += 1
            try:
                names.update(environment_names(tree))
            except ValueError as error:
                errors.append(f"{relative}: {error}")
    if not runtime_count:
        errors.append("no runtime Python source found in research-bot/research_bot")

    try:
        example_names, example_errors = template_names(root / "research-bot/.env.example")
        errors.extend(example_errors)
        if names - example_names:
            errors.append("configuration template is missing: " + ", ".join(sorted(names - example_names)))
        if example_names - names:
            errors.append("configuration template has unsupported names: " + ", ".join(sorted(example_names - names)))
    except (OSError, UnicodeError):
        errors.append("research-bot/.env.example cannot be read as UTF-8")
    notes.append(f"parsed {count} Python files without importing the bot; inventoried {len(names)} environment variables")
    return errors, notes


def main() -> int:
    errors, notes = check_repository(ROOT)
    for note in notes:
        print(f"NOTE: {note}")
    for error in errors:
        print(f"FAIL: {error}")
    if not errors:
        print("PASS: offline repository checks")
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
