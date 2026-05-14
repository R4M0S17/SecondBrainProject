# FIX_CEREBRO migration — phase index
Each phase has its own branch `fix-N-<slug>` and ends with an exit gate.

- **Phase 0** — `fix-0-triage` — triage log + `scripts/diag/*` *(DONE)*
- **Phase 1** — `fix-1-ram-containment` — 8 GB-safe defaults *(DONE)*
- **Phase 2** — `fix-2-tools-routing` — general tools + stream tool loop + Auto default + regex router *(DONE)*
- **Phase 3** — `fix-3-date-correctness` — `_date_preamble()` on LLM user turns + REGLA TEMPORAL + `tests/test_runtime_date_correctness.py` *(DONE)*
- **Phase 4** — `fix-4-calendar-perms` — `BackendResult` + 5s Apple read + `macos_perms` probe + status + async enricher + proactive default on *(DONE)*
