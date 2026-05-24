#!/usr/bin/env python3
"""Re-embed LanceDB tables after switching embedding backends or dimensions.

Usage (from repo root):
    .venv/bin/python scripts/reindex_embeddings.py
    .venv/bin/python scripts/reindex_embeddings.py --db ~/.cerebro/db --drop
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Repo root on sys.path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import lancedb  # noqa: E402

from core.inference.embedding_factory import build_embedding_provider  # noqa: E402
from core.memory.long_term import LongTermStore  # noqa: E402
from core.memory.vector_store import vector_schema  # noqa: E402


async def _reindex_documents(db_path: str, provider, *, drop: bool) -> int:
    db = lancedb.connect(db_path)
    dim = provider.dimensions()
    table_name = "documents"
    if drop and table_name in db.table_names():
        db.drop_table(table_name)
    if table_name not in db.table_names():
        return 0

    table = db.open_table(table_name)
    rows = table.to_arrow().to_pylist()
    if not rows:
        return 0

    db.drop_table(table_name)
    fresh = db.create_table(table_name, schema=vector_schema(dim))
    updated = []
    for row in rows:
        content = row["content"]
        vector = await provider.embed(content)
        updated.append({**row, "vector": vector})
    fresh.add(updated)
    return len(updated)


async def _reindex_agent_memory(db_path: str, provider, *, drop: bool) -> int:
    db = lancedb.connect(db_path)
    dim = provider.dimensions()
    table_name = LongTermStore.TABLE_NAME
    if drop and table_name in db.table_names():
        db.drop_table(table_name)
    if table_name not in db.table_names():
        return 0

    from core.memory.long_term import agent_memory_schema

    table = db.open_table(table_name)
    rows = table.to_arrow().to_pylist()
    if not rows:
        return 0

    db.drop_table(table_name)
    fresh = db.create_table(table_name, schema=agent_memory_schema(dim))
    updated = []
    for row in rows:
        content = row["content"]
        vector = await provider.embed(content)
        updated.append({**row, "vector": vector})
    fresh.add(updated)
    return len(updated)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Re-embed LanceDB after backend change")
    parser.add_argument(
        "--db",
        default=os.path.expanduser(os.getenv("CEREBRO_DB", "~/.cerebro/db")),
        help="LanceDB directory",
    )
    args = parser.parse_args()
    drop = True

    provider = build_embedding_provider(
        embed_url=os.getenv("CEREBRO_LLAMACPP_EMBED_URL", "http://127.0.0.1:8082"),
    )
    print(f"Embedding backend: {provider.name} (dim={provider.dimensions()})")

    doc_count = await _reindex_documents(args.db, provider, drop=drop)
    mem_count = await _reindex_agent_memory(args.db, provider, drop=drop)
    print(f"Re-indexed {doc_count} document chunks and {mem_count} agent-memory rows.")


if __name__ == "__main__":
    asyncio.run(main())
