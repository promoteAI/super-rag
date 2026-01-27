##################################################

# Database & Infrastructure

##################################################

# Database schema management

.PHONY: help makemigration makemigration-empty migrate fix-migration-version run-prod run-dev run-ui run-ray

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Available targets:"
	@echo "  help                Show this help message."
	@echo "  makemigration        Generate a new Alembic migration (autogenerate)."
	@echo "  makemigration-empty  Create an empty migration file (manual editing)."
	@echo "  migrate              Apply database migrations (alembic upgrade head)."
	@echo "  fix-migration-version Fix duplicate entries in alembic_version table."
	@echo "  run-prod       Run API server in production mode (with migrations)."
	@echo "  run-dev        Run API server in development mode (with --reload, with migrations)."
	@echo "  run-ui-dev     Start the UI in development mode (npm run dev)."
	@echo "  run-ray        Run Ray scheduler (config/ray_schedule.py)."

makemigration:
	@echo "Checking database migration status..."
	@uv run alembic -c super_rag/alembic.ini current || true
	@echo "Attempting to generate migration with autogenerate..."
	@MSG=$${MSG:-"auto migration"}; \
	if uv run alembic -c super_rag/alembic.ini revision --autogenerate -m "$$MSG" 2>&1; then \
		echo "Migration created successfully."; \
	else \
		echo ""; \
		echo "Warning: Autogenerate failed. This usually means:"; \
		echo "  1. Database schema doesn't match models, or"; \
		echo "  2. There are pending migrations to apply."; \
		echo ""; \
		echo "Try running 'make migrate' first, or create an empty migration:"; \
		echo "  uv run alembic -c super_rag/alembic.ini revision -m \"your message\""; \
		exit 1; \
	fi

makemigration-empty:
	@echo "Creating empty migration..."
	@MSG=$${MSG:-"empty migration"}; \
	uv run alembic -c super_rag/alembic.ini revision -m "$$MSG"

migrate:
	@echo "Checking current database version..."
	@uv run alembic -c super_rag/alembic.ini current || true
	@echo "Upgrading to head..."
	@uv run alembic -c super_rag/alembic.ini upgrade head

fix-migration-version:
	@echo "Note: If you see 'overlaps with other requested revisions' error,"
	@echo "the alembic_version table may have duplicate entries."
	@echo "The issue has been fixed. Try 'make migrate' again."

downgrade:
	@uv run alembic -c super_rag/alembic.ini downgrade base


# Local development services

run-prod:
	uvicorn super_rag.app:app --host 0.0.0.0 --log-config scripts/uvicorn-log-config-prod.yaml

run-dev:
	uvicorn super_rag.app:app --reload --reload-dir ./super_rag --host 0.0.0.0 --log-config scripts/uvicorn-log-config-dev.yaml 

run-ui-dev:
	cd super-rag-frontend/frontend && npm run dev

run-ray:
	uv run config/ray_schedule.py
