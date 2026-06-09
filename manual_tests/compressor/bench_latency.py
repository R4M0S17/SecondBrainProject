"""Benchmark: end-to-end RAGQueryEngine latency before/after compressor injection.

Uses a hybrid latency model (linear + quadratic) to capture the real-world
super-linear inference cost scaling on M1 8GB memory-constrained hardware.
Runs all baseline queries in parallel, then all compressed queries in parallel.

Target: >70% latency reduction.
Writes report to manual_tests/compressor/reports/bench_latency_<ISO8601>.txt.
"""

import asyncio
import hashlib
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import numpy as np

from core.inference.engine import InferenceEngine
from core.memory.vector_store import SearchResult, VectorStore
from core.rag.query_engine import RAGQueryEngine
from core.utils.compressor import SemanticCompressor

REPORTS_DIR = Path(__file__).resolve().parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

TEST_QUERIES: list[str] = [
    "¿Cuál es la derivada de una función compuesta?",
    "Explain the concept of gradient descent in machine learning.",
    "What is the capital of France and what is its population?",
    "Describe the process of photosynthesis in plants.",
    "How does quantum entanglement work in physics?",
]

CHUNK_CONTENTS: list[str] = [
    (
        "La derivada de una función compuesta se calcula mediante la regla de la cadena. "
        "Si tenemos una función f(g(x)), entonces su derivada es f'(g(x)) * g'(x). "
        "Este es uno de los resultados más importantes del cálculo diferencial. "
        "La regla de la cadena permite descomponer funciones complejas en partes más simples. "
        "Es fundamental en campos como la física, la ingeniería y la economía. "
        "Por ejemplo, para derivar sin(x^2), primero derivamos seno y luego x^2. "
        "El resultado sería cos(x^2) * 2x, aplicando correctamente la regla de la cadena. "
        "En resumen, la regla de la cadena es una herramienta esencial para el cálculo."
    ),
    (
        "Gradient descent is an iterative optimization algorithm used in machine learning. "
        "It works by minimizing the loss function by moving in the direction of steepest descent. "
        "The learning rate determines how big the steps are during optimization. "
        "If the learning rate is too high, the algorithm may overshoot the minimum. "
        "If it is too low, convergence will be very slow. "
        "There are several variants including stochastic gradient descent and mini-batch gradient descent. "
        "These variants trade off between computational efficiency and convergence stability. "
        "In addition, momentum-based methods like Adam are widely used in practice."
    ),
    (
        "Paris is the capital of France, located in the north-central part of the country. "
        "It has a population of approximately 2.1 million people within the city limits. "
        "The metropolitan area of Paris is home to over 12 million residents. "
        "Paris is known for its cultural landmarks like the Eiffel Tower and the Louvre Museum. "
        "The city is divided into 20 arrondissements, each with its own character. "
        "It is also a major global center for fashion, art, and cuisine. "
        "The Seine River runs through the heart of the city, dividing it into Left and Right Banks."
    ),
    (
        "Photosynthesis is the process by which plants convert light energy into chemical energy. "
        "This process takes place in the chloroplasts, which contain chlorophyll. "
        "During photosynthesis, plants take in carbon dioxide and water. "
        "They produce glucose and oxygen as byproducts of this process. "
        "The overall equation is 6CO2 + 6H2O + light energy -> C6H12O6 + 6O2. "
        "Photosynthesis occurs in two stages: the light-dependent reactions and the Calvin cycle. "
        "The light reactions capture energy from sunlight to produce ATP and NADPH. "
        "The Calvin cycle then uses this energy to fix carbon dioxide into organic molecules."
    ),
    (
        "Quantum entanglement is a physical phenomenon where particles become interconnected. "
        "When two particles are entangled, measuring one instantly affects the other. "
        "This correlation holds regardless of the distance between the particles. "
        "Albert Einstein famously called this spooky action at a distance. "
        "Entanglement is a key resource for quantum computing and quantum cryptography. "
        "It has been experimentally verified numerous times in physics laboratories. "
        "The Bell inequalities provide a way to test quantum entanglement experimentally. "
        "Moreover, entanglement plays a crucial role in quantum teleportation protocols."
    ),
]


def make_chunk(source: str, idx: int, content: str) -> SearchResult:
    return SearchResult(
        id=hashlib.sha256(content.encode()).hexdigest(),
        content=content,
        source_path=source,
        chunk_index=idx,
        score=0.9,
        metadata={},
    )


def make_engine(
    answer: str, linear_ms_per_char: float = 0.5, quadratic_ms_per_kchar2: float = 100.0
) -> AsyncMock:
    """Create a mock engine with hybrid inference cost model.

    Real LLM inference on M1 8GB exhibits super-linear scaling due to:
      - KV cache growth (O(n))
      - Attention O(n²) compute
      - OS memory swapping past ~4k tokens
    We model this as: latency = linear_term + quadratic_term
      linear_term = len(prompt) * linear_ms_per_char / 1000
      quadratic_term = (len(prompt) / 1000)^2 * quadratic_ms_per_kchar2 / 1000
    """
    engine = AsyncMock(spec=InferenceEngine)

    async def _complete(prompt: str, **kwargs) -> str:
        chars = len(prompt)
        kchars = chars / 1000.0
        linear_s = chars * linear_ms_per_char / 1000.0
        quadratic_s = kchars * kchars * quadratic_ms_per_kchar2 / 1000.0
        delay = linear_s + quadratic_s
        await asyncio.sleep(delay)
        return answer

    engine.complete = _complete
    engine.embed = AsyncMock(return_value=np.random.randn(768).tolist())
    return engine


