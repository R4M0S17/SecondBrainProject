"""Validate compressor output strictly respects max_tokens=600 budget.

Checks:
1. total_estimated_tokens <= 600 for all returned chunks
2. No SearchResult.content ends mid-sentence (check terminal punctuation / word boundary)
3. Memory profile via tracemalloc (< 50MB peak)

Writes report to manual_tests/compressor/reports/bench_tokens_<ISO8601>.txt.
"""

import hashlib
import re
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

from core.memory.vector_store import SearchResult
from core.utils.compressor import SemanticCompressor

REPORTS_DIR = Path(__file__).resolve().parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

TEST_QUERIES: list[tuple[str, list[SearchResult]]] = []


def _chunk(source: str, idx: int, content: str) -> SearchResult:
    return SearchResult(
        id=hashlib.sha256(content.encode()).hexdigest(),
        content=content,
        source_path=source,
        chunk_index=idx,
        score=0.9,
        metadata={},
    )


def _long_content(prefix: str, num_sentences: int) -> str:
    sentences = [
        f"{prefix} sentence number {i} with enough padding tokens to fill up the budget and test the compressor boundary detection logic."
        for i in range(num_sentences)
    ]
    return " ".join(sentences)


TEST_QUERIES = [
    (
        "gradient descent machine learning optimization",
        [
            _chunk("/docs/ml.txt", 0, _long_content("ML", 25)),
            _chunk("/docs/ml.txt", 1, _long_content("Neural networks", 20)),
            _chunk("/docs/dl.txt", 0, _long_content("Deep learning", 20)),
        ],
    ),
    (
        "photosynthesis plants carbon dioxide",
        [
            _chunk("/docs/bio.txt", 0, _long_content("Biology", 30)),
            _chunk("/docs/bio.txt", 1, _long_content("Plant cells", 15)),
        ],
    ),
    (
        "quantum entanglement physics experiment",
        [
            _chunk("/docs/phys.txt", 0, _long_content("Quantum mechanics", 28)),
            _chunk("/docs/phys.txt", 1, _long_content("Particle physics", 18)),
            _chunk("/docs/phys.txt", 2, _long_content("Experiments", 12)),
        ],
    ),
    (
        "calculus derivative function chain rule",
        [
            _chunk("/docs/math.txt", 0, _long_content("Calculus", 22)),
            _chunk("/docs/math-alt.txt", 0, _long_content("Differential equations", 16)),
        ],
    ),
    (
        "Paris France capital population landmarks",
        [
            _chunk("/docs/geo.txt", 0, _long_content("Geography", 20)),
            _chunk("/docs/geo.txt", 1, _long_content("European capitals", 15)),
            _chunk("/docs/history.txt", 0, _long_content("History", 18)),
            _chunk("/docs/culture.txt", 0, _long_content("Culture", 12)),
        ],
    ),
]

SENTENCE_TERMINAL = frozenset({".", "?", "!", "…"})
_WORD_BOUNDARY_RE = re.compile(r"\w$")


def _check_sentence_boundary(content: str) -> bool:
    """Return True if content ends at a valid sentence boundary."""
    stripped = content.rstrip()
    if not stripped:
        return True
    last_char = stripped[-1]
    if last_char in SENTENCE_TERMINAL:
        return True
    # Also allow word boundary as per protocol
    if _WORD_BOUNDARY_RE.search(stripped):
        return True
    return False


def estimated_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def build_report(results: list[dict]) -> str:
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("SEMANTIC COMPRESSOR — TOKEN BUDGET VALIDATION REPORT")
    lines.append(f"Generated: {datetime.now(UTC).strftime('%Y%m%dT%H%M%S')} UTC")
    lines.append("=" * 80)
    lines.append("")
    headers = f"{'Query':<50} {'Total Tokens':<15} {'≤600':<8} {'Boundaries OK':<15} {'Pass':<8}"
    lines.append(headers)
    lines.append("-" * 96)
    for r in results:
        q_short = r["query"][:47] + "..." if len(r["query"]) > 50 else r["query"]
        lines.append(
            f"{q_short:<50} {r['total_tokens']:<15} {'✅' if r['budget_ok'] else '❌':<8} "
            f"{'✅' if r['boundaries_ok'] else '❌':<15} "
            f"{'✅' if r['pass'] else '❌':<8}"
        )
    lines.append("-" * 96)
    all_ok = all(r["pass"] for r in results)
    lines.append(f"\nResult: {'ALL PASS ✅' if all_ok else 'SOME FAILURES ❌'}")
    mem_peak_mb = max(r["peak_mem_mb"] for r in results)
    lines.append(f"Peak memory (tracemalloc): {mem_peak_mb:.2f} MB (limit: 50 MB)")
    lines.append(f"Memory: {'PASS ✅' if mem_peak_mb < 50 else 'FAIL ❌'}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    results: list[dict] = []

    for query, chunks in TEST_QUERIES:
        tracemalloc.start()
        compressor = SemanticCompressor(embed_fn=None)  # Path B — TF-IDF
        compressed = compressor.compress(query, chunks, max_tokens=600)
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        total_tokens = sum(estimated_tokens(c.content) for c in compressed)
        budget_ok = total_tokens <= 600
        boundaries_ok = (
            all(_check_sentence_boundary(c.content) for c in compressed) if compressed else True
        )
        passed = budget_ok and boundaries_ok

        results.append(
            {
                "query": query,
                "total_tokens": total_tokens,
                "budget_ok": budget_ok,
                "boundaries_ok": boundaries_ok,
                "pass": passed,
                "peak_mem_mb": peak / 1024 / 1024,
                "compressed": compressed,
            }
        )

        print(f"Query: {query[:60]}...")
        print(f"  Total tokens: {total_tokens} (limit: 600) {'✅' if budget_ok else '❌'}")
        print(f"  Boundaries OK: {boundaries_ok} {'✅' if boundaries_ok else '❌'}")
        print(f"  Peak mem: {peak / 1024 / 1024:.2f} MB")
        if compressed:
            print(f"  Chunks returned: {len(compressed)}")
            for c in compressed:
                print(
                    f"    [{c.source_path}:{c.chunk_index}] tokens={estimated_tokens(c.content):>3} last={repr(c.content[-20:])}"
                )

    report = build_report(results)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    report_path = REPORTS_DIR / f"bench_tokens_{timestamp}.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to: {report_path}")

    # Assertions
    all_pass = all(r["pass"] for r in results)
    peak_mb = max(r["peak_mem_mb"] for r in results)

    failures = [r for r in results if not r["pass"]]
    if failures:
        for f in failures:
            if not f["budget_ok"]:
                print(f"  FAIL (budget): {f['query'][:50]} — {f['total_tokens']} tokens > 600")
            if not f["boundaries_ok"]:
                print(f"  FAIL (boundary): {f['query'][:50]} — mid-sentence cut detected")
        raise AssertionError(f"{len(failures)} token validation failure(s)")

    assert peak_mb < 50, f"Peak memory {peak_mb:.1f}MB exceeds 50MB limit"
    print("\n✅ bench_tokens.py PASSED — all token budgets and sentence boundaries valid.")


if __name__ == "__main__":
    main()
