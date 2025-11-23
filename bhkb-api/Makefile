.PHONY: coverage test install migrate downgrade

install:
	pip install -e .

test:
	PYTHONPATH=. pytest

coverage:
	PYTHONPATH=. pytest --cov=app --cov-report=term-missing

migrate:
	alembic upgrade head

downgrade:
	alembic downgrade -1
