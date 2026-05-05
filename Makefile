.PHONY: help dev down migrate migration upgrade downgrade test lint format run worker beat shell logs

help:
	@echo "DACA Operations Platform"
	@echo "========================"
	@echo "make dev        - Start all services via docker-compose (with build)"
	@echo "make down       - Stop all services"
	@echo "make test       - Run test suite (pytest with asyncio)"
	@echo "make lint       - Run ruff check"
	@echo "make format     - Run ruff format"
	@echo "make migrate    - Run pending migrations (alembic upgrade head)"
	@echo "make migration  - Generate a new Alembic migration (usage: make migration msg=\"description\")"
	@echo "make shell      - Open a shell in the api container"
	@echo "make worker     - Run Celery worker locally"
	@echo "make beat       - Run Celery beat scheduler locally"
	@echo "make logs       - Tail docker-compose logs"
	@echo "make upgrade    - Run pending migrations (alias for migrate)"
	@echo "make downgrade  - Roll back last migration"
	@echo "make run        - Run API server locally (no Docker)"

dev:
	docker-compose up --build

down:
	docker-compose down

test:
	pytest tests/ -v --asyncio-mode=auto --cov=app --cov-report=term-missing

lint:
	ruff check app/ tests/

format:
	ruff format app/ tests/

migrate:
	alembic upgrade head

migration:
	alembic revision --autogenerate -m "$(msg)"

upgrade:
	alembic upgrade head

downgrade:
	alembic downgrade -1

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	celery -A app.tasks.celery_app worker --loglevel=info

beat:
	celery -A app.tasks.celery_app beat --loglevel=info

shell:
	docker exec -it $$(docker-compose ps -q api) /bin/bash

logs:
	docker-compose logs -f
