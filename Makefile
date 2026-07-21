.PHONY: venv run test

venv: .venv/.installed

.venv/bin/python:
	python3 -m venv .venv

.venv/.installed: pyproject.toml | .venv/bin/python
	.venv/bin/python -m pip install -e .
	touch .venv/.installed

.venv/.dev-installed: pyproject.toml | .venv/bin/python
	.venv/bin/python -m pip install -e '.[dev]'
	touch .venv/.dev-installed

run: venv
	set -a; [ ! -f .env ] || . ./.env; set +a; .venv/bin/python manage.py runserver

test: .venv/.dev-installed
	.venv/bin/python -m pytest
