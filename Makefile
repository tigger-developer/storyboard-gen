# ABOUTME: Build entry points for storyboard-gen.
# ABOUTME: Provides install, test, lint, and sync targets.

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
RUFF := $(VENV)/bin/ruff
PYTEST := $(VENV)/bin/pytest

.PHONY: help install test lint lint-fix clean sync release

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

$(VENV)/bin/activate:
	python3.12 -m venv $(VENV)
	$(PIP) install --upgrade pip -q

install: $(VENV)/bin/activate ## Create venv, install deps, install tool in dev mode
	$(PIP) install -r requirements.txt -q
	$(PIP) install ruff pytest -q
	$(PIP) install -e . -q
	@echo "Setup complete. Run: source $(VENV)/bin/activate"

test: ## Run all tests
	$(PYTEST) tests/ -v

lint: ## Run Ruff linter and formatter check
	$(RUFF) check src/ tests/
	$(RUFF) format --check src/ tests/

lint-fix: ## Auto-fix lint issues
	$(RUFF) check --fix src/ tests/
	$(RUFF) format src/ tests/

clean: ## Remove build artefacts
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -print0 | xargs -0 rm -rf
	find . -type f -name '*.pyc' -delete

release: ## Increment version and tag. Usage: make release [VERSION=x.y.z]
	@current=$$($(PYTHON) -c "import storyboard_gen; print(storyboard_gen.__version__)"); \
	if [ -z "$(VERSION)" ]; then \
		new=$$(echo "$$current" | awk -F. '{printf "%d.%d.%d", $$1, $$2, $$3+1}'); \
	else \
		new="$(VERSION)"; \
	fi; \
	echo "Releasing $$current -> $$new"; \
	sed -i.bak "s/version=\"$$current\"/version=\"$$new\"/" setup.py && rm -f setup.py.bak; \
	sed -i.bak "s/__version__ = \"$$current\"/__version__ = \"$$new\"/" src/storyboard_gen/__init__.py && rm -f src/storyboard_gen/__init__.py.bak; \
	git add --all && git commit -m "release: v$$new" && git tag "v$$new"

sync: ## Git sync: add, commit, pull, push
	@read -r -p "Commit message: " msg; \
	git add --all && \
	git commit -m "$$msg" && \
	git pull --rebase && \
	git push
