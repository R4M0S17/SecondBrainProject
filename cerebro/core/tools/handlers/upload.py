"""File upload handler — processes PDFs, images, and text files safely."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import fitz  # pymupdf
from loguru import logger

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 10

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
    p = Path(file_path)
    if not p.exists():
        return False, f"File not found: {file_path}"
    if not p.is_file():
        return False, f"Not a file: {file_path}"
    try:
        size = p.stat().st_size
    except OSError as exc:
        return False, f"Cannot read file: {exc}"
    if size > max_bytes:
        size_mb = size / (1024 * 1024)
        max_mb = max_bytes / (1024 * 1024)
        return False, f"File too large: {size_mb:.1f} MB (max {max_mb:.0f} MB)"
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type not in ALL_SUPPORTED_TYPES:
        return False, f"Unsupported file type: {mime_type}. Supported: PDF, images, text files"
    return True, ""


def extract_pdf_text(pdf_path: str, max_pages: int = MAX_PDF_PAGES) -> str:
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
    from core.tools.handlers.filesystem import _require_authorized_path

    if enforce_authorization:
        try:
            _require_authorized_path(file_path, authorized_paths or [], operation="procesar")
        except Exception as exc:
            logger.error("Authorization failed for {}: {}", file_path, exc)
            return {"error": str(exc)}

    is_valid, error_msg = validate_file_upload(file_path)
    if not is_valid:
        logger.warning("File validation failed: {}", error_msg)
        return {"error": error_msg}

    p = Path(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)

    try:
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

        if mime_type in SUPPORTED_IMAGE_TYPES:
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

        if mime_type in SUPPORTED_TEXT_TYPES:
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

        return {"error": f"Unknown file type: {mime_type}"}
    except Exception as exc:
        logger.error("process_uploaded_file failed for {}: {}", file_path, exc)
        return {"error": f"Error processing file: {exc}"}
