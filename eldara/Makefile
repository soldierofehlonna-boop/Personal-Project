.PHONY: setup check start commit audit loop validate status

setup:
	python3 scripts/session.py setup

check:
	python3 scripts/session.py check

start:
	python3 scripts/session.py start

audit:
	python3 scripts/session.py audit

loop:
	python3 scripts/session.py loop

validate:
	python3 scripts/validate_state.py saves/current.json

status:
	python3 scripts/status_dump.py
