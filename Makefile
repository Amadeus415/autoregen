.PHONY: setup generate score dummy grok test chart

PYTHON ?= .venv/bin/python

setup:
	python3.13 -m venv .venv
	.venv/bin/pip install -U pip wheel
	.venv/bin/pip install -r requirements.txt

generate:
	$(PYTHON) prepare.py generate

score:
	$(PYTHON) prepare.py score

dummy:
	$(PYTHON) prepare.py loop --agent dummy --gens 10 --workdir runs/dummy

grok:
	$(PYTHON) prepare.py loop --agent grok --gens 10 --workdir runs/grok --model grok-4.6 --effort medium

chart:
	$(PYTHON) prepare.py chart

test:
	$(PYTHON) -m pytest tests/ -q
