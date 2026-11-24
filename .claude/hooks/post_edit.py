"""PostToolUse on Edit/Write: format, lint, type-check and slop-scan the touched file.

Exit 2 = problems found; stderr is fed back to Claude so it fixes them immediately.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2]))
HOME = Path.home()
ENV = {**os.environ, "PATH": f"{HOME}/.local/bin:{HOME}/.local/go/bin:{os.environ.get('PATH', '')}"}


def run(cmd: list[str], cwd: Path) -> tuple[bool, str]:
    result = subprocess.run(cmd, cwd=cwd, env=ENV, capture_output=True, text=True, check=False)
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def check_python(path: Path) -> list[str]:
    cwd = ROOT / "python"
    uv = ["uv", "run", "--frozen", "--quiet"]
    run([*uv, "ruff", "format", str(path)], cwd)
    run([*uv, "ruff", "check", "--fix", "--quiet", str(path)], cwd)
    problems: list[str] = []
    for name, cmd in [
        ("ruff", [*uv, "ruff", "check", str(path)]),
        ("pyright", [*uv, "pyright", str(path)]),
    ]:
        ok, out = run(cmd, cwd)
        if not ok:
            problems.append(f"[{name}]\n{out}")
    return problems


def check_go(path: Path) -> list[str]:
    cwd = ROOT / "go"
    run(["goimports", "-w", str(path)], cwd)
    pkg = "./" + path.parent.relative_to(cwd).as_posix()
    ok, out = run(["golangci-lint", "run", pkg], cwd)
    return [] if ok else [f"[golangci-lint]\n{out}"]


CHECKERS: dict[tuple[str, str], Callable[[Path], list[str]]] = {
    ("python", ".py"): check_python,
    ("go", ".go"): check_go,
}


def checker_for(raw: str) -> Callable[[Path], list[str]] | None:
    path = Path(raw).resolve() if raw else None
    if path is None or not path.is_relative_to(ROOT) or not path.exists():
        return None
    return CHECKERS.get((path.relative_to(ROOT).parts[0], path.suffix))


def main() -> int:
    raw = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
    check = checker_for(raw)
    if check is None:
        return 0

    path = Path(raw).resolve()
    problems = check(path)
    ok, out = run([sys.executable, "-I", str(ROOT / "scripts" / "slop_scan.py"), str(path)], ROOT)
    if not ok:
        problems.append(f"[slop scan]\n{out}")
    if problems:
        print(
            f"claude-guard found problems in {path.name}. Fix them properly "
            "(no suppressions, no skipped tests):\n\n" + "\n\n".join(problems),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
