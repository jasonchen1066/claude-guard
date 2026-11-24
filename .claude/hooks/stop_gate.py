"""Stop: Claude may not finish while any fast gate is red.

Skips the run if no source/config changed since the last green run.
After MAX_ATTEMPTS consecutive blocks it lets Claude stop (to avoid an endless loop)
but tells the human loudly that the gates are still failing.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2]))
STATE = ROOT / ".claude" / ".gate_state.json"
MAX_ATTEMPTS = 5
WATCHED_SUFFIXES = {".py", ".go", ".toml", ".mod", ".sum", ".yml", ".lock", ".sh", ".md"}
SKIP_DIRS = {".venv", "mutants", ".git", "__pycache__", ".pytest_cache", ".ruff_cache"}


def fingerprint() -> str:
    digest = hashlib.sha256()
    for path in sorted(ROOT.rglob("*")):
        parts = path.relative_to(ROOT).parts
        if path.is_file() and path.suffix in WATCHED_SUFFIXES and not SKIP_DIRS.intersection(parts):
            digest.update("/".join(parts).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def load_state() -> dict[str, object]:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main() -> int:
    json.load(sys.stdin)
    state = load_state()
    current = fingerprint()
    if state.get("green") == current:
        return 0

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "gate.sh"), "fast"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        STATE.write_text(json.dumps({"green": current, "attempts": 0}), encoding="utf-8")
        return 0

    attempts = int(str(state.get("attempts", 0))) + 1
    if attempts >= MAX_ATTEMPTS:
        STATE.write_text(json.dumps({"attempts": 0}), encoding="utf-8")
        print(
            json.dumps(
                {
                    "systemMessage": "claude-guard: quality gates are STILL FAILING after "
                    f"{attempts} attempts. Do not trust this change. Run `make check`.",
                }
            )
        )
        return 0

    STATE.write_text(json.dumps({"attempts": attempts}), encoding="utf-8")
    print(
        "claude-guard: you cannot finish yet, quality gates are failing "
        f"(attempt {attempts}/{MAX_ATTEMPTS}). Fix the root cause; do not weaken tests, "
        "add suppressions or touch config. If you are truly blocked, explain why to the human.\n\n"
        + result.stdout[-6000:],
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
