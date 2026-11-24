.PHONY: setup check full seal lock-tests unlock-tests selftest

GUARD := python3 -I scripts/guard.py

setup:            ## install dev tooling
	cd python && uv sync
	cd go && go mod download

check:            ## fast gates (also run by the Stop hook)
	@bash scripts/gate.sh fast

full:             ## fast gates + mutation testing
	@bash scripts/gate.sh full

seal:             ## HUMAN: accept current gate/config files as the trusted baseline
	@$(GUARD) seal

lock-tests:       ## HUMAN: freeze reviewed tests before Claude implements
	@$(GUARD) lock-tests

unlock-tests:     ## HUMAN: allow test edits again
	@$(GUARD) unlock-tests

selftest:         ## prove each gate catches a known-bad change
	@bash scripts/selftest.sh
