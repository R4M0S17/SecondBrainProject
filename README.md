# Cerebro (SecondBrain)

Local-first agentic personal OS — Python backend (FastAPI) + React/Tauri desktop UI.

## Quick start

```bash
make install
make engine    # llama.cpp on :8080
make run       # API on :7842
```

See **[`docs/guides/howToRun.md`](docs/guides/howToRun.md)** for full setup (8 GB Mac: [`docs/guides/8gb-mac-quickstart.md`](docs/guides/8gb-mac-quickstart.md)).

## Documentation

| What you need | Where to look |
|---------------|---------------|
| **Full index** | [`docs/README.md`](docs/README.md) |
| **Agent / dev reference** | [`CLAUDE.md`](CLAUDE.md) |
| **Architecture deep-dive** | [`docs/architecture/program-overview.md`](docs/architecture/program-overview.md) |
| **Stabilization & fix plans** | [`docs/plans/`](docs/plans/) |
| **Manual QA logs** | [`manual_tests/README.md`](manual_tests/README.md) |

## Repository layout

```
core/              Python backend
ui/tray/           React + Tauri frontend
docs/              Canonical documentation
manual_tests/      Manual E2E notes and smoke reports
config/            llama.cpp profiles and env templates
tests/             pytest (mocked inference)
```
