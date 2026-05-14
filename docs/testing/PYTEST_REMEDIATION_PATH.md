# Pytest remediation path — fleet monitor, phase 7 args, planner parsing

Use this sequence when the suite reports failures like **6 failed** in `test_fleet_hardware_monitor`, `test_phase7_advanced`, and `test_planner`.

## Step 1 — `test_fleet_hardware_monitor` (psutil / sysctl)

**Cause:** On sandboxed or hardened macOS, `psutil.cpu_count()` can raise `PermissionError` or surface as `SystemError` from the sysctl path.

**Fix:** In `core/inference/fleet/hardware_monitor.py`, wrap CPU probes in `try/except` for `(OSError, PermissionError, SystemError)` and fall back to `cpu_count = 1` and `cpu_percent = 0.0`.

**Verify:** `pytest tests/test_fleet_hardware_monitor.py -q`

---

## Step 2 — `test_phase7_advanced` (prompt cache layout)

**Cause:** Tests expect `bin/cache/` to exist and each llama.cpp profile args file to mention `--prompt-cache`.

**Fix:**

1. Ensure `bin/cache/` exists and is tracked (e.g. `bin/cache/.gitkeep`).
2. Add a `--prompt-cache bin/cache/<profile>.prompt.gguf` line to `config/chat.args`, `config/coding.args`, and `config/deep.args` (and mirrored `cerebro/config/*.args` if you keep that tree in sync).

**Verify:** `pytest tests/test_phase7_advanced.py::test_prompt_cache_dir_exists tests/test_phase7_advanced.py::test_args_files_contain_prompt_cache -q`

---

## Step 3 — `test_planner` (`_parse_step_response`)

**Cause:**

- Bracket scanning returned the **first** valid JSON array (`["Step A"]`) instead of a **richer** array later in the string.
- **`[]`** satisfied “list of strings” vacuously and was returned instead of **`None`**.

**Fix:** In `core/agents/planner.py`, inside `_parse_step_response`:

1. For direct JSON and fenced JSON, require `len(obj) > 0` before returning.
2. For bracket fragments, collect every valid non-empty string array and `return max(candidates, key=len)`.

**Verify:** `pytest tests/test_planner.py::test_parse_step_response_greedy_brackets tests/test_planner.py::test_parse_step_response_empty_array -q`

---

## Full slice

```bash
make test tests/test_fleet_hardware_monitor.py tests/test_phase7_advanced.py tests/test_planner.py
```

(Or `pytest` with the same paths using `.venv/bin/python`.)
