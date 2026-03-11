# ABOUTME: Build entry points for storyboard-gen.
# ABOUTME: Provides install, test, lint, release, and Homebrew targets.

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
RUFF := $(VENV)/bin/ruff
PYTEST := $(VENV)/bin/pytest
LOCAL_BIN := $(HOME)/.local/bin

VERSION_FILE := src/storyboard_gen/__init__.py
CURRENT_VERSION := $(shell grep '__version__' $(VERSION_FILE) 2>/dev/null | sed 's/.*"\(.*\)".*/\1/')

.PHONY: help install install-gui test lint lint-fix clean sync release formula brew-upgrade gui gui-verbose app

help: ## Show this help
	@echo "storyboard-gen v$(CURRENT_VERSION)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

$(VENV)/bin/activate:
	python3.12 -m venv $(VENV)
	$(PIP) install --upgrade pip -q

install: $(VENV)/bin/activate ## Create venv, install deps, symlink to ~/.local/bin
	$(PIP) install -r requirements.txt -q
	$(PIP) install ruff pytest -q
	$(PIP) install -e . -q
	@mkdir -p "$(LOCAL_BIN)"
	@ln -sf "$(CURDIR)/$(VENV)/bin/storyboard-gen" "$(LOCAL_BIN)/storyboard-gen"
	@echo "Installed: $(LOCAL_BIN)/storyboard-gen"
	@if ! echo "$$PATH" | grep -q "$(LOCAL_BIN)"; then \
		echo "Warning: $(LOCAL_BIN) is not on your PATH"; \
	fi
	@echo "Note: Cost estimates are indicative. FAL prices are live; Google and Replicate use static defaults."

install-gui: install ## Install with GUI dependencies (PySide6)
	$(PIP) install PySide6 pytest-qt -q
	$(PIP) install -e ".[gui]" -q
	@ln -sf "$(CURDIR)/$(VENV)/bin/storyboard-gen-gui" "$(LOCAL_BIN)/storyboard-gen-gui"
	@echo "Installed: $(LOCAL_BIN)/storyboard-gen-gui"

test: ## Run all tests
	$(PYTEST) tests/ -v

lint: ## Run Ruff linter and formatter check
	$(RUFF) check src/ tests/
	$(RUFF) format --check src/ tests/

lint-fix: ## Auto-fix lint issues
	$(RUFF) check --fix src/ tests/
	$(RUFF) format src/ tests/

gui: ## Launch the GUI (install-gui first if needed)
	@if ! $(PYTHON) -c "import PySide6" 2>/dev/null; then \
		echo "PySide6 not installed. Run: make install-gui"; \
		exit 1; \
	fi
	$(PYTHON) -m storyboard_gen.gui

gui-verbose: ## Launch the GUI with verbose stderr logging
	@if ! $(PYTHON) -c "import PySide6" 2>/dev/null; then \
		echo "PySide6 not installed. Run: make install-gui"; \
		exit 1; \
	fi
	$(PYTHON) -m storyboard_gen.gui --verbose

app: ## Build macOS .app bundle and DMG
	@scripts/build-macos.sh $(VERSION)

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

brew-upgrade: ## Upgrade local Homebrew install (CLI + GUI if installed)
	brew update
	brew upgrade tigger04/tap/storyboard-gen
	@if brew list --cask tigger04/tap/storyboard-gen-gui > /dev/null 2>&1; then \
		brew upgrade --cask tigger04/tap/storyboard-gen-gui; \
	else \
		echo "GUI cask not installed. Install with: brew install --cask tigger04/tap/storyboard-gen-gui"; \
	fi

MSG ?= $(shell hostname):$(USER)

sync: ## Git sync: add, commit, pull, push. Usage: make sync [MSG="message"]
	git add --all && \
	git commit -m "$(MSG)" && \
	git pull --rebase && \
	git push
