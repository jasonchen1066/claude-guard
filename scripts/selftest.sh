#!/usr/bin/env bash
# Prove each gate and hook catches a known-bad change. Restores the tree after every case.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PATH="$HOME/.local/bin:$HOME/.local/go/bin:$PATH"
export CLAUDE_PROJECT_DIR="$ROOT"
SNAP="$(mktemp -d)"
OUT="$(mktemp)"
PASS=0
FAIL=0
trap 'restore; rm -rf "$SNAP" "$OUT"' EXIT

SNAP_PATHS=(python/src python/tests python/pyproject.toml go .claude/guard.lock)
tar -cf "$SNAP/tree.tar" "${SNAP_PATHS[@]}"
restore() { rm -rf "${SNAP_PATHS[@]}"; tar -xf "$SNAP/tree.tar"; rm -f .claude/.gate_state.json; }

result() {  # name, ok?
  if [ "$2" = 1 ]; then echo "  caught   $1"; PASS=$((PASS + 1))
  else echo "  MISSED   $1"; sed 's/^/           /' "$OUT" | tail -n 15; FAIL=$((FAIL + 1)); fi
}

expect_gate() {  # description, mode, gate name
  bash scripts/gate.sh "$2" >"$OUT" 2>&1
  grep -q "FAIL  $3" "$OUT" && result "$1 -> [$3]" 1 || result "$1 -> [$3]" 0
  restore
}

expect_hook_block() {  # description, hook, json
  echo "$3" | python3 -I ".claude/hooks/$2" >"$OUT" 2>&1
  [ $? -eq 2 ] && result "$1 -> [$2]" 1 || result "$1 -> [$2]" 0
  restore
}

PARSE=python/src/durations/parse.py
PYTEST=python/tests/test_parse.py
GOSRC=go/allocate/allocate.go
GOTEST=go/allocate/allocate_test.go

echo "== baseline =="
bash scripts/gate.sh full >"$OUT" 2>&1 && result "clean tree passes all gates" 1 || result "clean tree passes all gates" 0

echo "== python =="
printf '\n\ndef answer() -> int:\n    return "42"\n' >>"$PARSE"
expect_gate "type error" fast "py types"

printf '\n\ndef risky() -> None:\n    try:\n        parse_duration("x")\n    except Exception:\n        pass\n' >>"$PARSE"
expect_gate "swallowed exception" fast "py lint"

printf '\n\ndef unreachable() -> int:\n    return 1\n    print("never")\n' >>"$PARSE"
expect_gate "unreachable dead code" fast "py dead code"

printf 'from durations import parse_duration\n\n\ndef test_runs() -> None:\n    parse_duration("1s")\n' >python/tests/test_empty.py
expect_gate "test without assertion" fast "slop scan"

sed -i 's/^def test_error_is_value_error/@pytest.mark.skip(reason="flaky")\ndef test_error_is_value_error/' "$PYTEST"
expect_gate "skipped test" fast "slop scan"

sed -i 's/    return total$/    return total  # type: ignore/' "$PARSE"
expect_gate "type: ignore suppression" fast "slop scan"

cat >>"$PARSE" <<'EOF'


def describe(seconds: int) -> str:
    if seconds < 0:
        return "negative"
    if seconds == 0:
        return "zero"
    if seconds < 60:
        return "seconds"
    if seconds < 3600:
        return "minutes"
    if seconds < 86400:
        return "hours"
    return "days"
EOF
expect_gate "untested code (coverage drop)" fast "py tests+cov"

cat >"$PYTEST" <<'EOF'
import pytest

from durations import DurationError, parse_duration


@pytest.mark.parametrize("text", ["0s", "45s", "1h30m", "1d2h3m4s"])
def test_returns_int(text: str) -> None:
    assert isinstance(parse_duration(text), int)


@pytest.mark.parametrize("text", ["", "abc", "1h 30m", "x1h", "1h30", "30m1h", "1h1h"])
def test_rejects(text: str) -> None:
    with pytest.raises(DurationError):
        parse_duration(text)
EOF
expect_gate "weak tests with 100% coverage" full "py mutation"

echo "== go =="
printf '\n// Even splits amount equally, ignoring the error.\nfunc Even(amount int64, n int) []int64 {\n\tparts, _ := Split(amount, make([]int64, n))\n\treturn parts\n}\n' >>"$GOSRC"
expect_gate "ignored error" fast "go lint"

