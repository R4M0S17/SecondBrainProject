# Documentation index

Canonical technical docs live under **`docs/`** at the repository root (not under `cerebro/`).

| Area | Path | Contents |
|------|------|----------|
| **Architecture & ops** | [`../CLAUDE.md`](../CLAUDE.md) | Stack overview, make targets, env vars, REST API sketch |
| **Connection checklist** | [`connection/progress.md`](connection/progress.md) | Backend ↔ frontend wiring modules and smoke-test notes |
| **HTTP / API usage** | [`connection/api-guide.md`](connection/api-guide.md) | REST examples |
| **Runbooks** | [`guides/howToRun.md`](guides/howToRun.md) · [`guides/running-es.md`](guides/running-es.md) · [`guides/llamacpp-run-guide.md`](guides/llamacpp-run-guide.md) | English / Spanish startup, llama.cpp notes |
| **Inference** | [`inference/`](inference/) | llama.cpp, MLX, RAM notes |
| **Frontend** | [`frontend/`](frontend/) | Design, roadmap, pending changes |
| **Product / spec** | [`project/`](project/) | Specs, current state, Obsidian inspiration |
| **Model efficiency experiment** | [`testing/`](testing/) | PLAN, EXECUTION_GUIDE, QUICK_START, EXPERIMENTAL_SUMMARY |
| **Pytest remediation (known failures)** | [`testing/PYTEST_REMEDIATION_PATH.md`](testing/PYTEST_REMEDIATION_PATH.md) | Ordered fixes for fleet monitor / phase7 args / planner parsing |
| **Issues & playbook** | [`PROJECT_ISSUES_AND_SOLUTIONS.md`](PROJECT_ISSUES_AND_SOLUTIONS.md) | Long-form troubleshooting ledger |

Supporting material elsewhere:

- **`features/`** — integration plans (e.g. Claude API, fleet orchestrator)
- **`bugs/`** — incident write-ups and migration logs
- **`roadmaps/`** — phased optimization notes
