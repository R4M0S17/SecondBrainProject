hello, what day is today?
Today is Wednesday
Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf · 29.4s
what is todays date
Wednesday, MAY 20,  10:17 AM
Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf · 12.9s
what are u capable of and how much ram do i need to run u?
I am a languageist personal designed to assist with tasks, provide information, and perform actions within the specified's capabilities.
Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf · 17.8s
con qué tareas puedes ayudarme?
No tienes t paras específicas que necesjasme ayudar hoy.
Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf · 16.7s
que fecha es hoy?
Wednesday, May 20,6
Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf · 5.2s
con qué me puedes ayudar?
Today es Wednesday, May 20,2026.
Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf · 14.1s
de que eres capaz?
The current date and time are Wednesday, May 20, at 1::22 PM EDT.
Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf · 13.0s
puedes crear un archivo python con texto “Hello"
No pude interpretar la respuesta del modelo. Intenta reformular tu pregunta.
Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf · 15.5s
crea un archivo python con texto “Hello"
Creando un archivo Python llamado 'hello.py.pyunto.py' exista el archivo 'helloasas.py', se sobreescri sobre él.
Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf · 16.1s





terminal 2:
mb@MacBook-Pro-de-M ~ % cd /Users/mb/Desktop/Javier/SecondBrain
  set -a
  . config/profiles/lite-8gb.env
  set +a
  make run
