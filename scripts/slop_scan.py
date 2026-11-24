"""Reject patterns that let low-quality code slip past the other gates.

Usage: slop_scan.py [FILE ...]   (no args = scan the whole repo)
Exit 1 with one line per finding.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", "mutants", ".git", "node_modules", "vendor", "__pycache__"}

PY_BANNED = [
    (re.compile(r"#\s*type:\s*ignore"), "type: ignore suppression"),
    (re.compile(r"#\s*noqa"), "noqa suppression"),
    (re.compile(r"#\s*pyright:\s*(ignore|basic|off)"), "pyright suppression"),
    (re.compile(r"pragma:\s*no\s*cover"), "coverage exclusion"),
    (re.compile(r"pytest\.mark\.(skip|skipif|xfail)\b"), "skipped/xfail test"),
    (re.compile(r"pytest\.(skip|xfail|importorskip)\("), "skipped/xfail test"),
    (re.compile(r"unittest\.skip"), "skipped test"),
]
GO_BANNED = [
    (re.compile(r"//\s*nolint"), "nolint suppression"),
    (re.compile(r"\bt\.Skip(f|Now)?\("), "skipped test"),
    (re.compile(r"//\s*coverage:ignore"), "coverage exclusion"),
]
GO_TEST_FUNC = re.compile(r"^func (Test\w*)\(t \*testing\.T\) \{$", re.MULTILINE)
GO_ASSERT = re.compile(r"\bt\.(Error|Errorf|Fatal|Fatalf|Fail|FailNow)\(")
PY_ASSERT_CALL = re.compile(r"^(assert_|pytest\.(raises|warns|fail))")
SELF_NAME = "slop_scan.py"


def scan_lines(path: Path, text: str, banned: list[tuple[re.Pattern[str], str]]) -> list[str]:
    return [
        f"{path}:{lineno}: {why}"
        for lineno, line in enumerate(text.splitlines(), 1)
        for pattern, why in banned
        if pattern.search(line)
    ]


def _calls_assertion(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assert):
            return True
        if isinstance(sub, ast.Call) and PY_ASSERT_CALL.match(ast.unparse(sub.func)):
            return True
    return False


def scan_python_tests(path: Path, text: str) -> list[str]:
    tree = ast.parse(text, filename=str(path))
    return [
        f"{path}:{node.lineno}: test '{node.name}' has no assertion"
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test")
        and not _calls_assertion(node)
    ]


def scan_go_tests(path: Path, text: str) -> list[str]:
    findings: list[str] = []
    for match in GO_TEST_FUNC.finditer(text):
        end = text.find("\n}\n", match.end())
        body = text[match.end() : end if end != -1 else len(text)]
        if not GO_ASSERT.search(body):
            lineno = text.count("\n", 0, match.start()) + 1
            name = match.group(1)
            findings.append(f"{path}:{lineno}: test '{name}' never fails (no t.Error/t.Fatal)")
    return findings


def scan_file(path: Path) -> list[str]:
    if path.name == SELF_NAME or not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    if path.suffix == ".py":
        findings = scan_lines(rel, text, PY_BANNED)
        if path.name.startswith("test_") or path.name.endswith("_test.py"):
            findings += scan_python_tests(rel, text)
        return findings
    if path.suffix == ".go":
        findings = scan_lines(rel, text, GO_BANNED)
        if path.name.endswith("_test.go"):
            findings += scan_go_tests(rel, text)
        return findings
    return []


def repo_files() -> list[Path]:
    return [
        p
        for p in sorted(ROOT.rglob("*"))
        if p.suffix in {".py", ".go"} and not SKIP_DIRS.intersection(p.relative_to(ROOT).parts)
    ]


def main(argv: list[str]) -> int:
    files = [Path(a).resolve() for a in argv] if argv else repo_files()
    findings = [f for path in files for f in scan_file(path)]
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
