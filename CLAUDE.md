# Engineering rules (enforced by claude-guard)

This repo has automated quality gates. Hooks run them on every edit and before you can finish.
`make check` runs the fast gates; `make full` adds mutation testing. Read their output, fix root causes.

## Workflow
1. **Tests first.** For a feature or bug fix, write failing tests that pin down the required
   behaviour, run them, show they fail for the right reason, then STOP and let the human review
   them. The human locks them (`make lock-tests`) before you implement.
2. **Implement** the smallest change that makes the locked tests pass. Locked tests cannot be
   edited; you may add new test files.
3. **Gates green**: `make check` must pass. Before saying "done", also run `make full`.
4. **Independent review**: use the `slop-reviewer` subagent on your diff and address every
   finding (or explain to the human why it does not apply).
5. Report honestly: what changed, what was verified, what was not.

## Hard rules
- Never weaken a check: no `# type: ignore`, `# noqa`, `# pyright: ignore`, `pragma: no cover`,
  `//nolint`, skipped/xfail tests, lowered thresholds. These are blocked anyway.
- Never edit gate config, hooks, scripts, CI, or dependency files (`pyproject.toml`, `uv.lock`,
  `go.mod`, `go.sum`). Need a new dependency or a config change? Stop and ask the human.
- Every test must assert something meaningful. Assert exact values and exact error types/messages,
  not just "no exception" or substring matches that a wrong message would also satisfy.
- Errors are handled or returned with context, never swallowed. No bare `except`, no `except
  Exception: pass`, no `_ = err`.
- No dead code, no commented-out code, no speculative abstractions, no unused parameters,
  no "just in case" options. Do only what was asked.
- Comments explain *why*, never restate *what* the code does. No banner or changelog comments.
- No new files, modules or layers unless the task needs them. Prefer editing existing code.
- Keep functions small (complexity limits are enforced). Split by responsibility, not by line count.
- If a requirement is ambiguous or a test looks wrong, stop and ask. Do not guess and do not
  "fix" the test.

## Layout
- `python/` — uv project; src layout in `python/src/`, tests in `python/tests/`.
- `go/` — Go module; tests next to code as `*_test.go`, external `_test` packages preferred.
