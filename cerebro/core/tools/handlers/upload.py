"""File upload handler — processes PDFs, images, and text files safely."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import fitz  # pymupdf
from loguru import logger

# Size limits (10 MB per file)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 10

# Supported MIME types
SUPPORTED_TEXT_TYPES = {
    "text/plain",
    "text/markdown",
    "application/json",
    "text/x-python",
    "text/javascript",
    "text/typescript",
    "text/x-java",
    "text/x-c",
    "text/x-cpp",
    "text/yaml",
    "text/xml",
}

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

SUPPORTED_DOCUMENT_TYPES = {
    "application/pdf",
}

ALL_SUPPORTED_TYPES = SUPPORTED_TEXT_TYPES | SUPPORTED_IMAGE_TYPES | SUPPORTED_DOCUMENT_TYPES


def validate_file_upload(file_path: str, max_bytes: int = MAX_UPLOAD_BYTES) -> tuple[bool, str]:
    """
    Validate that a file is safe to upload.

    Returns: (is_valid, error_message)
    """
    p = Path(file_path)

    # Check existence
    if not p.exists():
        return False, f"File not found: {file_path}"

    if not p.is_file():
        return False, f"Not a file: {file_path}"

    # Check size
    try:
        size = p.stat().st_size
    except OSError as exc:
        return False, f"Cannot read file: {exc}"

    if size > max_bytes:
        size_mb = size / (1024 * 1024)
        max_mb = max_bytes / (1024 * 1024)
        return False, f"File too large: {size_mb:.1f} MB (max {max_mb:.0f} MB)"

    # Check MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type not in ALL_SUPPORTED_TYPES:
        return False, f"Unsupported file type: {mime_type}. Supported: PDF, images, text files"

    return True, ""


def extract_pdf_text(pdf_path: str, max_pages: int = MAX_PDF_PAGES) -> str:
    """
    Extract text from PDF file (limited to max_pages to avoid huge outputs).
    Returns concatenated text with page markers.
    """
    try:
        doc = fitz.open(pdf_path)
        total_pages = doc.page_count
        actual_pages = min(total_pages, max_pages)

        parts = [f"[PDF: {pdf_path}, pages {actual_pages}/{total_pages}]\n"]

        for page_num in range(actual_pages):
            page = doc[page_num]
            text = page.get_text()
            parts.append(f"\n--- Page {page_num + 1} ---\n{text}")

        if actual_pages < total_pages:
            parts.append(
                f"\n[Truncado: Se mostraron {actual_pages} de {total_pages} páginas. "
                f"Pídeme una página específica con read_file si necesitas más.]"
            )

        doc.close()
        return "".join(parts)

    except Exception as exc:
        logger.error("extract_pdf_text failed: {}", exc)
        return f"Error extracting PDF text: {exc}"


def encode_image_base64(image_path: str) -> dict:
    """
    Encode image as base64 and return metadata.
    Returns: {"base64": str, "mime_type": str, "size_bytes": int}
    """
    try:
        p = Path(image_path)
        data = p.read_bytes()
        mime_type, _ = mimetypes.guess_type(image_path)
        b64 = base64.b64encode(data).decode("utf-8")

        return {
            "base64": b64,
            "mime_type": mime_type or "image/unknown",
            "size_bytes": len(data),
            "filename": p.name,
        }
    except Exception as exc:
        logger.error("encode_image_base64 failed: {}", exc)
        return {"error": str(exc)}


def process_uploaded_file(
    file_path: str,
    authorized_paths: list[str] | None = None,
    *,
    enforce_authorization: bool = True,
) -> dict:
    """
    Process an uploaded file and return metadata + content.

    For PDFs: extracts text
    For images: returns base64
    For text: returns content directly

    Returns: {"type": str, "content": str, "metadata": dict} or error dict
    """
    from core.tools.handlers.filesystem import _require_authorized_path

    # Uploaded files arrive through a server-managed temp file, so the upload
    # endpoint can skip path authorization after validating the HTTP upload.
    if enforce_authorization:
        try:
            _require_authorized_path(file_path, authorized_paths or [], operation="procesar")
        except Exception as exc:
            logger.error("Authorization failed for {}: {}", file_path, exc)
            return {"error": str(exc)}

    # Validate file
    is_valid, error_msg = validate_file_upload(file_path)
    if not is_valid:
        logger.warning("File validation failed: {}", error_msg)
        return {"error": error_msg}

    p = Path(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)

    try:
        # PDF
        if mime_type == "application/pdf":
            text = extract_pdf_text(file_path)
            return {
                "type": "pdf",
                "content": text,
                "metadata": {
                    "filename": p.name,
                    "mime_type": mime_type,
                    "size_bytes": p.stat().st_size,
                },
            }

        # Image
        elif mime_type in SUPPORTED_IMAGE_TYPES:
            img_data = encode_image_base64(file_path)
            if "error" in img_data:
                return {"error": img_data["error"]}
            return {
                "type": "image",
                "content": img_data["base64"],
                "metadata": {
                    "filename": p.name,
                    "mime_type": mime_type,
                    "size_bytes": img_data["size_bytes"],
                },
            }

        # Text file
        elif mime_type in SUPPORTED_TEXT_TYPES:
            content = p.read_text(encoding="utf-8", errors="replace")
            if len(content) > MAX_UPLOAD_BYTES:
                content = content[:MAX_UPLOAD_BYTES]
                content += "\n[Archivo truncado — demasiado grande]"

            return {
                "type": "text",
                "content": content,
                "metadata": {
                    "filename": p.name,
                    "mime_type": mime_type,
                    "size_bytes": p.stat().st_size,
                },
            }

        else:
            return {"error": f"Unknown file type: {mime_type}"}

    except Exception as exc:
        logger.error("process_uploaded_file failed for {}: {}", file_path, exc)
        return {"error": f"Error processing file: {exc}"}


def handle_file_upload(file_path: str, authorized_paths: list[str]) -> str:
    """
    Tool handler for file uploads. Returns a formatted summary.
    Used by agents to process user-uploaded files.
    """
    result = process_uploaded_file(file_path, authorized_paths)

    if "error" in result:
        return f"Error: {result['error']}"

    meta = result.get("metadata", {})
    file_type = result.get("type", "unknown")
    content = result.get("content", "")

    # For images, show metadata only (base64 is shown separately in UI)
    if file_type == "image":
        return (
            f"✓ Image uploaded: {meta.get('filename')} "
            f"({meta.get('size_bytes', 0) / 1024:.1f} KB)\n"
            f"The image has been provided to the AI for analysis."
        )

    # For PDFs/text, show first 500 chars of content
    content_preview = content[:500] if content else ""
    if len(content) > 500:
        content_preview += "\n...(truncado)"

    return (
        f"✓ File uploaded: {meta.get('filename')} ({file_type.upper()})\n\n"
        f"Content preview:\n{content_preview}"
    )
