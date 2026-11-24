"""PreToolUse: block edits to protected config, locked tests, and guard bypasses.

Exit 2 = block the tool call; stderr is shown to Claude.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2]))
GUARD = ROOT / "scripts" / "guard.py"

BYPASS = [
    (re.compile(r"guard\.lock"), "the guard lock file"),
    (re.compile(r"guard\.py\s+(seal|lock-tests|unlock-tests)"), "guard admin commands"),
    (re.compile(r"\bmake\s+(seal|lock-tests|unlock-tests)\b"), "guard admin commands"),
    (re.compile(r"--no-verify\b|\bgit\s+commit\b.*\s-n\b"), "skipping git hooks"),
    (re.compile(r"\bSKIP_GATES\b|CLAUDE_GUARD_OFF"), "disabling gates"),
]
WRITE_OPS = re.compile(
    r"(\bsed\s+-i|\bperl\s+-i|>|\btee\b|\bmv\b|\brm\b|\bcp\b|\btruncate\b"
    r"|\bgit\s+(checkout|restore)\b)"
)
PROTECTED_NAMES = re.compile(
    r"(CLAUDE\.md|Makefile|settings\.json|\.claude/hooks|\.claude/agents|scripts/|\.github/|"
    r"pyproject\.toml|uv\.lock|\.golangci\.yml|go\.mod|go\.sum|_test\.go|tests/)"
)


def classify(path: str) -> str:
    result = subprocess.run(
        [sys.executable, "-I", str(GUARD), "classify", path],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def block(reason: str) -> int:
    print(f"BLOCKED by claude-guard: {reason}", file=sys.stderr)
    return 2


def check_edit(path: str) -> int:
    kind = classify(path)
    if kind == "config":
        return block(
            f"{path} is protected gate/config/dependency file. Do not change it. "
            "If you think it must change, stop and ask the human, explaining why."
        )
    if kind == "test":
        return block(
            f"{path} is a locked test. Make the implementation pass the existing tests; "
            "do not edit tests. You may add new test files. "
            "If a test is wrong, stop and tell the human."
        )
    return 0


def check_bash(command: str) -> int:
    for pattern, what in BYPASS:
        if pattern.search(command):
            return block(f"command touches {what}; that is human-only.")
    if WRITE_OPS.search(command) and PROTECTED_NAMES.search(command):
        return block(
            "shell command appears to modify protected config or tests. "
            "Use the Edit tool for source files; ask the human for config/test changes."
        )
    return 0


def main() -> int:
    event = json.load(sys.stdin)
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    if tool in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        return check_edit(path)
    if tool == "Bash":
        return check_bash(tool_input.get("command", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
