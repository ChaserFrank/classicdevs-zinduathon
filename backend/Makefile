# Common tasks. Run from backend/. `make help` lists them.
PY ?= .venv/bin/python
MANAGE = $(PY) manage.py

.PHONY: help venv services dev down migrate run test cov lint format schema schema-check deploy-check seed

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

venv: ## Create .venv and install dev requirements
	python3.12 -m venv .venv && .venv/bin/pip install -r requirements/dev.txt

services: ## Start postgres, redis and mailpit only
	docker compose up -d postgres redis mailpit

dev: ## Start the full stack in Docker (web on :8000, Mailpit on :8025)
	docker compose up --build

down: ## Stop the Docker stack
	docker compose down

migrate: ## Apply migrations
	$(MANAGE) migrate

run: ## Run the dev server from the venv (needs `make services`)
	$(MANAGE) runserver 0.0.0.0:8000

test: ## Run the test suite
	$(PY) -m pytest

cov: ## Run tests with coverage
	$(PY) -m pytest --cov --cov-report=term-missing

lint: ## Lint and check formatting
	$(PY) -m ruff check . && $(PY) -m ruff format --check .

format: ## Auto-fix lint issues and format
	$(PY) -m ruff check --fix . && $(PY) -m ruff format .

schema: ## Regenerate openapi.yaml (commit the result)
	$(MANAGE) spectacular --file openapi.yaml --validate --fail-on-warn

schema-check: ## Fail if openapi.yaml is out of date
	$(MANAGE) spectacular --file /tmp/openapi.check.yaml --validate --fail-on-warn && diff -u openapi.yaml /tmp/openapi.check.yaml

deploy-check: ## Django deployment checklist with production settings
	DJANGO_SETTINGS_MODULE=config.settings.prod DJANGO_SECRET_KEY=$$(python3 -c "import secrets;print(secrets.token_urlsafe(50))") DJANGO_ALLOWED_HOSTS=api.example.com $(MANAGE) check --deploy --fail-level WARNING

seed: ## Load demo data (available from Phase 6)
	$(MANAGE) seed_demo
