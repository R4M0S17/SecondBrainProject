# 8 GB Mac quick start

One-page path to a working Cerebro on a memory-constrained Mac (for example MacBook Pro M1 with 8 GB unified RAM).

> Nota: Desarrollo en un MacBook Pro M1 (8 GB). En mi experiencia, con los modelos actuales funciona muy bien; tiempos de respuesta observados ≈ 20–40 segundos.

## 1. Install once

From the repository root:

```bash
make install
```

This creates the virtual environment, installs Python dependencies, and sets up pre-commit.

## 2. Run with the lite profile

Prefer the bundled lite env so chat stays within the 8 GB budget:

```bash
make engine-lite
```

In a second terminal:

```bash
make lite
```

Equivalent manual flow:

```bash
cp config/profiles/lite-8gb.env .env
make engine
make run
```

`make lite` / the profile file set `CEREBRO_MLX_ENABLED=false`, simple llama.cpp mode, and conservative RAM thresholds. See `config/profiles/lite-8gb.env` for the exact variables.

## 3. Calendar Automation (macOS)

For calendar questions to return real events, grant **Automation → Calendar** to the Python process that runs the backend (often **Terminal** or **iTerm** if you start `make lite` from there).

Path: **System Settings → Privacy & Security → Automation** (or open **Privacy & Security** and use the Automation section). Enable **Calendar** for your terminal app or for **Python** if listed.

The first-launch wizard also surfaces a reminder with **Open Settings** when the probe is not `ok`.

## 4. Confirm the API is healthy

With the backend listening on port **7842**:

```text
http://localhost:7842/api/status
```

Check JSON fields:

- `ram_pressure` should be **`ok`** under normal desktop load. If it reads `warn` or `critical`, close other heavy apps or stay on `make lite` + `make engine-lite`.
- `macos_permissions.calendar` should be **`ok`** after Automation is granted (`unknown` or `denied` means calendar tools may not see events).

## 5. Smoke questions (Spanish)

In the UI or via `POST /api/query`:

1. `¿Qué día es hoy?` — answer should reflect the real current date.
2. `¿Cuál es mi próximo evento?` — should list an upcoming event or an explicit empty/permission message, not a silent hallucination.

## 6. If something fails

Run the diagnostics (aggregate runner):

```bash
bash scripts/diag/doctor.sh; echo "exit=$?"
```

Or individually:

```bash
python scripts/diag/snapshot.py
python scripts/diag/check_models.py
python scripts/diag/check_calendar.py
python scripts/diag/check_routing.py
```

Paste the full output into a new issue. For missing chat GGUF files, the doctor script hints at `python scripts/download_model.py llama` when appropriate.

---

See also: [`docs/README.md`](../README.md), root [`CLAUDE.md`](../../CLAUDE.md), and [`docs/plans/stabilization/fix-cerebro.md`](../../docs/plans/stabilization/fix-cerebro.md) for the full remediation plan.
