.PHONY: install test init-db doctor

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

init-db:
	combination init-db --path data/combination.sqlite3

doctor:
	combination doctor --path data/combination.sqlite3