sed -i 's/^func Split(/\/\/nolint:gocyclo\nfunc Split(/' "$GOSRC"
expect_gate "nolint suppression" fast "slop scan"

printf '\nfunc TestNothing(t *testing.T) {\n\tt.Parallel()\n\t_, _ = allocate.Split(1, []int64{1})\n}\n' >>"$GOTEST"
expect_gate "test without assertion" fast "slop scan"

cat >"$GOTEST" <<'EOF'
package allocate_test

import (
	"testing"

	"example.com/claudeguard/allocate"
)

func TestSplitRuns(t *testing.T) {
	t.Parallel()

	inputs := [][]int64{{1, 1}, {1, 1, 1}, {3, 1}, {0, 1, 1}, {4}, {-1}, {0, 0}, nil}
	for _, w := range inputs {
		got, err := allocate.Split(7, w)
		if err == nil && len(got) != len(w) {
			t.Errorf("Split(7, %v) returned %d parts", w, len(got))
		}
	}
	if _, err := allocate.Split(-1, []int64{1}); err == nil {
		t.Error("want error")
	}
}
EOF
expect_gate "weak tests" full "go mutation"

echo "== tamper protection =="
sed -i 's/^fail_under = 90/fail_under = 10/' python/pyproject.toml
expect_gate "lowered coverage threshold" fast "tamper check"

python3 -I scripts/guard.py lock-tests >/dev/null
sed -i 's/("0s", 0)/("0s", 1)/' "$PYTEST"
expect_gate "edited a locked test" fast "tamper check"

python3 -I scripts/guard.py lock-tests >/dev/null
rm "$GOTEST"
expect_gate "deleted a locked test" fast "tamper check"

echo "== hooks =="
expect_hook_block "Edit gate config" pre_tool.py \
  "{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"$ROOT/python/pyproject.toml\"}}"
expect_hook_block "Write new dependency" pre_tool.py \
  "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$ROOT/go/go.mod\"}}"
expect_hook_block "sed on config via Bash" pre_tool.py \
  '{"tool_name":"Bash","tool_input":{"command":"sed -i s/90/10/ python/pyproject.toml"}}'
expect_hook_block "unlock tests via Bash" pre_tool.py \
  '{"tool_name":"Bash","tool_input":{"command":"make unlock-tests"}}'
expect_hook_block "git commit --no-verify" pre_tool.py \
  '{"tool_name":"Bash","tool_input":{"command":"git commit --no-verify -m x"}}'

python3 -I scripts/guard.py lock-tests >/dev/null
expect_hook_block "Edit a locked test" pre_tool.py \
  "{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"$ROOT/$PYTEST\"}}"

printf '\n\ndef answer() -> int:\n    return "42"\n' >>"$PARSE"
expect_hook_block "post-edit catches type error" post_edit.py \
  "{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"$ROOT/$PARSE\"}}"

printf '\n// Even splits amount equally, ignoring the error.\nfunc Even(amount int64, n int) []int64 {\n\tparts, _ := Split(amount, make([]int64, n))\n\treturn parts\n}\n' >>"$GOSRC"
expect_hook_block "post-edit catches ignored Go error" post_edit.py \
  "{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"$ROOT/$GOSRC\"}}"

printf '\n\ndef answer() -> int:\n    return "42"\n' >>"$PARSE"
expect_hook_block "Stop blocked while gates red" stop_gate.py '{"hook_event_name":"Stop"}'

echo "== allowed (must NOT block) =="
echo "{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"$ROOT/$PARSE\"}}" \
  | python3 -I .claude/hooks/pre_tool.py >"$OUT" 2>&1 && result "Edit source file allowed" 1 || result "Edit source file allowed" 0
echo '{"tool_name":"Bash","tool_input":{"command":"make check"}}' \
  | python3 -I .claude/hooks/pre_tool.py >"$OUT" 2>&1 && result "make check allowed" 1 || result "make check allowed" 0
echo "{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"$ROOT/$PARSE\"}}" \
  | python3 -I .claude/hooks/post_edit.py >"$OUT" 2>&1 && result "post-edit passes clean file" 1 || result "post-edit passes clean file" 0
echo '{"hook_event_name":"Stop"}' \
  | python3 -I .claude/hooks/stop_gate.py >"$OUT" 2>&1 && result "Stop allowed when green" 1 || result "Stop allowed when green" 0
restore

echo "== $PASS caught, $FAIL missed =="
[ "$FAIL" -eq 0 ]
