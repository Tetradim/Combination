.PHONY: bootstrap doctor test test-all chain iron

bootstrap:
	python scripts/bootstrap.py --dev

doctor:
	combination doctor --strict

test:
	python -m pytest tests

test-all:
	combination test-all

chain:
	combination chain --host 127.0.0.1 --port 8004

iron:
	combination iron -- --help
