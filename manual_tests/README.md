# Manual tests & E2E notes

Human-driven chat sessions, smoke reports, and fix verification — not automated pytest.

## Layout

| Folder | Contents |
|--------|----------|
| [`implemefix/`](implemefix/) | ImplemeFIX baseline, smoke report, sessions 1–2, fix plans, tray transcript |
| [`sessions/`](sessions/) | Dated frontend chat logs (master session index) |
| [`diagnoses/`](diagnoses/) | Root-cause analysis tied to a session |
| [`e2e/`](e2e/) | Per-feature E2E fix notes (calendar, file write, reminders) |
| [`fixtures/`](fixtures/) | ICS and helpers for calendar E2E |
| [`logs/`](logs/) | Live reminder test JSONL output |

## Recommended reading order

1. [`implemefix/baseline-before.md`](implemefix/baseline-before.md) — pre-change metrics  
2. [`implemefix/post-smoke.md`](implemefix/post-smoke.md) — `make smoke` after ImplemeFIX  
3. [`sessions/frontend_chat_qwen3_2026-05-24.md`](sessions/frontend_chat_qwen3_2026-05-24.md) — latest session checklist  
4. [`e2e/`](e2e/) — individual fix write-ups linked from that session  

## Commands

```bash
make smoke          # writes/updates implemefix/post-smoke.md
scripts/live_reminder_test.sh   # logs → logs/_live_reminder_results.jsonl
.venv/bin/python scripts/test_file_write_llamacpp.py   # file write + calendar export fusion (live llama.cpp)
pytest tests/test_file_write_calendar_fusion.py -q
```

## Feature status (2026-05-25)

| Feature | Doc | Estado |
|---------|-----|--------|
| Export calendario → archivo | [`e2e/calendar_file_export_fusion_2026-05-25.md`](e2e/calendar_file_export_fusion_2026-05-25.md) | **DONE** |
| Escritura inteligente (literal/spec/fences) | [`e2e/file_write_smart_e2e_2026-05-24.md`](e2e/file_write_smart_e2e_2026-05-24.md) | **DONE** |
| Fast path calendario lectura | [`e2e/calendar_fast_path_e2e_2026-05-24.md`](e2e/calendar_fast_path_e2e_2026-05-24.md) | **DONE** |

Automated tests live in [`../tests/`](../tests/).
