.PHONY: install test smoke run lint lite engine engine-embed engine-lite engine-code engine-deep desktop-config desktop-launch desktop-icon desktop-app desktop-install package-backend package-macos package-windows

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	$(VENV)/bin/pre-commit install

test:
	$(PYTHON) -m pytest tests/ -v --cov=core --cov-fail-under=80

smoke:
	bash scripts/smoke.sh

run:
	$(PYTHON) main.py

lite:
	set -a; . config/profiles/lite-8gb.env; set +a; \
	$(PYTHON) main.py

engine:
	./bin/start_engine.sh chat

engine-embed:
	./bin/start_engine.sh embed

engine-lite:
	set -a; . config/profiles/lite-8gb.env; set +a; \
	./bin/start_engine.sh chat

engine-code:
	./bin/start_engine.sh coding

engine-deep:
	./bin/start_engine.sh deep

lint:
	$(VENV)/bin/black --check .
	$(VENV)/bin/ruff check .
	$(VENV)/bin/mypy core/

# ── Desktop one-click launch (see docs/guides/DESKTOP_ONE_CLICK_LAUNCH.md) ───

desktop-config:
	bash scripts/write_desktop_config.sh

desktop-launch:
	bash scripts/cerebro_desktop_launcher.sh

desktop-stop:
	bash scripts/cerebro_desktop_stop.sh

# Desktop .app build uses cerebro/ui/tray (icons + Tauri project live there).
desktop-icon desktop-app desktop-install:
	$(MAKE) -C cerebro $@

# ── Packaging (Module 13) ─────────────────────────────────────────────────────

package-backend:
	$(PIP) install pyinstaller>=6.0
	$(VENV)/bin/pyinstaller build/cerebro-backend.spec --distpath dist --noconfirm

package-macos: package-backend
	bash build/build_macos.sh

package-windows: package-backend
	powershell -ExecutionPolicy Bypass -File build/build_windows.ps1
