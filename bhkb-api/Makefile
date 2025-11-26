.PHONY: coverage test test-unit install migrate downgrade

install:
	pip install -e .

test:
	PYTHONPATH=. pytest

coverage:
	PYTHONPATH=. pytest --cov=app --cov-report=term-missing --cov-report=html:coverage_html

test-unit:
	PYTHONPATH=. pytest --cov=app --cov-report=term-missing --cov-report=html:coverage_html tests/unit

migrate:
	alembic upgrade head

downgrade:
	alembic downgrade -1
