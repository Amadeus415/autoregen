.PHONY: setup quick gen0 loop chart benchmark benchmark-audit benchmark-preflight full-data verify

PYTHON ?= .venv/bin/python

setup:
	python3.13 -m venv .venv
	.venv/bin/pip install -U pip wheel
	.venv/bin/pip install -r requirements.txt

quick:
	$(PYTHON) prepare.py generate --quick
	$(PYTHON) prepare.py checksum --write

full-data:
	$(PYTHON) prepare.py generate --seed 42
	$(PYTHON) prepare.py checksum --write

gen0:
	$(PYTHON) prepare.py gen0 --workers 4

loop:
	MAX_GENS=$${MAX_GENS:-50} WORKERS=$${WORKERS:-4} ./loop.sh

chart:
	$(PYTHON) plots/make_chart.py

benchmark-preflight:
	$(PYTHON) benchmark_models.py --preflight-only

benchmark:
	$(PYTHON) benchmark_models.py --generations $${GENERATIONS:-3} --workers $${WORKERS:-4}

benchmark-audit:
	test -n "$${RUN}" && $(PYTHON) audit_benchmark.py "$${RUN}"

verify:
	$(PYTHON) prepare.py verify-checksum
