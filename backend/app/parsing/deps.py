from __future__ import annotations

from docling.document_converter import DocumentConverter
from fastapi import Request


def get_docling_converter(request: Request) -> DocumentConverter:
    return request.app.state.docling_converter
