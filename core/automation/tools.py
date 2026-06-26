"""Tool handler factories for Desktop Automation.

Each function returns a callable that closes over its dependencies.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from core.automation.generalizer import GeneralizationError
from core.automation.service import (
    RecordingConflictError,
    RecordingUnavailableError,
    TooFewEventsError,
    run_workflow,
    start_recording,
    stop_and_create_workflow,
)


def make_start_recording(recorder: Any) -> Any:
    """Return a handler that starts the recorder."""

    async def _start(
        recorder: Any = recorder,
    ) -> str:
        try:
            start_recording(recorder)
        except RecordingUnavailableError as exc:
            return f"Error: {exc.error_key}"
        except RecordingConflictError:
            return "La grabación ya está en curso."
        return "Grabación iniciada. Realiza las acciones que quieras automatizar."

    return _start


def make_stop_recording(recorder: Any, workflow_store: Any, chat_provider_getter: Any) -> Any:
    """Return a handler that stops recording and generalises events."""

    async def _stop(
        recorder: Any = recorder,
        workflow_store: Any = workflow_store,
        chat_provider_getter: Any = chat_provider_getter,
    ) -> str:
        try:
            wf = await stop_and_create_workflow(
                recorder,
                workflow_store,
                chat_provider_getter,
            )
        except RecordingUnavailableError as exc:
            return f"Error: {exc.error_key}"
        except RecordingConflictError:
            return "Error: no hay ninguna grabación en curso."
        except TooFewEventsError as exc:
            return (
                f"Grabación detenida — solo {exc.count} eventos capturados. "
                "Se necesitan al menos 3 acciones para generar un workflow."
            )
        except GeneralizationError as exc:
            logger.exception("Workflow generalization failed")
            return f"Error al generalizar: {exc}"
        except Exception as exc:
            logger.exception("Unexpected error during generalization")
            return f"Error inesperado: {exc}"

        return (
            f"Workflow creado: '{wf['name']}' (ID: {wf['id']})\n"
            f"Descripción: {wf['description']}\n"
            f"Parámetros: {len(wf['parameters'])}\n"
            f"Etiquetas: {', '.join(wf['tags'])}\n\n"
            f"Puedes ejecutarlo con: 'ejecuta workflow {wf['id']}'"
        )

    return _stop


def make_run_workflow(workflow_store: Any) -> Any:
    """Return a handler that executes a saved workflow."""

    async def _run(
        workflow_id: str,
        workflow_store: Any = workflow_store,
        params: dict[str, str] | None = None,
    ) -> str:
        payload = await run_workflow(workflow_store, workflow_id, params)
        return payload["result"]

    return _run
