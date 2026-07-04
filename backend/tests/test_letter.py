"""M6 cover-letter module — YAML builder, tailoring, and real Typst compilation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from app.llm.schemas import TailoredCoverLetter
from app.rendercv.compile import CompileError, compile_pdf
from app.rendercv.letter import build_cover_letter_yaml, tailor_cover_letter

_PROFILE = {
    "contact": {
        "name": "Jane Doe",
        "headline": "Senior Software Engineer",
        "email": "jane@example.com",
        "phone": "+14155552671",
        "location": "Remote",
        "website": "https://janedoe.dev",
        "social_networks": [],
        "links": [],
    },
    "summary": "Untailored master summary.",
}

_JOB = {"company": "Acme", "title": "Engineer"}


def _tailored(**overrides) -> TailoredCoverLetter:
    base = dict(
        worth_it=True,
        recipient="Hiring Manager",
        salutation="Dear Hiring Manager,",
        body_paragraphs=[
            "I've long admired Acme's engineering culture.",
            "I understand the role involves owning backend services end to end.",
            "In my prior role I shipped a system that reduced latency by 30%: measured by Y.",
        ],
        closing="Sincerely,",
    )
    base.update(overrides)
    return TailoredCoverLetter(**base)


class TestBuildCoverLetterYaml:
    def test_contact_fields_mapped_verbatim(self):
        text = build_cover_letter_yaml(_PROFILE, _tailored(), "engineeringresumes")
        doc = yaml.safe_load(text)
        cv = doc["cv"]
        assert cv["name"] == "Jane Doe"
        assert cv["email"] == "jane@example.com"
        assert cv["phone"] == "+14155552671"

    def test_body_paragraphs_become_text_entry_section(self):
        text = build_cover_letter_yaml(_PROFILE, _tailored(), "engineeringresumes")
        doc = yaml.safe_load(text)
        paragraphs = doc["cv"]["sections"]["Cover Letter"]
        assert "Dear Hiring Manager," in paragraphs
        assert any("Acme's engineering culture" in p for p in paragraphs)
        assert any(p.startswith("Sincerely,") for p in paragraphs)

    def test_closing_includes_name(self):
        text = build_cover_letter_yaml(_PROFILE, _tailored(), "engineeringresumes")
        doc = yaml.safe_load(text)
        paragraphs = doc["cv"]["sections"]["Cover Letter"]
        assert paragraphs[-1] == "Sincerely,\nJane Doe"

    def test_theme_applied(self):
        text = build_cover_letter_yaml(_PROFILE, _tailored(), "sb2nov")
        doc = yaml.safe_load(text)
        assert doc["design"]["theme"] == "sb2nov"

    def test_no_bold_keywords_setting(self):
        # Unlike the CV, prose shouldn't get keyword-bolding.
        text = build_cover_letter_yaml(_PROFILE, _tailored(), "engineeringresumes")
        doc = yaml.safe_load(text)
        assert "settings" not in doc

    def test_invalid_phone_omitted(self):
        profile = {**_PROFILE, "contact": {**_PROFILE["contact"], "phone": "555-1234"}}
        text = build_cover_letter_yaml(profile, _tailored(), "engineeringresumes")
        doc = yaml.safe_load(text)
        assert "phone" not in doc["cv"]


class TestTailorCoverLetter:
    @pytest.mark.asyncio
    async def test_calls_llm_once(self):
        fake_response = MagicMock()
        fake_response.parsed = _tailored()
        fake_llm = MagicMock()
        fake_llm.invoke = AsyncMock(return_value=fake_response)

        result = await tailor_cover_letter(fake_llm, _PROFILE, _JOB, instructions="Mention my OSS work")

        assert fake_llm.invoke.call_count == 1
        assert result.salutation == "Dear Hiring Manager,"
        call_args = fake_llm.invoke.call_args
        messages = call_args.args[0]
        assert any("Mention my OSS work" in m.text for m in messages if hasattr(m, "text"))


class TestCompileCoverLetterPdf:
    def test_valid_yaml_compiles_to_pdf(self):
        text = build_cover_letter_yaml(_PROFILE, _tailored(), "engineeringresumes")
        pdf_bytes = compile_pdf(text)
        assert pdf_bytes[:4] == b"%PDF"

    def test_invalid_yaml_syntax_raises_yaml_stage_error(self):
        with pytest.raises(CompileError) as exc_info:
            compile_pdf("cv:\n  name: [unterminated")
        assert exc_info.value.stage == "yaml"
