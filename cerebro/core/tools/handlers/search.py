from __future__ import annotations

from core.rag.query_engine import RAGQueryEngine


async def search_documents(query: str, rag_engine: RAGQueryEngine) -> str:
    response = await rag_engine.query(query)
    sources = ", ".join(response.sources) if response.sources else "none"
    return f"{response.answer}\n\n[Sources: {sources}]"
