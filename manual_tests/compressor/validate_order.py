"""Validate chronological order preservation within each compressed chunk.

Protocol:
1. Create a test document with numbered sentences: "SENT_1.", "SENT_2.", ...
2. Run compressor.compress on the chunk
3. Extract sentence numbers from compressed content
4. Assert numbers are in strictly ascending order

Also validates memory via tracemalloc (< 50MB peak).

Writes report to manual_tests/compressor/reports/validate_order_<ISO8601>.txt.
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

_SENTENCE_NUM_RE = re.compile(r"SENT_(\d+)")


def _chunk(source: str, idx: int, content: str) -> SearchResult:
    return SearchResult(
        id=hashlib.sha256(content.encode()).hexdigest(),
        content=content,
        source_path=source,
        chunk_index=idx,
        score=0.9,
        metadata={},
    )


def _numbered_content(count: int) -> str:
    """Generate text with embedded SENT_ markers.

    SENT_ markers are embedded within the sentence body (before the terminal
    period) so they survive sentence splitting and min-token filtering.
    The compressor regex intentionally avoids splitting on digits to protect
    decimals (3.14), so "SENT_1. " at the start of a sentence would be split
    off as a separate short unit and filtered. By embedding the marker inside
    the sentence text, it stays with the main content unit.
    """
    sentences: list[str] = []
    for i in range(1, count + 1):
        tail = (
            "Esta es una oración de relleno con suficiente contexto para probar "
            "que el compresor semántico mantiene el orden cronológico con el "
            f"marcador SENT_{i} incluido en el cuerpo de la oración."
        )
        sentences.append(tail)
    return " ".join(sentences)


TEST_CASES: list[tuple[str, list[SearchResult], str]] = [
    (
        "single chunk 12 sentences",
        [_chunk("/docs/test.txt", 0, _numbered_content(12))],
        "SENT_",
    ),
    (
        "two chunks with overlapping indices",
        [
            _chunk("/docs/a.txt", 0, _numbered_content(8)),
            _chunk("/docs/b.txt", 1, _numbered_content(6)),
        ],
        "SENT_",
    ),
    (
        "three chunks single source",
        [
            _chunk("/docs/large.txt", 0, _numbered_content(10)),
            _chunk("/docs/large.txt", 1, _numbered_content(7)),
            _chunk("/docs/large.txt", 2, _numbered_content(5)),
        ],
        "SENT_",
    ),
    (
        "interleaved sources",
        [
            _chunk("/docs/math.txt", 0, _numbered_content(6)),
            _chunk("/docs/physics.txt", 0, _numbered_content(8)),
            _chunk("/docs/math.txt", 1, _numbered_content(5)),
        ],
        "SENT_",
    ),
    (
        "single sentence chunks (boundary case)",
        [
            _chunk(
                "/docs/single.txt",
                0,
                "Esta es la primera oración única con el marcador SENT_1 dentro del cuerpo del texto para verificar el orden cuando cada chunk contiene una sola oración.",
            ),
            _chunk(
                "/docs/single.txt",
                1,
                "Esta es la segunda oración independiente con el marcador SENT_2 también dentro del texto y con suficiente longitud para pasar los filtros del compresor.",
            ),
            _chunk(
                "/docs/single.txt",
                2,
                "Esta es la tercera oración de prueba con el marcador SENT_3 al final del contenido para verificar el orden cronológico sin importar el score.",
            ),
        ],
        "SENT_",
    ),
]


def build_report(results: list[dict], all_pass: bool) -> str:
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("SEMANTIC COMPRESSOR — ORDER VALIDATION REPORT")
    lines.append(f"Generated: {datetime.now(UTC).strftime('%Y%m%dT%H%M%S')} UTC")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"{'Test Case':<45} {'Chunks Out':<14} {'Order OK':<12}")
    lines.append("-" * 71)
    for r in results:
        name = r["name"][:42] + "..." if len(r["name"]) > 45 else r["name"]
        lines.append(f"{name:<45} {r['chunks_out']:<14} {'✅' if r['order_ok'] else '❌':<12}")
    lines.append("-" * 71)
    lines.append(f"\nResult: {'ALL PASS ✅' if all_pass else 'FAILURES DETECTED ❌'}")
    lines.append("")
    if all_pass:
        lines.append("All compressed chunks maintain strict chronological order.")
    else:
        for r in results:
            if not r["order_ok"]:
                lines.append(
                    f"  FAIL: {r['name']} — order violation in chunk {r.get('fail_chunk')}"
                )
                lines.append(f"    Numbers found: {r.get('numbers_found')}")
    lines.append("")
    return "\n".join(lines)


def _check_chunk_order(content: str, label: str) -> tuple[bool, list[int], str | None]:
    """Check that numbered sentences within content are in ascending order.

    Returns (ok, numbers_found, fail_chunk_key).
    """
    numbers = [int(m) for m in _SENTENCE_NUM_RE.findall(content)]
    if len(numbers) <= 1:
        return True, numbers, None
    for i in range(1, len(numbers)):
        if numbers[i] <= numbers[i - 1]:
            return (
                False,
                numbers,
                f"{label} (descending at position {i}: {numbers[i-1]} -> {numbers[i]})",
            )
    return True, numbers, None


def main() -> None:
    results: list[dict] = []
    all_pass = True

    for case_name, chunks, pattern_label in TEST_CASES:
        tracemalloc.start()

        compressor = SemanticCompressor(embed_fn=None)
        compressed = compressor.compress(case_name, chunks, max_tokens=600)

        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        order_ok = True
        fail_chunk = None
        all_numbers: list[int] = []

        for c in compressed:
            key = f"{c.source_path}:{c.chunk_index}"
            ok, numbers, fail = _check_chunk_order(c.content, key)
            all_numbers.extend(numbers)
            if not ok:
                order_ok = False
                fail_chunk = fail

        print(f"Test: {case_name}")
        print(f"  Input chunks: {len(chunks)} -> Output chunks: {len(compressed)}")
        print(f"  Numbers found: {all_numbers}")
        print(f"  Strictly ascending: {'✅' if order_ok else '❌'}")

        if not order_ok:
            all_pass = False
            print(f"  ERROR: {fail_chunk}")

        results.append(
            {
                "name": case_name,
                "chunks_out": len(compressed),
                "order_ok": order_ok,
                "fail_chunk": fail_chunk,
                "numbers_found": all_numbers,
                "peak_mem_mb": peak / 1024 / 1024,
            }
        )

    report = build_report(results, all_pass)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    report_path = REPORTS_DIR / f"validate_order_{timestamp}.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to: {report_path}")
    print(report)

    peak_mb = max(r["peak_mem_mb"] for r in results)
    assert peak_mb < 50, f"Peak memory {peak_mb:.1f}MB exceeds 50MB limit"

    assert all_pass, "FAIL: Some order validation checks failed"
    print("\n✅ validate_order.py PASSED — all chunks preserve chronological order.")


if __name__ == "__main__":
    main()
