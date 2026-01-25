##################################################

# Database & Infrastructure

##################################################

# Database schema management

.PHONY: help makemigration migrate run-prod run-dev run-ui run-ray

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Available targets:"
	@echo "  help           Show this help message."
	@echo "  makemigration  Generate a new Alembic migration."
	@echo "  migrate        Apply database migrations (alembic upgrade head)."
	@echo "  run-prod       Run API server in production mode (with migrations)."
	@echo "  run-dev        Run API server in development mode (with --reload, with migrations)."
	@echo "  run-ui         Start the UI (bash ui/start.sh)."
	@echo "  run-ray        Run Ray scheduler (config/ray_schedule.py)."

makemigration:
	@uv run alembic -c super_rag/alembic.ini revision --autogenerate

migrate:
	@uv run alembic -c super_rag/alembic.ini upgrade head

downgrade:
	@uv run alembic -c super_rag/alembic.ini downgrade base


# Local development services

run-prod:
	uvicorn super_rag.app:app --host 0.0.0.0 --log-config scripts/uvicorn-log-config.yaml

run-dev:
	uvicorn super_rag.app:app --reload --reload-dir ./super_rag --host 0.0.0.0 --log-config scripts/uvicorn-log-config.yaml 

run-ui:
	bash ui/start.sh

run-ray:
	uv run config/ray_schedule.py
