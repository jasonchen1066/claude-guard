#!/usr/bin/env bash
# Quality gates. Usage: scripts/gate.sh [fast|full]
#   fast: format, lint, types, dead code, tests + coverage, slop scan, tamper check
#   full: fast + mutation testing
# Runs every gate, prints only failures, exits 1 if any failed.
set -uo pipefail

MODE="${1:-fast}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:$HOME/.local/go/bin:$PATH"
COVER_MIN=90
MUTATION_MIN=90
FAILED=()
LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT

gate() {
  local name="$1"; shift
  if "$@" >"$LOG" 2>&1; then
    echo "  ok    $name"
  else
    echo "  FAIL  $name"
    sed 's/^/        /' "$LOG" | tail -n 40
    FAILED+=("$name")
  fi
}

py() { (cd "$ROOT/python" && uv run --frozen --quiet "$@"); }

go_cover() {
  local out; out="$(mktemp)"
  (cd "$ROOT/go" && go test -count=1 -coverprofile="$out" ./...) || { rm -f "$out"; return 1; }
  local pct; pct="$(cd "$ROOT/go" && go tool cover -func="$out" | awk '/^total:/ {sub("%","",$3); print $3}')"
  rm -f "$out"
  awk -v p="$pct" -v m="$COVER_MIN" 'BEGIN { if (p+0 < m) { printf "coverage %.1f%% < %d%%\n", p, m; exit 1 } }'
}

go_fmt() {
  local bad; bad="$(cd "$ROOT/go" && gofmt -l .)"
  [ -z "$bad" ] || { echo "not gofmt'd:"; echo "$bad"; return 1; }
}

py_mutation() {
  (cd "$ROOT/python" && rm -rf mutants && uv run --frozen --quiet mutmut run >/dev/null 2>&1; \
   uv run --frozen --quiet mutmut export-cicd-stats >/dev/null 2>&1) || true
  python3 -I - "$ROOT/python/mutants/mutmut-cicd-stats.json" "$MUTATION_MIN" <<'EOF' || { (cd "$ROOT/python" && uv run --frozen --quiet mutmut results 2>/dev/null); return 1; }
import json, sys
d = json.load(open(sys.argv[1]))
total = d["total"] - d["skipped"]
score = 100 * d["killed"] / total if total else 100
print(f"mutation score {score:.1f}% ({d['killed']}/{total} killed)")
sys.exit(0 if score >= float(sys.argv[2]) else 1)
EOF
}

# gremlins' own --threshold-* flags do not change its exit code, so parse the report.
go_mutation() {
  local report; report="$(cd "$ROOT/go" && gremlins unleash --timeout-coefficient 30 . 2>&1)" || {
    echo "$report"; return 1; }
  echo "$report" | grep -E 'LIVED|NOT COVERED|TIMED OUT|Test efficacy|Mutator coverage'
  echo "$report" | awk -v m="$MUTATION_MIN" '
    /Test efficacy:/    { e = $3 + 0; seen++ }
    /Mutator coverage:/ { c = $3 + 0; seen++ }
    END {
      if (seen < 2) { print "could not read gremlins report"; exit 1 }
      if (e < m || c < m) { printf "efficacy %.1f%% / mutator coverage %.1f%% below %d%%\n", e, c, m; exit 1 }
    }'
}

echo "== gates ($MODE) =="
gate "tamper check"     python3 -I "$ROOT/scripts/guard.py" verify
gate "slop scan"        python3 -I "$ROOT/scripts/slop_scan.py"

if [ -f "$ROOT/python/pyproject.toml" ]; then
  gate "py format"      py ruff format --check .
  gate "py lint"        py ruff check .
  gate "py types"       py pyright
  gate "py dead code"   py vulture src --min-confidence 80
  gate "py tests+cov"   py pytest -q --cov --cov-report=term-missing
  gate "tooling lint"   py ruff check --config ../scripts/ruff.toml ../scripts ../.claude/hooks
  gate "tooling format" py ruff format --check --config ../scripts/ruff.toml ../scripts ../.claude/hooks
  gate "tooling types"  py pyright ../scripts ../.claude/hooks
fi

if [ -f "$ROOT/go/go.mod" ]; then
  gate "go format"      go_fmt
  gate "go lint"        bash -c "cd '$ROOT/go' && golangci-lint run ./..."
  gate "go tests+cov"   go_cover
  if [ "${GATE_RACE:-0}" = "1" ]; then
    gate "go race"      bash -c "cd '$ROOT/go' && CGO_ENABLED=1 go test -race -count=1 ./..."
  fi
fi

if [ "$MODE" = "full" ]; then
  [ -f "$ROOT/python/pyproject.toml" ] && gate "py mutation" py_mutation
  [ -f "$ROOT/go/go.mod" ] && gate "go mutation" go_mutation
fi

if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "== FAILED: ${FAILED[*]} =="
  exit 1
fi
echo "== all gates passed =="
