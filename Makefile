.PHONY: setup generate score dummy grok grok45 gemini terra sol test chart compare

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
	$(PYTHON) prepare.py loop --agent dummy --gens 15 --workdir runs/dummy

grok:
	$(PYTHON) prepare.py loop --agent grok --gens 20 --workdir runs/grok --model grok-4.6 --effort medium

grok45:
	$(PYTHON) prepare.py loop --agent grok --gens 20 --workdir runs/grok-4.5 --model grok-4.5 --effort high

gemini:
	$(PYTHON) prepare.py loop --agent antigravity --gens 20 --workdir runs/gemini-3.7-flash --model gemini-3.7-flash-high --effort high

terra:
	$(PYTHON) prepare.py loop --agent codex --gens 20 --workdir runs/codex-terra-high --model gpt-5.6-terra --effort high

sol:
	$(PYTHON) prepare.py loop --agent codex --gens 20 --workdir runs/codex-sol-medium --model gpt-5.6-sol --effort medium

chart:
	$(PYTHON) prepare.py chart

compare:
	$(PYTHON) plots.py

test:
	$(PYTHON) -m pytest tests/ -q
