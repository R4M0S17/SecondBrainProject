"""Validate that source_path and chunk_index are never mutated by the compressor.

Protocol:
1. Retrieve raw chunks for a test query
2. Record original lineage {(source_path, chunk_index)}
3. Run compressor.compress(query, chunks)
4. Assert compressed lineage is a subset of original

Writes report to manual_tests/compressor/reports/validate_lineage_<ISO8601>.txt.
"""

import hashlib
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

from core.memory.vector_store import SearchResult
from core.utils.compressor import SemanticCompressor

REPORTS_DIR = Path(__file__).resolve().parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Test queries with varied lineage patterns
TEST_CASES: list[tuple[str, list[SearchResult]]] = []


def _chunk(source: str, idx: int, content: str, score: float = 0.9) -> SearchResult:
    return SearchResult(
        id=hashlib.sha256(content.encode()).hexdigest(),
        content=content,
        source_path=source,
        chunk_index=idx,
        score=score,
        metadata={},
    )


def _text(prefix: str, n: int) -> str:
    """Generate a multi-sentence text for realistic compression."""
    s = [
        f"{prefix} paragraph {i} contains several interesting sentences that provide detailed information about the topic being discussed in this context."
        for i in range(n)
    ]
    return " ".join(s)


TEST_CASES = [
    (
        "multiple sources multiple chunks",
        [
            _chunk("/docs/math.txt", 0, _text("Derivatives", 8)),
            _chunk("/docs/math.txt", 1, _text("Integrals", 6)),
            _chunk("/docs/physics.txt", 0, _text("Quantum mechanics", 10)),
            _chunk("/docs/physics.txt", 1, _text("Relativity", 5)),
            _chunk("/docs/chemistry.txt", 0, _text("Organic chemistry", 7)),
        ],
    ),
    (
        "single source multiple chunks",
        [
            _chunk("/docs/ml.txt", 0, _text("Supervised learning", 12)),
            _chunk("/docs/ml.txt", 1, _text("Unsupervised learning", 8)),
            _chunk("/docs/ml.txt", 2, _text("Reinforcement learning", 6)),
            _chunk("/docs/ml.txt", 3, _text("Deep learning architectures", 9)),
        ],
    ),
    (
        "single source single chunk",
        [
            _chunk("/docs/readme.txt", 0, _text("Project overview", 15)),
        ],
    ),
    (
        "empty-like minimal content",
        [
            _chunk("/docs/empty.txt", 0, "This is short."),
            _chunk("/docs/empty.txt", 1, "Another one."),
        ],
    ),
    (
        "repeated source different indices",
        [
            _chunk("/docs/large.txt", 5, _text("Chapter 1", 10)),
            _chunk("/docs/large.txt", 12, _text("Chapter 2", 8)),
            _chunk("/docs/large.txt", 99, _text("Chapter 3", 6)),
        ],
    ),
]


def build_report(results: list[dict], all_pass: bool) -> str:
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("SEMANTIC COMPRESSOR — LINEAGE VALIDATION REPORT")
    lines.append(f"Generated: {datetime.now(UTC).strftime('%Y%m%dT%H%M%S')} UTC")
    lines.append("=" * 80)
    lines.append("")
    lines.append(
        f"{'Test Case':<45} {'Original Count':<16} {'Compressed Count':<18} {'Lineage OK':<12}"
    )
    lines.append("-" * 91)
    for r in results:
        name = r["name"][:42] + "..." if len(r["name"]) > 45 else r["name"]
        lines.append(
            f"{name:<45} {r['original_count']:<16} {r['compressed_count']:<18} "
            f"{'✅' if r['lineage_ok'] else '❌':<12}"
        )
    lines.append("-" * 91)
    lines.append(f"\nResult: {'ALL PASS ✅' if all_pass else 'FAILURES DETECTED ❌'}")
    lines.append("")
    if all_pass:
        lines.append(
            "All compressed (source_path, chunk_index) pairs are strict subsets of originals."
        )
    else:
        for r in results:
            if not r["lineage_ok"]:
                lines.append(f"  FAIL: {r['name']}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    results: list[dict] = []
    all_pass = True

    for case_name, chunks in TEST_CASES:
        tracemalloc.start()

        compressor = SemanticCompressor(embed_fn=None)  # TF-IDF path
        compressed = compressor.compress(case_name, chunks, max_tokens=600)

        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        original_lineage = {(c.source_path, c.chunk_index) for c in chunks}
        compressed_lineage = {(c.source_path, c.chunk_index) for c in compressed}

        # Must be a strict subset — no new pairs may appear
        lineage_ok = compressed_lineage.issubset(original_lineage)

        print(f"Test: {case_name}")
        print(f"  Original chunks: {len(chunks)} -> Compressed: {len(compressed)}")
        print(f"  Original lineage: {sorted(original_lineage)}")
        print(f"  Compressed lineage: {sorted(compressed_lineage)}")
        print(f"  Lineage subset check: {'✅' if lineage_ok else '❌'}")

        if not lineage_ok:
            all_pass = False
            new_pairs = compressed_lineage - original_lineage
            print(f"  ERROR: New (source_path, chunk_index) pairs appeared: {new_pairs}")

        results.append(
            {
                "name": case_name,
                "original_count": len(chunks),
                "compressed_count": len(compressed),
                "lineage_ok": lineage_ok,
                "peak_mem_mb": peak / 1024 / 1024,
            }
        )

    report = build_report(results, all_pass)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    report_path = REPORTS_DIR / f"validate_lineage_{timestamp}.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to: {report_path}")
    print(report)

    peak_mb = max(r["peak_mem_mb"] for r in results)
    assert peak_mb < 50, f"Peak memory {peak_mb:.1f}MB exceeds 50MB limit"

    assert all_pass, "FAIL: Some lineage validation checks failed"
    print("\n✅ validate_lineage.py PASSED — all lineages preserved.")


if __name__ == "__main__":
    main()
