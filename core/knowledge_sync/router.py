from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.knowledge_sync.models import SyncResult, SyncSourceConfig

router = APIRouter(prefix="/api/knowledge-sync", tags=["knowledge-sync"])


class SyncTriggerPayload(BaseModel):
    force: bool = False
    source_id: str | None = None


class ImportPayload(BaseModel):
    version: int = 1
    sources: list[SyncSourceConfig] = []


def _get_orchestrator() -> Any:
    from ui.tray.server import app_state

    return app_state.knowledge_sync_orchestrator


@router.get("/sources")
async def list_sources() -> list[dict]:
    orch = _get_orchestrator()
    result: list[dict] = []
    for c in orch.list_sources():
        state = orch.get_state(c.id)
        result.append(
            {
                **vars(c),
                "status": state.status.value,
                "last_sync_at": state.last_sync_at,
                "last_error": state.last_error,
                "items_indexed": state.items_indexed_count,
            }
        )
    return result


@router.post("/sources")
async def add_source(config: SyncSourceConfig) -> dict:
    orch = _get_orchestrator()
    orch.add_source(config)
    return {"status": "ok", "id": config.id}


@router.delete("/sources/{source_id}")
async def remove_source(source_id: str) -> dict:
    orch = _get_orchestrator()
    orch.remove_source(source_id)
    return {"status": "ok"}


@router.post("/sync")
async def trigger_sync(payload: SyncTriggerPayload) -> dict:
    orch = _get_orchestrator()
    return await orch.trigger_sync(
        source_id=payload.source_id,
        force=payload.force,
    )


@router.post("/sync/{source_id}")
async def sync_one(source_id: str, force: bool = False) -> SyncResult:
    orch = _get_orchestrator()
    result = await orch.sync_one(source_id, force=force)
    if result.errors and not result.indexed:
        raise HTTPException(500, detail=result.errors[0])
    return result


@router.get("/sources/{source_id}/state")
async def source_state(source_id: str) -> dict:
    orch = _get_orchestrator()
    state = orch.get_state(source_id)
    return {
        "source_id": state.source_id,
        "status": state.status.value,
        "last_sync_at": state.last_sync_at,
        "last_error": state.last_error,
        "items_indexed": state.items_indexed_count,
    }


@router.post("/sync/stream")
async def trigger_sync_stream(payload: SyncTriggerPayload) -> StreamingResponse:
    orch = _get_orchestrator()
    source_id = payload.source_id
    force = payload.force
    send_queue: asyncio.Queue[str] = asyncio.Queue()

    async def _progress_cb(stage: str, data: dict) -> None:
        event = {"stage": stage, **data}
        await send_queue.put(f"event: progress\ndata: {json.dumps(event, ensure_ascii=False)}\n\n")

    async def _run_sync() -> None:
        try:
            if source_id:
                result = await orch.sync_one(source_id, force=force, progress_cb=_progress_cb)
                await send_queue.put(
                    f"event: complete\ndata: {json.dumps({'source_id': result.source_id, 'indexed': result.indexed, 'errors': result.errors}, ensure_ascii=False)}\n\n"
                )
            else:
                if force:
                    for sid in list(orch._sources.keys()):
                        result = await orch.sync_one(sid, force=True, progress_cb=_progress_cb)
                        await send_queue.put(
                            f"event: complete\ndata: {json.dumps({'source_id': result.source_id, 'indexed': result.indexed, 'errors': result.errors}, ensure_ascii=False)}\n\n"
                        )
                else:
                    results = await orch.sync_all()
                    for r in results:
                        await send_queue.put(
                            f"event: complete\ndata: {json.dumps({'source_id': r.source_id, 'indexed': r.indexed, 'errors': r.errors}, ensure_ascii=False)}\n\n"
                        )
        finally:
            await send_queue.put("event: done\ndata: [DONE]\n\n")

    async def _stream():
        task = asyncio.create_task(_run_sync())
        while True:
            msg = await send_queue.get()
            yield msg
            if msg.startswith("event: done"):
                task.cancel()
                break

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/export")
async def export_sources() -> dict:
    orch = _get_orchestrator()
    sources = []
    for c in orch.list_sources():
        sources.append(
            {
                "id": c.id,
                "source_type": c.source_type.value,
                "uri": c.uri,
                "label": c.label,
                "interval_minutes": c.interval_minutes,
                "tags": c.tags,
                "schedule_cron": c.schedule_cron,
            }
        )
    return {
        "version": 1,
        "exported_at": __import__("datetime")
        .datetime.now(__import__("datetime").timezone.utc)
        .isoformat(),
        "sources": sources,
    }


@router.post("/import")
async def import_sources(payload: ImportPayload) -> dict:
    orch = _get_orchestrator()
    added = 0
    errors: list[str] = []
    for src_cfg in payload.sources:
        try:
            orch.add_source(src_cfg)
            added += 1
        except ValueError as e:
            errors.append(f"{src_cfg.id}: {e}")
    return {"status": "ok", "added": added, "errors": errors}
