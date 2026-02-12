# ABOUTME: Build entry points for storyboard-gen.
# ABOUTME: Provides install, test, lint, release, and Homebrew targets.

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
RUFF := $(VENV)/bin/ruff
PYTEST := $(VENV)/bin/pytest

VERSION_FILE := src/storyboard_gen/__init__.py
CURRENT_VERSION := $(shell grep '__version__' $(VERSION_FILE) 2>/dev/null | sed 's/.*"\(.*\)".*/\1/')

.PHONY: help install test lint lint-fix clean sync release formula brew-upgrade

help: ## Show this help
	@echo "storyboard-gen v$(CURRENT_VERSION)"
	@echo ""
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

release: ## Release new version. Usage: make release [VERSION=x.y.z]
	@scripts/release.sh $(VERSION)

formula: ## Update Homebrew formula SHA256 for current version
	@version="$(CURRENT_VERSION)"; \
	url="https://github.com/tigger04/storyboard-gen/archive/refs/tags/v$${version}.tar.gz"; \
	sha256=$$(curl -sL "$${url}" | shasum -a 256 | cut -d' ' -f1); \
	echo "v$${version} SHA256: $${sha256}"; \
	python3 -c " \
import re; from pathlib import Path; \
f = Path('../homebrew-tap/Formula/storyboard-gen.rb'); \
c = f.read_text(); \
c = re.sub(r'sha256 \"[a-f0-9]+\"', 'sha256 \"$${sha256}\"', c); \
c = re.sub(r'url \".*\.tar\.gz\"', 'url \"$${url}\"', c); \
f.write_text(c); \
print('Updated formula')"

brew-upgrade: ## Upgrade local Homebrew install
	brew update
	brew upgrade tigger04/tap/storyboard-gen

sync: ## Git sync: add, commit, pull, push
	@read -r -p "Commit message: " msg; \
	git add --all && \
	git commit -m "$$msg" && \
	git pull --rebase && \
	git push
