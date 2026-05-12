.PHONY: install test run lint engine engine-code engine-deep package-backend package-macos package-windows

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	$(VENV)/bin/pre-commit install

test:
	$(PYTHON) -m pytest tests/ -v

run:
	$(PYTHON) main.py

engine:
	./bin/start_engine.sh chat

engine-code:
	./bin/start_engine.sh coding

engine-deep:
	./bin/start_engine.sh deep

lint:
	$(VENV)/bin/black --check .
	$(VENV)/bin/ruff check .
	$(VENV)/bin/mypy core/

# ── Packaging (Module 13) ─────────────────────────────────────────────────────

package-backend:
	$(PIP) install pyinstaller>=6.0
	$(VENV)/bin/pyinstaller build/cerebro-backend.spec --distpath dist --noconfirm

package-macos: package-backend
	bash build/build_macos.sh

package-windows: package-backend
	powershell -ExecutionPolicy Bypass -File build/build_windows.ps1
