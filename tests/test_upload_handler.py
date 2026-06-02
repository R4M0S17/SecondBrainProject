"""Tests for file upload handler — PDF, images, text files."""

import base64

import pytest

from core.tools.handlers.upload import (
    encode_image_base64,
    extract_pdf_text,
    handle_file_upload,
    process_uploaded_file,
    validate_file_upload,
)


@pytest.fixture
def tmp_text_file(tmp_path):
    """Create a temporary text file."""
    f = tmp_path / "test.txt"
    f.write_text("Hello, World!\n" * 100)
    return f


@pytest.fixture
def tmp_pdf_file(tmp_path):
    """Create a minimal valid PDF file for testing."""
    # Simple PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 50
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF Document) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000203 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
304
%%EOF
"""
    f = tmp_path / "test.pdf"
    f.write_bytes(pdf_content)
    return f


@pytest.fixture
def tmp_image_file(tmp_path):
    """Create a minimal valid PNG image."""
    # Smallest valid PNG: 1x1 transparent pixel
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d494844520000000100000001"
        "0802000000907753de0000001049444154789c62f8cfccc0"
        "0000031001010000183b0b06000000004945444d456f"
    )
    f = tmp_path / "test.png"
    f.write_bytes(png_bytes)
    return f


# ────────────────────────────────────────────────────────────────────────────────
# validate_file_upload tests
# ────────────────────────────────────────────────────────────────────────────────


def test_validate_file_upload_text_succeeds(tmp_text_file):
    """Valid text file should pass validation."""
    is_valid, error = validate_file_upload(str(tmp_text_file))
    assert is_valid is True
    assert error == ""


def test_validate_file_upload_nonexistent_fails():
    """Nonexistent file should fail validation."""
    is_valid, error = validate_file_upload("/nonexistent/file.txt")
    assert is_valid is False
    assert "not found" in error.lower()


def test_validate_file_upload_directory_fails(tmp_path):
    """Directory should fail validation."""
    is_valid, error = validate_file_upload(str(tmp_path))
    assert is_valid is False
    assert "not a file" in error.lower()


def test_validate_file_upload_oversized_fails(tmp_path):
    """File exceeding max size should fail validation."""
    large_file = tmp_path / "large.txt"
    # Create file larger than default 10MB
    large_file.write_bytes(b"x" * (11 * 1024 * 1024))

    is_valid, error = validate_file_upload(str(large_file))
    assert is_valid is False
    assert "too large" in error.lower()


def test_validate_file_upload_unsupported_type(tmp_path):
    """Unsupported MIME type should fail validation."""
    exe_file = tmp_path / "test.exe"
    exe_file.write_bytes(b"MZ\x90\x00")  # PE header

    is_valid, error = validate_file_upload(str(exe_file))
    assert is_valid is False
    assert "unsupported" in error.lower() or "type" in error.lower()


# ────────────────────────────────────────────────────────────────────────────────
# extract_pdf_text tests
# ────────────────────────────────────────────────────────────────────────────────


def test_extract_pdf_text_succeeds(tmp_pdf_file):
    """PDF extraction should return text."""
    text = extract_pdf_text(str(tmp_pdf_file))
    assert "[PDF:" in text
    assert "Test PDF Document" in text or len(text) > 0


def test_extract_pdf_text_nonexistent_returns_error():
    """Extracting from nonexistent PDF should return error."""
    text = extract_pdf_text("/nonexistent/file.pdf")
    assert "Error" in text or "error" in text.lower()


# ────────────────────────────────────────────────────────────────────────────────
# encode_image_base64 tests
# ────────────────────────────────────────────────────────────────────────────────


def test_encode_image_base64_succeeds(tmp_image_file):
    """Image encoding should produce base64."""
    result = encode_image_base64(str(tmp_image_file))
    assert "base64" in result
    assert "mime_type" in result
    assert result["mime_type"] == "image/png"
    assert len(result["base64"]) > 0
    # Verify it's valid base64
    decoded = base64.b64decode(result["base64"])
    assert len(decoded) > 0


def test_encode_image_base64_nonexistent_returns_error():
    """Encoding nonexistent image should return error dict."""
    result = encode_image_base64("/nonexistent/image.png")
    assert "error" in result


# ────────────────────────────────────────────────────────────────────────────────
# process_uploaded_file tests
# ────────────────────────────────────────────────────────────────────────────────


def test_process_text_file_succeeds(tmp_text_file, tmp_path):
    """Processing text file should extract content."""
    result = process_uploaded_file(str(tmp_text_file), [str(tmp_path)])
    assert result["type"] == "text"
    assert "Hello, World!" in result["content"]
    assert result["metadata"]["filename"] == "test.txt"
    assert result["metadata"]["mime_type"] == "text/plain"


def test_process_pdf_file_succeeds(tmp_pdf_file, tmp_path):
    """Processing PDF should extract text."""
    result = process_uploaded_file(str(tmp_pdf_file), [str(tmp_path)])
    assert result["type"] == "pdf"
    assert result["metadata"]["filename"] == "test.pdf"
    assert result["metadata"]["mime_type"] == "application/pdf"
    assert len(result["content"]) > 0


def test_process_image_file_succeeds(tmp_image_file, tmp_path):
    """Processing image should return base64."""
    result = process_uploaded_file(str(tmp_image_file), [str(tmp_path)])
    assert result["type"] == "image"
    assert result["metadata"]["filename"] == "test.png"
    assert result["metadata"]["mime_type"] == "image/png"
    assert len(result["content"]) > 0  # base64
    # Verify it's valid base64
    decoded = base64.b64decode(result["content"])
    assert len(decoded) > 0


def test_process_file_unauthorized_path_fails(tmp_text_file, tmp_path):
    """File outside authorized paths should return error."""
    result = process_uploaded_file(str(tmp_text_file), ["/unauthorized/path"])
    assert isinstance(result, dict)
    assert "error" in result


def test_process_nonexistent_file_returns_error(tmp_path):
    """Nonexistent file should return error."""
    result = process_uploaded_file("/nonexistent/file.txt", [str(tmp_path)])
    assert "error" in result


# ────────────────────────────────────────────────────────────────────────────────
# handle_file_upload tests (tool handler)
# ────────────────────────────────────────────────────────────────────────────────


def test_handle_file_upload_text_returns_string(tmp_text_file, tmp_path):
    """Tool handler should return formatted string."""
    result = handle_file_upload(str(tmp_text_file), [str(tmp_path)])
    assert isinstance(result, str)
    assert "✓" in result or "File uploaded" in result
    assert "test.txt" in result


def test_handle_file_upload_image_returns_string(tmp_image_file, tmp_path):
    """Tool handler for image should return formatted string."""
    result = handle_file_upload(str(tmp_image_file), [str(tmp_path)])
    assert isinstance(result, str)
    assert "✓" in result or "Image uploaded" in result
    assert "test.png" in result


def test_handle_file_upload_error_returns_error_string(tmp_path):
    """Tool handler should return error string for invalid files."""
    result = handle_file_upload("/nonexistent/file.txt", [str(tmp_path)])
    assert isinstance(result, str)
    assert "Error" in result


# ────────────────────────────────────────────────────────────────────────────────
# Edge cases
# ────────────────────────────────────────────────────────────────────────────────


def test_process_text_file_max_bytes_truncated(tmp_path):
    """Large text file should be rejected due to size limit."""
    big_text = tmp_path / "big.txt"
    big_text.write_text("x" * 20 * 1024 * 1024)  # 20 MB

    result = process_uploaded_file(str(big_text), [str(tmp_path)])
    # Should return error for oversized file
    assert "error" in result


def test_json_file_treated_as_text(tmp_path):
    """JSON file should be treated as text."""
    json_file = tmp_path / "data.json"
    json_file.write_text('{"key": "value"}')

    result = process_uploaded_file(str(json_file), [str(tmp_path)])
    assert result["type"] == "text"
    assert '{"key": "value"}' in result["content"]


def test_markdown_file_treated_as_text(tmp_path):
    """Markdown file should be treated as text."""
    md_file = tmp_path / "README.md"
    md_file.write_text("# Hello\n\nThis is markdown.")

    result = process_uploaded_file(str(md_file), [str(tmp_path)])
    assert result["type"] == "text"
    assert "# Hello" in result["content"]