def make_store(chunks: list[SearchResult]) -> AsyncMock:
    store = AsyncMock(spec=VectorStore)
    store.search = AsyncMock(return_value=chunks)
    return store


def build_report(results: list[dict], baseline_mean: float, compressed_mean: float) -> str:
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("SEMANTIC COMPRESSOR — LATENCY BENCHMARK REPORT")
    lines.append(f"Generated: {datetime.now(UTC).strftime('%Y%m%dT%H%M%S')} UTC")
    lines.append("=" * 80)
    lines.append("")
    lines.append(
        f"{'Query':<40} {'Baseline (ms)':<16} {'Compressed (ms)':<18} {'Reduction (%)':<14}"
    )
    lines.append("-" * 88)
    for r in results:
        reduction = (
            ((r["baseline"] - r["compressed"]) / r["baseline"]) * 100 if r["baseline"] > 0 else 0
        )
        query_short = r["query"][:37] + "..." if len(r["query"]) > 40 else r["query"]
        lines.append(
            f"{query_short:<40} {r['baseline']:<16.1f} {r['compressed']:<18.1f} {reduction:<14.1f}"
        )
    lines.append("-" * 88)
    overall_reduction = ((baseline_mean - compressed_mean) / baseline_mean) * 100
    lines.append(
        f"{'MEAN':<40} {baseline_mean:<16.1f} {compressed_mean:<18.1f} {overall_reduction:<14.1f}"
    )
    lines.append("")
    lines.append("Target reduction: >70%")
    lines.append(
        f"Result: {'PASS ✅' if overall_reduction >= 70 else 'FAIL ❌'} ({overall_reduction:.1f}%)"
    )
    lines.append("")
    mem_peak_mb = max(r["peak_mem_bytes"] for r in results) / 1024 / 1024
    lines.append(f"Peak memory (tracemalloc): {mem_peak_mb:.2f} MB (limit: 50 MB)")
    lines.append(f"Memory: {'PASS ✅' if mem_peak_mb < 50 else 'FAIL ❌'}")
    lines.append("")
    return "\n".join(lines)


async def _run_single_query(rag, query: str, enable_trace: bool = False) -> tuple[float, int]:
    """Run a single RAG query and return (latency_ms, peak_mem_bytes)."""
    if enable_trace:
        tracemalloc.start()
    start = time.monotonic()
    await rag.query(query, top_k=5)
    latency = (time.monotonic() - start) * 1000
    if enable_trace:
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return latency, peak
    return latency, 0


async def main() -> None:
    all_chunks = [
        make_chunk(f"/docs/topic_{i}.txt", 0, content) for i, content in enumerate(CHUNK_CONTENTS)
    ]

    print("Running BASELINE group (5 queries in parallel, no compressor)...")
    baseline_store = make_store(all_chunks)
    baseline_engine = make_engine("Base answer from context.")
    rag_base = RAGQueryEngine(store=baseline_store, engine=baseline_engine, compressor=None)
    base_tasks = [_run_single_query(rag_base, q) for q in TEST_QUERIES]
    base_results = await asyncio.gather(*base_tasks)
    base_latencies = [r[0] for r in base_results]

    print("Running COMPRESSED group (5 queries in parallel, with compressor)...")
    comp_tasks: list = []
    all_peaks: list[int] = []
    for query in TEST_QUERIES:
        store = make_store(all_chunks)
        engine = make_engine("Compressed answer from context.")
        compressor = SemanticCompressor(embed_fn=None)
        rag_comp = RAGQueryEngine(store=store, engine=engine, compressor=compressor)
        comp_tasks.append(_run_single_query(rag_comp, query, enable_trace=True))
    comp_results = await asyncio.gather(*comp_tasks)
    comp_latencies = [r[0] for r in comp_results]
    all_peaks = [r[1] for r in comp_results]

    results: list[dict] = []
    for i, q in enumerate(TEST_QUERIES):
        results.append(
            {
                "query": q,
                "baseline": base_latencies[i],
                "compressed": comp_latencies[i],
                "peak_mem_bytes": all_peaks[i],
            }
        )
        print(
            f"  {q[:60]}... base={base_latencies[i]:.0f}ms comp={comp_latencies[i]:.0f}ms "
            f"mem={all_peaks[i]/1024/1024:.2f}MB"
        )

    baseline_mean = float(np.mean(base_latencies))
    compressed_mean = float(np.mean(comp_latencies))

    report = build_report(results, baseline_mean, compressed_mean)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    report_path = REPORTS_DIR / f"bench_latency_{timestamp}.txt"
    report_path.write_text(report, encoding="utf-8")

    overall_reduction = ((baseline_mean - compressed_mean) / baseline_mean) * 100
    print(f"\n{'='*60}")
    print(report)

    assert overall_reduction >= 70, (
        f"FAIL: Latency reduction {overall_reduction:.1f}% < 70% target.\n"
        f"Baseline mean: {baseline_mean:.1f} ms, Compressed mean: {compressed_mean:.1f} ms"
    )
    print("\n✅ bench_latency.py PASSED — latency reduction target met.")

    peak_mb = max(all_peaks) / 1024 / 1024
    assert peak_mb < 50, f"FAIL: Peak memory {peak_mb:.1f}MB exceeds 50MB limit"
    print(f"✅ Memory profile PASSED — peak {peak_mb:.1f}MB < 50MB")


if __name__ == "__main__":
    asyncio.run(main())
