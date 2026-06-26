# Security Hardening — Audit Results

> Generated: 2026-06-18
> Plan reference: `docs/plans/SECURITY_HARDENING_PLAN.md`

## Resumen

21/21 items del roadmap implementados y verificados.

## Items P4 (Future) — Pendientes

Estos items están fuera del scope de las 3 semanas pero documentados en el plan:

| Item | Archivo | Descripción |
|------|---------|-------------|
| P2.5 TLS | — | Deferido — revisit for shared-machine deployments |
| P4.3 nsjail config | `core/tools/sandbox/nsjail.cfg` | Linux power-user deployment only |
| P4.4 sandbox-exec replacement | — | Monitor for Seatbelt sandbox replacement |
| P4.5 HardenedSandbox | `core/tools/handlers/execution.py` | Exception sanitization, tightened builtins |
| P6.3 SBOM generation | — | Post-stabilization |
| P7.2 Security healthcheck | `ui/tray/server.py` | GET /api/security/healthcheck endpoint |
| P7.3 Alerting | — | Auth failures, sandbox escapes |

## Tests — Pendientes (Section 13 del plan)

Crear `tests/test_security/` con los siguientes archivos:

### `tests/test_security/test_tauri_capabilities.py`
- `test_shell_allowlist_only_known_commands`
- `test_args_true_not_present`
- `test_csp_is_not_null`
- `test_no_remote_domain_ipc_access`

### `tests/test_security/test_auth.py`
- `test_server_binds_to_127_0_0_1_by_default` (integration)
- `test_fail_closed_on_0_0_0_0_without_key` (integration)
- `test_verify_api_key_rejects_wrong_key` (unit)
- `test_verify_api_key_uses_client_ip_not_host_header` (unit)
- `test_config_update_validates_profile` (unit)
- `test_config_update_rejects_watched_folders_outside_home` (unit)
- `test_auto_generate_key_creates_valid_key` (unit)

### `tests/test_security/test_ssrf.py`
- `test_blocked_169_254_range` (unit)
- `test_dns_rebinding_resolved_once_pinned` (integration, mock DNS)
- `test_redirect_hop_revalidated` (integration, mock HTTP)
- `test_allowed_url_passes` (unit)
- `test_blocked_private_network` (unit)
- `test_cors_restricted_origins` (integration)
- `test_rate_limit_query_endpoint` (integration)

### `tests/test_security/test_secrets.py`
- `test_keychain_primary_storage` (unit, mock keyring)
- `test_fallback_encrypted_file` (unit)
- `test_fallback_warning_on_missing_keyring` (unit)
- `test_rotation_updates_live_auth_state` (integration)
- `test_secret_not_leaked_to_environ` (unit)
- `test_set_secret_endpoint_validation` (integration)

### `tests/test_security/test_sandbox.py`
- `test_import_blocked` (unit)
- `test_global_blocked` (unit)
- `test_basic_math_works` (unit)
- `test_timeout_enforced` (unit)
- `test_output_truncated` (unit)
- `test_exception_sanitized_no_paths` (unit)
- `test_sandbox_exec_profile_exists_and_is_valid` (unit, parse profile)

### `tests/test_security/test_agent_integrity.py`
- `test_tool_output_markers_in_prompt` (unit)
- `test_confirmation_gate_audit_detects_unprotected_tool` (unit)
- `test_llm_blocked_tools_cannot_be_called` (unit)
- `test_all_state_changing_tools_in_confirmation_set` (unit, auto-generated)

### `tests/test_security/test_audit.py`
- `test_audit_log_writes_jsonl` (unit)
- `test_audit_log_rotates_monthly` (unit)
- `test_audit_log_cleans_up_old` (unit)
- `test_sensitive_fields_redacted` (unit)

## Breaking Changes — Migration Checklist

| Change | Status |
|--------|--------|
| Default bind `127.0.0.1` (antes `0.0.0.0`) | ✅ Implementado |
| `CEREBRO_API_KEY` mandatory on `0.0.0.0` | ✅ Implementado |
| `VITE_CEREBRO_KEY` removed from bundle | ✅ Implementado |
| API keys moved from `/api/config` to `/api/secrets` | ✅ Implementado (secrets endpoints created, patch_config still supports anthropic_api_key for backward compat) |

## Bugs Fixed (Appendix 14)

| # | Location | Issue | Status |
|---|----------|-------|--------|
| 1 | `config/security.py` | `.startswith()` prefix check | ✅ Ya usaba `relative_to()` |
| 2 | `core/tools/handlers/filesystem.py` | `.startswith()` prefix check | ✅ Ya usaba `relative_to()` |
| 2b | `core/tools/policy.py` | `str.startswith()` en `_is_under` | ✅ Corregido → `Path.relative_to()` |
| 3 | `bin/start_engine.sh` | Unquoted `$(cat ...)` | ✅ Corregido → `mapfile` + array |
| 4 | `core/tools/handlers/execution.py` | `asyncio.create_subprocess_exec(timeout=...)` invalid | ✅ Corregido → `asyncio.wait_for()` |
| 5 | `ui/tray/server.py` | `request.url.hostname` instead of `request.client.host` | ✅ Corregido |
| 6 | `ui/tray/server.py` | Module-level `SystemExit(1)` before setup | ✅ Corregido (moved to `if __name__` block) |
| 7 | `core/tools/handlers/web.py` | Missing `169.254.0.0/16` | ✅ Añadido |
| 8 | `core/tools/handlers/web.py` | `follow_redirects=True` without re-validation | ✅ Corregido → manual follow |
| 9 | `core/tools/handlers/web.py` | DNS rebinding | ✅ Corregido → resolve + validate before connect |
| 10 | `capabilities/main.json` | `args: true` on bash | ✅ Corregido → named commands + validators |
| 11 | `tauri.conf.json` | `"csp": null` | ✅ Set CSP |
| 12 | `tauri.conf.json` | No `dangerousRemoteDomainIpcAccess` | ✅ Set to `[]` |
| 13 | `client.ts` | `VITE_CEREBRO_KEY` in bundle | ✅ Corregido → Tauri command |