.venv/bin/python main.py
2026-05-20 10:15:04.007 | INFO     | __main__:_build_app_state:102 - Fleet: Selected smollm2-360m-q8 (0.36B, Q8_0) for medium task
2026-05-20 10:15:04.007 | INFO     | __main__:_build_app_state:145 - llamacpp mode: simple=True (set CEREBRO_LLAMACPP_SIMPLE=false for model swapping)
2026-05-20 10:15:04.007 | INFO     | __main__:_build_app_state:171 - Inference: llama.cpp simple → http://127.0.0.1:8080
2026-05-20 10:15:04.007 | INFO     | __main__:_build_app_state:221 - Embeddings: local (dim=384, embed server not required when backend=local)
2026-05-20 10:15:04.314 | INFO     | __main__:_build_app_state:264 - Filesystem authorized read paths: ['/Users/mb/Desktop/Javier/SecondBrain', '/Users/mb/Desktop/CerebroFiles']
2026-05-20 10:15:04.314 | INFO     | __main__:_build_app_state:265 - Filesystem authorized write paths: ['/Users/mb/Desktop/CerebroFiles']
2026-05-20 10:15:04.326 | WARNING  | core.agents.state_store:list_agents:183 - Skipping unreadable agent file: config.json
2026-05-20 10:15:04.327 | WARNING  | core.agents.state_store:list_agents:183 - Skipping unreadable agent file: wizard.json
INFO:     Started server process [95815]
INFO:     Waiting for application startup.
/Users/mb/Desktop/Javier/SecondBrain/.venv/lib/python3.14/site-packages/lancedb/__init__.py:294: UserWarning: lance is not fork-safe. If you are using multiprocessing, use spawn instead.
  warnings.warn(
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:7842 (Press CTRL+C to quit)
2026-05-20 10:15:06.012 | INFO     | core.inference.health_monitor:_run_loop:170 - Llama-server is up at http://127.0.0.1:8080
INFO:     127.0.0.1:65325 - "OPTIONS /api/wizard/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65326 - "OPTIONS /api/wizard/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65325 - "GET /api/wizard/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65326 - "GET /api/wizard/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65325 - "OPTIONS /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65326 - "OPTIONS /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65325 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65326 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65329 - "OPTIONS /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65330 - "OPTIONS /api/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:65331 - "OPTIONS /api/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:65325 - "GET /api/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:65326 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65329 - "GET /api/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:65325 - "OPTIONS /api/models HTTP/1.1" 200 OK
INFO:     127.0.0.1:65326 - "OPTIONS /api/llama-cpp/models HTTP/1.1" 200 OK
INFO:     127.0.0.1:65325 - "GET /api/models HTTP/1.1" 200 OK
INFO:     127.0.0.1:65326 - "GET /api/llama-cpp/models HTTP/1.1" 200 OK
INFO:     127.0.0.1:65338 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65339 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65340 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65345 - "OPTIONS /api/query/stream HTTP/1.1" 200 OK
INFO:     127.0.0.1:65345 - "POST /api/query/stream HTTP/1.1" 200 OK
2026-05-20 10:16:33.998 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.49 GB
INFO:     127.0.0.1:65346 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65347 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65348 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:16:44.015 | WARNING  | core.cache.embedding_cache:_embed_with_retry:352 - Embedding timeout on attempt 1 (waited 10s), retrying in 0.5s
INFO:     127.0.0.1:65376 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65377 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65378 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:16:46.295 | INFO     | core.inference.providers.local_embedding_provider:_load_model:43 - Loading local embedding model sentence-transformers/all-MiniLM-L6-v2 on mps
2026-05-20 10:16:46.295 | INFO     | core.inference.providers.local_embedding_provider:_load_model:43 - Loading local embedding model sentence-transformers/all-MiniLM-L6-v2 on mps
Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
Loading weights: 100%|██████████████████████| 103/103 [00:00<00:00, 5361.56it/s]
Loading weights: 100%|██████████████████████| 103/103 [00:00<00:00, 6884.56it/s]
2026-05-20 10:16:48.419 | INFO     | core.cache.embedding_cache:_embed_with_retry:347 - Embedding provider recovered after 1 retries
/Users/mb/Desktop/Javier/SecondBrain/.venv/lib/python3.14/site-packages/lancedb/__init__.py:294: UserWarning: lance is not fork-safe. If you are using multiprocessing, use spawn instead.
  warnings.warn(
2026-05-20 10:16:51.525 | WARNING  | core.agents.context_enricher:enrich:193 - ContextEnricher.enrich timed out after 3s (handlers exceeded timeout)
2026-05-20 10:16:51.530 | DEBUG    | core.agents.runtime:_context_assembly_node:774 - Micro-route: agent=calendar-v1 tools_in_prompt=['get_upcoming_events', 'query_events', 'search_upcoming', 'create_calendar_event', 'add_reminder', 'send_notification']
2026-05-20 10:16:51.531 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.33 GB
INFO:     127.0.0.1:65386 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65387 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65388 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:17:03.355 | INFO     | core.inference.context_usage:log_context_usage:36 - Context usage: 1143/4096 (source=usage.total_tokens)
2026-05-20 10:17:03.356 | DEBUG    | core.agents.runtime:_reason_node_streaming:836 - Reason node raw response: {
  "action": "answer",
   "answer": "Today is Wednesday"
}
INFO:     127.0.0.1:65345 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65391 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65345 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65391 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65394 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65401 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65402 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65403 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65401 - "POST /api/query/stream HTTP/1.1" 200 OK
2026-05-20 10:17:19.304 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.20 GB
2026-05-20 10:17:23.467 | WARNING  | core.agents.context_enricher:enrich:193 - ContextEnricher.enrich timed out after 3s (handlers exceeded timeout)
2026-05-20 10:17:23.470 | DEBUG    | core.agents.runtime:_context_assembly_node:774 - Micro-route: agent=calendar-v1 tools_in_prompt=['get_upcoming_events', 'query_events', 'search_upcoming', 'create_calendar_event', 'add_reminder', 'send_notification']
2026-05-20 10:17:23.471 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.33 GB
INFO:     127.0.0.1:65408 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65409 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65410 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:17:32.211 | INFO     | core.inference.context_usage:log_context_usage:36 - Context usage: 1146/4096 (source=usage.total_tokens)
2026-05-20 10:17:32.211 | DEBUG    | core.agents.runtime:_reason_node_streaming:836 - Reason node raw response: {"action": "answer", "answer": "Wednesday, MAY 20,  10:17 AM"}
INFO:     127.0.0.1:65401 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65413 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65413 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65401 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65416 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65423 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65424 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65425 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65432 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65433 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65434 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:18:03.641 | WARNING  | core.agents.llm_router:classify:61 - LLMRouter: unexpected response 'technical', falling back to general
INFO:     127.0.0.1:65438 - "POST /api/query/stream HTTP/1.1" 200 OK
2026-05-20 10:18:03.647 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.18 GB
INFO:     127.0.0.1:65441 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65442 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65443 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:18:06.896 | WARNING  | core.agents.context_enricher:enrich:193 - ContextEnricher.enrich timed out after 3s (handlers exceeded timeout)
2026-05-20 10:18:06.900 | DEBUG    | core.agents.runtime:_context_assembly_node:774 - Micro-route: agent=general-v1 tools_in_prompt=['get_upcoming_events', 'query_events', 'search_upcoming', 'create_calendar_event', 'add_reminder', 'read_file', 'write_file', 'list_directory', 'search_files', 'spotlight_search', 'search_notes', 'evaluate_math']
2026-05-20 10:18:06.901 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.27 GB
INFO:     127.0.0.1:65448 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65449 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65450 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:18:21.452 | INFO     | core.inference.context_usage:log_context_usage:36 - Context usage: 1273/4096 (source=usage.total_tokens)
2026-05-20 10:18:21.452 | DEBUG    | core.agents.runtime:_reason_node_streaming:836 - Reason node raw response: {"action": "answer", "answer": "I am a languageist personal designed to assist with tasks, provide information, and perform actions within the specified's capabilities. "}
INFO:     127.0.0.1:65438 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65453 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65438 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65453 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65456 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65463 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65464 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65465 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65472 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65474 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65475 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65482 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65483 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65484 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:18:58.107 | WARNING  | core.agents.llm_router:classify:61 - LLMRouter: unexpected response 'technical', falling back to general
INFO:     127.0.0.1:65482 - "POST /api/query/stream HTTP/1.1" 200 OK
2026-05-20 10:18:58.112 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.20 GB
2026-05-20 10:19:01.567 | WARNING  | core.agents.context_enricher:enrich:193 - ContextEnricher.enrich timed out after 3s (handlers exceeded timeout)
2026-05-20 10:19:01.572 | DEBUG    | core.agents.runtime:_context_assembly_node:774 - Micro-route: agent=general-v1 tools_in_prompt=['get_upcoming_events', 'query_events', 'search_upcoming', 'create_calendar_event', 'add_reminder', 'read_file', 'write_file', 'list_directory', 'search_files', 'spotlight_search', 'search_notes', 'evaluate_math']
2026-05-20 10:19:01.574 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.23 GB
INFO:     127.0.0.1:65490 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65491 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65492 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:19:14.782 | INFO     | core.inference.context_usage:log_context_usage:36 - Context usage: 1257/4096 (source=usage.total_tokens)
2026-05-20 10:19:14.782 | DEBUG    | core.agents.runtime:_reason_node_streaming:836 - Reason node raw response: {"action": "answer", "answer": "No tienes t paras específicas que necesjasme ayudar hoy."   }
INFO:     127.0.0.1:65482 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65496 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65482 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65496 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65499 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65506 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65507 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65508 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65515 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65516 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65517 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65515 - "POST /api/query/stream HTTP/1.1" 200 OK
2026-05-20 10:19:39.202 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.20 GB
2026-05-20 10:19:42.453 | WARNING  | core.agents.context_enricher:enrich:193 - ContextEnricher.enrich timed out after 3s (handlers exceeded timeout)
2026-05-20 10:19:42.457 | DEBUG    | core.agents.runtime:_context_assembly_node:774 - Micro-route: agent=general-v1 tools_in_prompt=['get_upcoming_events', 'query_events', 'search_upcoming', 'create_calendar_event', 'add_reminder', 'read_file', 'write_file', 'list_directory', 'search_files', 'spotlight_search', 'search_notes', 'evaluate_math']
2026-05-20 10:19:42.458 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.25 GB
2026-05-20 10:19:44.405 | INFO     | core.inference.context_usage:log_context_usage:36 - Context usage: 1245/4096 (source=usage.total_tokens)
2026-05-20 10:19:44.405 | DEBUG    | core.agents.runtime:_reason_node_streaming:836 - Reason node raw response: {"action": "answer", "answer": "Wednesday, May 20,6"}
INFO:     127.0.0.1:65515 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65521 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65515 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65521 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65524 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65531 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:65532 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:65533 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49154 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49157 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49158 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49169 - "OPTIONS /api/fleet/models HTTP/1.1" 200 OK
INFO:     127.0.0.1:49170 - "OPTIONS /api/fleet/models HTTP/1.1" 200 OK
INFO:     127.0.0.1:49169 - "GET /api/fleet/models HTTP/1.1" 200 OK
INFO:     127.0.0.1:49170 - "GET /api/fleet/models HTTP/1.1" 200 OK
INFO:     127.0.0.1:49169 - "PATCH /api/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:49169 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49170 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49172 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49169 - "OPTIONS /api/fleet/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:49169 - "PATCH /api/fleet/config HTTP/1.1" 400 Bad Request
INFO:     127.0.0.1:49179 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49180 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49181 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49179 - "PATCH /api/fleet/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:49179 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49179 - "PATCH /api/fleet/config HTTP/1.1" 400 Bad Request
INFO:     127.0.0.1:49179 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49185 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49186 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49191 - "PATCH /api/fleet/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:49191 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49191 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49192 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49193 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49200 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49201 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49202 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49209 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49210 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49211 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49215 - "POST /api/query/stream HTTP/1.1" 200 OK
2026-05-20 10:21:14.001 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.20 GB
INFO:     127.0.0.1:49217 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49218 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49219 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:21:17.959 | WARNING  | core.agents.context_enricher:enrich:193 - ContextEnricher.enrich timed out after 3s (handlers exceeded timeout)
2026-05-20 10:21:17.963 | DEBUG    | core.agents.runtime:_context_assembly_node:774 - Micro-route: agent=code-v1 tools_in_prompt=['read_file', 'write_file', 'create_directory', 'list_directory', 'search_files', 'create_python_file', 'run_script', 'delete_file', 'evaluate_math']
2026-05-20 10:21:17.964 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.24 GB
INFO:     127.0.0.1:49224 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49225 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49226 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:21:28.065 | INFO     | core.inference.context_usage:log_context_usage:36 - Context usage: 883/4096 (source=usage.total_tokens)
2026-05-20 10:21:28.066 | DEBUG    | core.agents.runtime:_reason_node_streaming:836 - Reason node raw response: {
  "action": "answer",
  "answer": "Today es Wednesday, May 20,2026."
}
INFO:     127.0.0.1:49215 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49224 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49234 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49235 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49236 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49243 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49244 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49245 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49276 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49277 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49278 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49276 - "POST /api/query/stream HTTP/1.1" 200 OK
2026-05-20 10:21:57.821 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.23 GB
2026-05-20 10:22:01.073 | WARNING  | core.agents.context_enricher:enrich:193 - ContextEnricher.enrich timed out after 3s (handlers exceeded timeout)
2026-05-20 10:22:01.078 | DEBUG    | core.agents.runtime:_context_assembly_node:774 - Micro-route: agent=code-v1 tools_in_prompt=['read_file', 'write_file', 'create_directory', 'list_directory', 'search_files', 'create_python_file', 'run_script', 'delete_file', 'evaluate_math']
2026-05-20 10:22:01.078 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.24 GB
INFO:     127.0.0.1:49283 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49284 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49285 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:22:10.810 | INFO     | core.inference.context_usage:log_context_usage:36 - Context usage: 893/4096 (source=usage.total_tokens)
2026-05-20 10:22:10.811 | DEBUG    | core.agents.runtime:_reason_node_streaming:836 - Reason node raw response: {"action": "answer", "answer": "The current date and time are Wednesday, May 20, at 1::22 PM EDT."}
INFO:     127.0.0.1:49276 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49283 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49294 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49295 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49296 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49303 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49304 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49305 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49313 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49314 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49315 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49322 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49323 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49324 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49322 - "POST /api/query/stream HTTP/1.1" 200 OK
2026-05-20 10:22:46.249 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.14 GB
2026-05-20 10:22:49.891 | WARNING  | core.agents.context_enricher:enrich:193 - ContextEnricher.enrich timed out after 3s (handlers exceeded timeout)
2026-05-20 10:22:49.896 | DEBUG    | core.agents.runtime:_context_assembly_node:774 - Micro-route: agent=general-v1 tools_in_prompt=['get_upcoming_events', 'query_events', 'search_upcoming', 'create_calendar_event', 'add_reminder', 'read_file', 'write_file', 'list_directory', 'search_files', 'spotlight_search', 'search_notes', 'evaluate_math']
2026-05-20 10:22:49.897 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.21 GB
INFO:     127.0.0.1:49329 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49330 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49331 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:23:01.740 | INFO     | core.inference.context_usage:log_context_usage:36 - Context usage: 1245/4096 (source=usage.total_tokens)
2026-05-20 10:23:01.741 | DEBUG    | core.agents.runtime:_reason_node_streaming:836 - Reason node raw response: {
  "action": "answer",
 "answer": " "}
2026-05-20 10:23:01.741 | WARNING  | core.agents.runtime:_parse_llm_response:384 - LLM answer action with empty answer field
INFO:     127.0.0.1:49322 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49334 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49322 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49334 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49337 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49344 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49345 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49346 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49344 - "POST /api/query/stream HTTP/1.1" 200 OK
2026-05-20 10:23:16.521 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.14 GB
2026-05-20 10:23:19.735 | WARNING  | core.agents.context_enricher:enrich:193 - ContextEnricher.enrich timed out after 3s (handlers exceeded timeout)
2026-05-20 10:23:19.740 | DEBUG    | core.agents.runtime:_context_assembly_node:774 - Micro-route: agent=general-v1 tools_in_prompt=['get_upcoming_events', 'query_events', 'search_upcoming', 'create_calendar_event', 'add_reminder', 'read_file', 'write_file', 'list_directory', 'search_files', 'spotlight_search', 'search_notes', 'evaluate_math']
2026-05-20 10:23:19.741 | DEBUG    | core.inference.registry:select_for_task:117 - RAM available: 1.25 GB
INFO:     127.0.0.1:49351 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49352 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49353 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:23:32.652 | INFO     | core.inference.context_usage:log_context_usage:36 - Context usage: 1274/4096 (source=usage.total_tokens)
2026-05-20 10:23:32.652 | DEBUG    | core.agents.runtime:_reason_node_streaming:836 - Reason node raw response: {"action": "answer", "answer": "Creando un archivo Python llamado 'hello.py.pyunto.py' exista el archivo 'helloasas.py', se sobreescri sobre él. "  }
INFO:     127.0.0.1:49344 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49356 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49356 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49344 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49359 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49366 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49367 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49368 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49375 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49376 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49377 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49384 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49385 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49386 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:24:16.317 | DEBUG    | core.inference.providers.llamacpp_provider:is_available:114 - llama-server unavailable at http://127.0.0.1:8080
INFO:     127.0.0.1:49392 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49394 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49395 - "GET /api/fleet/status HTTP/1.1" 200 OK
2026-05-20 10:24:20.952 | WARNING  | core.inference.health_monitor:_run_loop:178 - Llama-server missed 2 pings — recovering
2026-05-20 10:24:21.114 | WARNING  | core.inference.health_monitor:_attempt_restart:156 - Llama-server restarting (attempt 1 this session)
2026-05-20 10:24:26.140 | INFO     | core.inference.health_monitor:_run_loop:170 - Llama-server is up at http://127.0.0.1:8080
INFO:     127.0.0.1:49401 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49403 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49404 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49420 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49422 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49423 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49420 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49422 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49423 - "GET /api/fleet/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49492 - "GET /api/wizard/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49420 - "GET /api/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:49420 - "GET /api/models HTTP/1.1" 200 OK
INFO:     127.0.0.1:49422 - "GET /api/llama-cpp/models HTTP/1.1" 200 OK
INFO:     127.0.0.1:49502 - "GET /api/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49503 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:49504 - "GET /api/fleet/status HTTP/1.1" 200 OK
^CINFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [95815]


RAM average 7.35