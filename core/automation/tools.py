"""Tool handler factories for Desktop Automation.

Each function returns a callable that closes over its dependencies.
"""

from __future__ import annotations

import subprocess
from typing import Any

from loguru import logger


def make_start_recording(recorder: Any) -> Any:
    """Return a handler that starts the recorder."""

    async def _start(
        recorder: Any = recorder,
    ) -> str:
        if recorder is None:
            return "Error: Desktop Recorder no disponible (pyobjc no instalado)"
        if recorder.is_recording:
            return "La grabación ya está en curso."
        recorder.start()
        return "Grabación iniciada. Realiza las acciones que quieras automatizar."

    return _start


def make_stop_recording(recorder: Any, workflow_store: Any, chat_provider_getter: Any) -> Any:
    """Return a handler that stops recording and generalises events."""

    async def _stop(
        recorder: Any = recorder,
        workflow_store: Any = workflow_store,
        chat_provider_getter: Any = chat_provider_getter,
    ) -> str:
        if recorder is None:
            return "Error: Desktop Recorder no disponible."
        if not recorder.is_recording:
            return "Error: no hay ninguna grabación en curso."

        events = recorder.stop()
        if len(events) < 3:
            return (
                f"Grabación detenida — solo {len(events)} eventos capturados. "
                "Se necesitan al menos 3 acciones para generar un workflow."
            )

        from core.automation.generalizer import GeneralizationError, generalize_events

        provider = chat_provider_getter() if callable(chat_provider_getter) else None
        if provider is None:
            return "Error: no hay proveedor de inferencia disponible."

        try:
            result = await generalize_events(events, provider)
        except GeneralizationError as exc:
            logger.exception("Workflow generalization failed")
            return f"Error al generalizar: {exc}"
        except Exception as exc:
            logger.exception("Unexpected error during generalization")
            return f"Error inesperado: {exc}"

        if workflow_store is None:
            return "Error: workflow store no disponible."

        wid = workflow_store.save(
            name=result["name"],
            applescript=result["applescript"],
            description=result["description"],
            parameters=result["parameters"],
            tags=result["tags"],
        )

        return (
            f"Workflow creado: '{result['name']}' (ID: {wid})\n"
            f"Descripción: {result['description']}\n"
            f"Parámetros: {len(result['parameters'])}\n"
            f"Etiquetas: {', '.join(result['tags'])}\n\n"
            f"Puedes ejecutarlo con: 'ejecuta workflow {wid}'"
        )

    return _stop


def make_run_workflow(workflow_store: Any) -> Any:
    """Return a handler that executes a saved workflow."""

    async def _run(
        workflow_id: str,
        workflow_store: Any = workflow_store,
    ) -> str:
        if workflow_store is None:
            return "Error: workflow store no disponible."

        wf = workflow_store.get(workflow_id)
        if wf is None:
            return f"Error: workflow '{workflow_id}' no encontrado."

        applescript = wf["applescript"]

        try:
            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=30.0,
            )
            workflow_store.increment_run_count(workflow_id)
            if result.returncode != 0:
                return f"Error ejecutando workflow: {result.stderr.strip()}"
            output = result.stdout.strip()
            return (
                f"Workflow ejecutado correctamente.\n{output}"
                if output
                else "Workflow ejecutado correctamente."
            )
        except subprocess.TimeoutExpired:
            return "Error: el workflow excedió el tiempo máximo (30s)."
        except Exception as exc:
            logger.exception("Workflow execution failed")
            return f"Error ejecutando workflow: {exc}"

    return _run
