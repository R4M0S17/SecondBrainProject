"""Module 8 — Specialized Agents.

Three pre-configured agent profiles with prefix-based routing (fast path)
and optional LLM-based intent classification (slow path via SmolLM2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from core.agents.state_store import AgentProfile, AgentState, AgentStateStore

if TYPE_CHECKING:
    from core.agents.llm_router import LLMRouter

# ──────────────────────────────────────────────────────────────────────────────
# Well-known agent IDs — stable across sessions (stored on disk by these keys)
# ──────────────────────────────────────────────────────────────────────────────

ACADEMIC_AGENT_ID = "academic-v1"
CALENDAR_AGENT_ID = "calendar-v1"
CODE_AGENT_ID = "code-v1"
GENERAL_AGENT_ID = "general-v1"

# Tool authorizations per spec
ACADEMIC_TOOLS: list[str] = [
    "search_documents",
    "read_file",
    "write_file",
    "create_note",
    # Phase 1 & 3: filesystem read + Notes/Spotlight
    "list_directory",
    "search_files",
    "search_notes",
    "spotlight_search",
]
CALENDAR_TOOLS: list[str] = [
    "search_documents",
    "get_upcoming_events",
    "query_events",
    "search_upcoming",
    "create_calendar_event",
    "add_reminder",
    # Phase 3: desktop notification after creating events
    "send_notification",
]
CODE_TOOLS: list[str] = [
    "search_documents",
    "read_file",
    "execute_python",
    # Phase 1 & 2: filesystem + script execution
    "create_python_file",
    "run_script",
    "delete_file",
    "list_directory",
    "search_files",
    "create_directory",
]
# Read-only, low-risk tools the general agent may use without confirmation
GENERAL_TOOLS: list[str] = [
    "get_upcoming_events",
    "query_events",
    "search_upcoming",
    "search_documents",
    "spotlight_search",
    "list_directory",
    "search_files",
    "search_notes",
]

_PREFIX_MAP: dict[str, str] = {
    "/academic": ACADEMIC_AGENT_ID,
    "/calendar": CALENDAR_AGENT_ID,
    "/code": CODE_AGENT_ID,
}

_LLM_CATEGORY_MAP: dict[str, str] = {
    "code": CODE_AGENT_ID,
    "calendar": CALENDAR_AGENT_ID,
    "academic": ACADEMIC_AGENT_ID,
    "general": GENERAL_AGENT_ID,
}


# ──────────────────────────────────────────────────────────────────────────────
# Profile factories
# ──────────────────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(UTC).isoformat()


def make_academic_profile() -> AgentProfile:
    now = _now()
    return AgentProfile(
        id=ACADEMIC_AGENT_ID,
        name="Asistente Académico",
        domain_tags=["academic", "notes", "learning"],
        authorized_tools=ACADEMIC_TOOLS,
        preferences={
            "instructions": (
                "Eres un asistente académico. Tu objetivo es organizar notas, "
                "crear resúmenes claros, generar quizzes y conectar conceptos "
                "entre documentos. Prioriza la precisión y la síntesis."
            )
        },
        created_at=now,
        updated_at=now,
    )


def make_code_profile() -> AgentProfile:
    now = _now()
    return AgentProfile(
        id=CODE_AGENT_ID,
        name="Asistente de Código",
        domain_tags=["code", "development", "debugging"],
        authorized_tools=CODE_TOOLS,
        preferences={
            "instructions": (
                "Eres un asistente de código. Responde preguntas sobre la base "
                "de código, sugiere refactorizaciones y genera snippets cuando "
                "sea útil. Ejecuta código solo para verificar lógica, nunca para "
                "acceder a recursos externos."
            )
        },
        created_at=now,
        updated_at=now,
    )


def make_calendar_profile() -> AgentProfile:
    now = _now()
    return AgentProfile(
        id=CALENDAR_AGENT_ID,
        name="Asistente de Calendario",
        domain_tags=["calendar", "scheduling", "tasks", "reminders"],
        authorized_tools=CALENDAR_TOOLS,
        preferences={
            "instructions": (
                "Eres un asistente de calendario y gestión de tareas. "
                "Puedes consultar eventos, recordatorios y tareas usando las herramientas disponibles.\n"
                "IMPORTANTE: Cuando respondas sobre fechas u horas, incluye SIEMPRE el día, "
                "mes, año y hora completos. Nunca respondas solo el nombre del día sin el año y mes.\n\n"
                "REGLA ANTI-BUCLE: Llama a una herramienta UNA SOLA VEZ por consulta. "
                "Si el resultado dice 'Sin eventos', responde directamente con esa información. "
                "NO repitas la llamada con una ventana de tiempo más grande.\n\n"
                "Para ver eventos de hoy/mañana:\n"
                '{"action": "tool", "tool": "get_upcoming_events", "args": {"hours_ahead": 48}}\n'
                "Para ver la semana completa:\n"
                '{"action": "tool", "tool": "get_upcoming_events", "args": {"hours_ahead": 168}}\n'
                "Para el evento o cumpleaños MÁS CERCANO (próximo año):\n"
                '{"action": "tool", "tool": "get_upcoming_events", "args": {"hours_ahead": 8760}}\n'
                "Para buscar por palabra clave (ej: 'reunión', 'cumple', 'doctor'):\n"
                '{"action": "tool", "tool": "query_events", "args": {"keyword": "reunión", "hours_ahead": 8760}}\n'
                "Para el próximo cumpleaños (puede estar a meses vista):\n"
                '{"action": "tool", "tool": "search_upcoming", "args": {"keyword": "cumple", "days_ahead": 365}}\n'
                "NOTA: Los cumpleaños se guardan como eventos recurrentes anuales. "
                "Para buscar cumpleaños usa query_events con keyword='cumple' y hours_ahead=8760.\n\n"
                "Para crear una reunión o cita:\n"
                '{"action": "tool", "tool": "create_calendar_event", "args": {"title": "Reunión equipo", "datetime_str": "next monday at 3pm", "duration_mins": 60}}\n'
                "Para añadir un recordatorio:\n"
                '{"action": "tool", "tool": "add_reminder", "args": {"title": "Llamar al médico", "datetime_str": "next saturday at 9am"}}\n'
                "USA create_calendar_event para: reuniones, citas, bloquear tiempo.\n"
                "USA add_reminder para: 'recuérdame', 'no olvidar', tareas con fecha.\n"
                "Responde de forma clara y en el idioma del usuario."
            )
        },
        created_at=now,
        updated_at=now,
    )


def make_general_profile() -> AgentProfile:
    now = _now()
    _general_extra = (
        "Si el usuario pregunta por la fecha, hora, eventos, cumpleaños, recordatorios o "
        "cualquier dato que cambie con el tiempo, USA herramientas — NO inventes la respuesta. "
        'Para "qué día es hoy" o "qué hora es" mira la línea FECHA Y HORA ACTUAL del prompt. '
        "Para eventos del calendario usa get_upcoming_events; para cumpleaños usa "
        'query_events con keyword="cumple" o search_upcoming con keyword="cumple".'
    )
    return AgentProfile(
        id=GENERAL_AGENT_ID,
        name="Asistente General",
        domain_tags=["general"],
        authorized_tools=GENERAL_TOOLS,
        preferences={
            "instructions": (
                "Eres un asistente personal. Responde preguntas, gestiona "
                "documentos y ejecuta acciones con prudencia. Para acciones de "
                "escritura, confirma antes de proceder cuando tengas dudas.\n\n" + _general_extra
            )
        },
        created_at=now,
        updated_at=now,
    )


_PROFILE_FACTORIES = [
    (make_academic_profile, ACADEMIC_AGENT_ID),
    (make_calendar_profile, CALENDAR_AGENT_ID),
    (make_code_profile, CODE_AGENT_ID),
    (make_general_profile, GENERAL_AGENT_ID),
]


# ──────────────────────────────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class RouteResult:
    agent_id: str
    query: str  # stripped of any command prefix


class SpecializedAgentRouter:
    """Route a raw user input to the appropriate agent profile.

    Prefix detection is the fast path. If no prefix matches and an LLMRouter
    is provided, SmolLM2 classifies the intent (slow path).
    """

    def __init__(self, llm_router: LLMRouter | None = None) -> None:
        self._llm_router = llm_router

    def route(self, raw_input: str) -> RouteResult:
        stripped = raw_input.strip()
        for prefix, agent_id in _PREFIX_MAP.items():
            if stripped.startswith(prefix + " ") or stripped == prefix:
                query = stripped[len(prefix) :].strip()
                return RouteResult(agent_id=agent_id, query=query or stripped)
        return RouteResult(agent_id=GENERAL_AGENT_ID, query=stripped)

    async def route_with_llm(self, raw_input: str) -> RouteResult:
        """Prefix routing first; falls back to LLM classification if no prefix matches."""
        prefix_result = self.route(raw_input)
        if prefix_result.agent_id != GENERAL_AGENT_ID:
            return prefix_result
        if self._llm_router is not None:
            category = await self._llm_router.classify(raw_input)
            agent_id = _LLM_CATEGORY_MAP.get(category, GENERAL_AGENT_ID)
            return RouteResult(agent_id=agent_id, query=prefix_result.query)
        return prefix_result

    def ensure_profiles(self, store: AgentStateStore) -> None:
        """Seed default profiles and keep existing ones in sync with factory defaults.

        Creates missing agents. For agents that already exist, updates authorized_tools
        and instructions if they differ from the factory — preserving all session state
        (session_summary, tool_trace, execution_count, etc.).
        """
        existing: dict[str, AgentState] = {p.id: store.load(p.id) for p in store.list_agents()}
        for factory, agent_id in _PROFILE_FACTORIES:
            canonical = factory()
            if agent_id not in existing:
                state = AgentState(
                    profile=canonical,
                    session_summary="",
                    working_memory={},
                    tool_trace=[],
                    semantic_memory_refs=[],
                    execution_count=0,
                    last_active=canonical.created_at,
                )
                store.save(state)
            else:
                state = existing[agent_id]
                stale = (
                    state.profile.authorized_tools != canonical.authorized_tools
                    or state.profile.preferences.get("instructions")
                    != canonical.preferences.get("instructions")
                )
                if stale:
                    state.profile.authorized_tools = canonical.authorized_tools
                    state.profile.preferences["instructions"] = canonical.preferences.get(
                        "instructions", ""
                    )
                    store.save(state)
