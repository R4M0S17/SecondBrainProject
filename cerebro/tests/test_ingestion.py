import hashlib

import pytest

from core.ingestion.pipeline import Document, IngestionPipeline


@pytest.fixture
def pipeline():
    return IngestionPipeline(chunk_size=20, chunk_overlap=5, min_chunk_size=5)


# --- Format parsing ---


def test_parse_txt(tmp_path, pipeline):
    f = tmp_path / "test.txt"
    f.write_text("Hello world " * 30)
    docs = pipeline.ingest(str(f))
    assert len(docs) > 0
    assert all(isinstance(d, Document) for d in docs)


def test_parse_md(tmp_path, pipeline):
    f = tmp_path / "test.md"
    f.write_text("# Title\n\nSome content here. " * 30)
    docs = pipeline.ingest(str(f))
    assert len(docs) > 0


def test_parse_py(tmp_path, pipeline):
    f = tmp_path / "test.py"
    f.write_text("def foo():\n    return 42\n" * 30)
    docs = pipeline.ingest(str(f))
    assert len(docs) > 0


def test_parse_pdf(tmp_path, pipeline):
    import fitz

    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello world " * 60)
    doc.save(str(pdf_path))
    doc.close()

    docs = pipeline.ingest(str(pdf_path))
    assert len(docs) > 0
    assert all(d.metadata.get("extension") == ".pdf" for d in docs)


def test_parse_docx(tmp_path, pipeline):
    from docx import Document as DocxDocument

    docx_path = tmp_path / "test.docx"
    doc = DocxDocument()
    for _ in range(15):
        doc.add_paragraph("This is a paragraph with some content in it. " * 3)
    doc.save(str(docx_path))

    docs = pipeline.ingest(str(docx_path))
    assert len(docs) > 0


def test_unsupported_format_returns_empty(tmp_path, pipeline):
    f = tmp_path / "data.csv"
    f.write_text("a,b,c\n1,2,3\n")
    assert pipeline.ingest(str(f)) == []


# --- Chunking boundaries and overlap ---


def test_chunk_boundaries_and_overlap(tmp_path):
    pipeline = IngestionPipeline(chunk_size=10, chunk_overlap=3, min_chunk_size=3)
    words = [f"w{i}" for i in range(40)]
    f = tmp_path / "test.txt"
    f.write_text(" ".join(words))
    docs = pipeline.ingest(str(f))
    assert len(docs) > 1
    # Tail of chunk N must equal head of chunk N+1 (overlap = 3 words)
    for i in range(len(docs) - 1):
        tail = docs[i].content.split()[-3:]
        head = docs[i + 1].content.split()[:3]
        assert tail == head


def test_no_chunk_below_min_size(tmp_path):
    pipeline = IngestionPipeline(chunk_size=20, chunk_overlap=5, min_chunk_size=10)
    # 23 words → one 20-word chunk + 8-word remainder (below min) → merged into first
    f = tmp_path / "test.txt"
    f.write_text(" ".join([f"w{i}" for i in range(23)]))
    docs = pipeline.ingest(str(f))
    for doc in docs:
        assert len(doc.content.split()) >= 10


def test_chunk_index_is_sequential(tmp_path, pipeline):
    f = tmp_path / "test.txt"
    f.write_text("word " * 100)
    docs = pipeline.ingest(str(f))
    assert [d.chunk_index for d in docs] == list(range(len(docs)))


# --- Edge cases ---


def test_empty_file_returns_empty(tmp_path, pipeline):
    f = tmp_path / "empty.txt"
    f.write_text("")
    assert pipeline.ingest(str(f)) == []


def test_nonexistent_file_returns_empty(pipeline):
    assert pipeline.ingest("/nonexistent/path/file.txt") == []


def test_latin1_fallback(tmp_path, pipeline):
    f = tmp_path / "latin.txt"
    f.write_bytes(("café résumé " * 30).encode("latin-1"))
    docs = pipeline.ingest(str(f))
    assert len(docs) > 0


def test_document_id_is_sha256_of_content(tmp_path, pipeline):
    f = tmp_path / "test.txt"
    f.write_text("Hello world " * 30)
    docs = pipeline.ingest(str(f))
    for doc in docs:
        expected = hashlib.sha256(doc.content.encode()).hexdigest()
        assert doc.id == expected


def test_corrupt_pdf_returns_empty(tmp_path, pipeline):
    f = tmp_path / "corrupt.pdf"
    f.write_bytes(b"this is not a pdf")
    docs = pipeline.ingest(str(f))
    assert docs == []
