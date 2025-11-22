.PHONY: coverage test install migrate downgrade

install:
	pip install -e api

test:
	PYTHONPATH=api pytest

coverage:
	PYTHONPATH=api pytest --cov=app --cov-report=term-missing

migrate:
	cd api && alembic upgrade head

downgrade:
	cd api && alembic downgrade -1
