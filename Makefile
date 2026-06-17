.PHONY: install setup test smoke run lint lite engine engine-embed engine-lite engine-code engine-deep desktop-config desktop-launch desktop-icon desktop-app desktop-install package-backend package-macos package-windows

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	$(VENV)/bin/pre-commit install

setup:
	bash scripts/setup.sh

test:
	$(PYTHON) -m pytest tests/ -v --cov=core --cov-fail-under=80

test-stable:
	$(PYTHON) -m pytest tests/test_stable_fast_paths.py tests/test_file_write_fast_path.py tests/test_file_write_calendar_fusion.py tests/test_calendar_fast_path.py tests/test_file_search_fast_path.py tests/test_math_fast_path.py -v -m "not live" --tb=short

smoke:
	$(PYTHON) -m pytest tests/test_smoke_live.py -v --tb=short

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

# Desktop .app build (ui/tray — Tauri project).
desktop-icon:
	cd ui/tray && npm run tauri -- icon app-icon.png

DESKTOP_APP := ui/tray/src-tauri/target/release/bundle/macos/Cerebro.app
DESKTOP_DMG := ui/tray/src-tauri/target/release/bundle/dmg

desktop-app: desktop-config
	cd ui/tray && npm run build
	cd ui/tray && CARGO_TARGET_DIR="$(CURDIR)/ui/tray/src-tauri/target" npm run tauri:build:release
	@test -d "$(DESKTOP_APP)" || (echo "Build finished but $(DESKTOP_APP) not found." >&2; exit 1)
	@echo ""
	@echo "Built: $(DESKTOP_APP)"
	@ls -1 "$(DESKTOP_DMG)"/*.dmg 2>/dev/null && echo "DMG:   $(DESKTOP_DMG)/" || true
	@echo "Install: make desktop-install"

desktop-install:
	@test -d "$(DESKTOP_APP)" || (echo "Run make desktop-app first." >&2; exit 1)
	cp -R "$(DESKTOP_APP)" /Applications/
	@echo "Installed → /Applications/Cerebro.app"
	@echo "Open from Applications or Spotlight; Keep in Dock from the app icon menu."

# ── Packaging (Module 13) ─────────────────────────────────────────────────────

package-backend:
	$(PIP) install pyinstaller>=6.0
	$(VENV)/bin/pyinstaller build/cerebro-backend.spec --distpath dist --noconfirm

package-macos: package-backend
	bash build/build_macos.sh

package-windows: package-backend
	powershell -ExecutionPolicy Bypass -File build/build_windows.ps1
