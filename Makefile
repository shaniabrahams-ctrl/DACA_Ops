.PHONY: help dev migrate upgrade downgrade test lint format run worker beat

help:
	@echo "DACA Operations Platform"
	@echo "========================"
	@echo "make dev        - Start all services via docker-compose"
	@echo "make migrate    - Generate a new Alembic migration"
	@echo "make upgrade    - Run pending migrations"
	@echo "make downgrade  - Roll back last migration"
	@echo "make test       - Run test suite"
	@echo "make lint       - Run ruff + mypy"
	@echo "make format     - Run black + ruff --fix"
	@echo "make run        - Run API server locally (no Docker)"
	@echo "make worker     - Run Celery worker locally"
	@echo "make beat       - Run Celery beat scheduler locally"

dev:
	docker-compose up --build

migrate:
	alembic revision --autogenerate -m "$(msg)"

upgrade:
	alembic upgrade head

downgrade:
	alembic downgrade -1

test:
	pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	ruff check app/ tests/
	mypy app/

format:
	black app/ tests/
	ruff check --fix app/ tests/

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	celery -A app.tasks.celery_app worker --loglevel=info

beat:
	celery -A app.tasks.celery_app beat --loglevel=info
