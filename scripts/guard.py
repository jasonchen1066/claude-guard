"""Tamper protection for gate config and (optionally) tests.

  guard.py seal          snapshot protected config (human, after changing config)
  guard.py lock-tests    snapshot test files; Claude may add tests but not edit/delete them
  guard.py unlock-tests  allow test edits again (test-writing phase)
  guard.py verify        fail if anything protected changed since the snapshot
  guard.py classify PATH print "config", "test" (only when locked) or "free"

The snapshot lives in .claude/guard.lock and should be committed.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / ".claude" / "guard.lock"

CONFIG_PATTERNS = [
    "CLAUDE.md",
    "Makefile",
    ".claude/settings.json",
    ".claude/hooks/*",
    ".claude/agents/*",
    ".claude/guard.lock",
    "scripts/*",
    ".github/workflows/*",
    "python/pyproject.toml",
    "python/uv.lock",
    "go/.golangci.yml",
    "go/go.mod",
    "go/go.sum",
]
TEST_PATTERNS = ["python/tests/*.py", "python/tests/**/*.py", "go/*_test.go", "go/**/*_test.go"]
SKIP_DIRS = {".venv", "mutants", ".git", "__pycache__", ".pytest_cache", ".ruff_cache"}


def _matches(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(rel, p) for p in patterns)


def _files(patterns: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT).as_posix()
        if (
            path.is_file()
            and not SKIP_DIRS.intersection(path.relative_to(ROOT).parts)
            and rel != ".claude/guard.lock"
            and _matches(rel, patterns)
        ):
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _load() -> dict[str, dict[str, str] | None]:
    if not LOCK.exists():
        return {"config": None, "tests": None}
    return json.loads(LOCK.read_text(encoding="utf-8"))


def _save(state: dict[str, dict[str, str] | None]) -> None:
    LOCK.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _diff(label: str, before: dict[str, str], now: dict[str, str], *, allow_new: bool) -> list[str]:
    problems = [f"{label} changed: {p}" for p in before if p in now and now[p] != before[p]]
    problems += [f"{label} deleted: {p}" for p in before if p not in now]
    if not allow_new:
        problems += [f"{label} added: {p}" for p in now if p not in before]
    return problems


def verify() -> int:
    state = _load()
    problems: list[str] = []
    if state["config"] is not None:
        problems += _diff(
            "protected config", state["config"], _files(CONFIG_PATTERNS), allow_new=False
        )
    if state["tests"] is not None:
        problems += _diff("locked test", state["tests"], _files(TEST_PATTERNS), allow_new=True)
    for p in problems:
        print(p)
    if problems:
        print("Only a human may change these. If the change is intended, a human runs `make seal`.")
    return 1 if problems else 0


def classify(raw: str) -> str:
    path = Path(raw).resolve()
    if not path.is_relative_to(ROOT):
        return "free"
    rel = path.relative_to(ROOT).as_posix()
    if _matches(rel, CONFIG_PATTERNS):
        return "config"
    if _load()["tests"] is not None and _matches(rel, TEST_PATTERNS):
        return "test"
    return "free"


def _update(key: str, files: dict[str, str] | None) -> int:
    state = _load()
    state[key] = files
    _save(state)
    print(f"{key}: {'unlocked' if files is None else f'{len(files)} files snapshotted'}")
    return 0


COMMANDS: dict[str, Callable[[], int]] = {
    "seal": lambda: _update("config", _files(CONFIG_PATTERNS)),
    "lock-tests": lambda: _update("tests", _files(TEST_PATTERNS)),
    "unlock-tests": lambda: _update("tests", None),
    "verify": verify,
}


def main(argv: list[str]) -> int:
    match argv:
        case [cmd] if cmd in COMMANDS:
            return COMMANDS[cmd]()
        case ["classify", path]:
            print(classify(path))
            return 0
        case _:
            print(__doc__)
            return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
