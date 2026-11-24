# claude-guard

Template for Python + Go projects where Claude writes the code and hard, automated gates decide
whether it is good enough. LLM review is a supplement; the deterministic gates are the contract.

## Layers

| Layer | What | When |
|---|---|---|
| Rules | `CLAUDE.md`: workflow (tests first) and banned shortcuts | every session |
| Post-edit hook | format + lint + types + slop scan on the edited file; errors go back to Claude | every Edit/Write |
| Pre-tool hook | blocks edits to gate config, deps, hooks, CI and locked tests; blocks bypass commands | every Edit/Write/Bash |
| Stop hook | Claude cannot finish while `make check` is red (gives up after 5 tries and warns you) | end of every turn |
| Tamper check | hashes of config (and locked tests) in `.claude/guard.lock`; catches changes made any way | every gate run |
| Mutation testing | mutmut / gremlins: tests must kill ≥ 90% of mutants, so "100% coverage, asserts nothing" fails | `make full`, CI |
| Independent review | `slop-reviewer` subagent reviews the diff in a fresh context | before "done" |
| CI | `.github/workflows/ci.yml` reruns everything, plus `go test -race` | every PR |

Gates (`scripts/gate.sh`): tamper check, slop scan, ruff format/lint (`ALL` rules), pyright strict,
vulture, pytest with ≥ 90% branch coverage, gofmt, golangci-lint (almost all linters), go test with
≥ 90% coverage, the tooling's own lint/types, and in `full` mode mutation testing for both languages.

Slop scan (`scripts/slop_scan.py`) rejects `# type: ignore`, `# noqa`, `pragma: no cover`, `//nolint`,
skipped/xfail tests, and test functions that cannot fail (no assertion).

## Workflow

```bash
make setup                # once
# 1. ask Claude for failing tests that pin the behaviour; review them yourself
make lock-tests           # 2. freeze them (you, not Claude)
# 3. ask Claude to implement; hooks keep it honest
make full                 # 4. everything incl. mutation testing
make unlock-tests         # next feature
```

Changed a gate config yourself (thresholds, linters, dependencies)? Run `make seal` to accept it.
`make selftest` injects 29 known-bad changes and proves each one is caught.

Optional cross-model review: `codex exec "review git diff HEAD for bugs, weak tests and slop"`.

## Using it in an existing project

Copy `CLAUDE.md`, `.claude/`, `scripts/`, `Makefile`, `.github/`, and the tool sections of
`python/pyproject.toml` / `go/.golangci.yml`. Paths assume a `python/` and/or `go/` subdirectory;
adjust `scripts/gate.sh` and the patterns in `scripts/guard.py` if your layout differs. Then `make seal`.

## Limits

- Hooks are guardrails against an agent taking shortcuts, not a security boundary. CI plus branch
  protection is the real enforcement; enable "require status checks" on `main`.
- The Bash guard is pattern-based; the tamper check catches what it misses at the next gate run.
- Some surviving mutants are equivalent (no test can tell them apart), hence a 90% threshold, not 100%.
- `go test -race` needs cgo; it runs in CI (`GATE_RACE=1`), not on machines without a C toolchain.
