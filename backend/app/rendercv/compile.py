"""Compile RenderCV YAML source to PDF bytes, in-process (no subprocess).

RenderCV renders via Typst (not LaTeX/TinyTeX — see CLAUDE.md's Typst-not-
TinyTeX correction), and ships a clean Python API for both validation and
rendering (rendercv.schema.rendercv_model_builder + rendercv.renderer.*).
Nothing is ever written outside a TemporaryDirectory — no PDFs or Typst
sources are persisted (see Document model's docstring: source_text is the
only thing stored).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from rendercv.exception import RenderCVInternalError, RenderCVUserError, RenderCVUserValidationError
from rendercv.renderer.pdf_png import generate_pdf
from rendercv.renderer.typst import generate_typst
from rendercv.schema.rendercv_model_builder import build_rendercv_dictionary_and_model


class CompileError(Exception):
    """Raised on any compile failure. ``stage`` is one of:
    - "yaml": the source isn't valid YAML at all.
    - "schema": valid YAML, but doesn't satisfy RenderCV's schema (e.g. bad
      phone format, unknown field, wrong entry-type mix in a section).
    - "render": valid + schema-valid, but Typst compilation itself failed.
    """

    def __init__(self, stage: str, errors: list[str]):
        self.stage = stage
        self.errors = errors
        super().__init__(f"{stage}: {'; '.join(errors)}")


def compile_pdf(source_text: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="hirable-cv-") as tmp:
        input_path = Path(tmp) / "cv.yaml"
        input_path.write_text(source_text, encoding="utf-8")

        try:
            _, model = build_rendercv_dictionary_and_model(
                source_text,
                input_file_path=input_path,
                dont_generate_html=True,
                dont_generate_markdown=True,
                dont_generate_png=True,
            )
        except RenderCVUserValidationError as exc:
            # Both plain YAML syntax errors and schema-validation errors raise
            # this same exception type; schema_location is None only for the
            # former (see rendercv.schema.rendercv_model_builder).
            stage = "yaml" if all(e.schema_location is None for e in exc.validation_errors) else "schema"
            raise CompileError(stage, [e.message for e in exc.validation_errors]) from exc
        except RenderCVUserError as exc:
            raise CompileError("yaml", [exc.message or str(exc)]) from exc

        try:
            typst_path = generate_typst(model)
            pdf_path = generate_pdf(model, typst_path)
        except (RenderCVUserError, RenderCVInternalError) as exc:
            message = getattr(exc, "message", None) or str(exc)
            raise CompileError("render", [message]) from exc

        if pdf_path is None:
            raise CompileError("render", ["PDF generation produced no output"])
        return pdf_path.read_bytes()
