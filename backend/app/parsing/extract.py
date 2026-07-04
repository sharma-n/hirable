from __future__ import annotations

import io
import logging
import re

from fastapi import HTTPException

logger = logging.getLogger(__name__)

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_ALLOWED_FORMATS = {"pdf", "docx", "tex"}


def _strip_latex(text: str) -> str:
    """Strip LaTeX commands, leaving readable plain text."""
    # Remove comments
    text = re.sub(r"%.*$", "", text, flags=re.MULTILINE)
    # Remove \command[opts]{arg} — keep arg content
    text = re.sub(r"\\[a-zA-Z]+\*?\[.*?\]\{(.*?)\}", r"\1", text, flags=re.DOTALL)
    # Remove \command{arg} — keep arg content
    text = re.sub(r"\\[a-zA-Z]+\*?\{(.*?)\}", r"\1", text, flags=re.DOTALL)
    # Remove remaining \commands
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    # Remove { }
    text = re.sub(r"[{}]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _extract_with_docling(data: bytes, fmt: str) -> str:
    """Convert PDF/DOCX bytes to markdown via docling.

    Feeds docling an in-memory ``DocumentStream`` (no temp file).
    """
    from docling.datamodel.base_models import DocumentStream
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    source = DocumentStream(name=f"resume.{fmt}", stream=io.BytesIO(data))
    result = converter.convert(source)
    return result.document.export_to_markdown()


def extract_text(data: bytes, fmt: str) -> str:
    """Return plain/markdown text from resume bytes.

    fmt: 'pdf' | 'docx' | 'tex'
    Raises HTTPException on unsupported format, oversized file, or conversion failure.
    """
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    if fmt not in _ALLOWED_FORMATS:
        raise HTTPException(status_code=415, detail=f"Unsupported format: {fmt}")

    if fmt == "tex":
        try:
            return _strip_latex(data.decode("utf-8", errors="replace"))
        except Exception as exc:
            raise HTTPException(
                status_code=422, detail=f"Could not process .tex file: {exc}"
            ) from exc

    # pdf / docx — single docling path.
    try:
        from docling.document_converter import DocumentConverter  # noqa: F401
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="docling not installed") from exc

    try:
        text = _extract_with_docling(data, fmt)
    except Exception as exc:
        # Log full traceback so the server terminal shows what actually went wrong.
        logger.exception("Text extraction failed for %s", fmt.upper())
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract text from {fmt.upper()} — {exc}",
        ) from exc

    if not text or not text.strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "Extracted text is empty — the file may be a scanned image PDF. "
                "Please export a text-based PDF and try again."
            ),
        )
    return text
