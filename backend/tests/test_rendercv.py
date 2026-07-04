"""M5 rendercv module — YAML builder, tailoring, and real Typst compilation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from app.llm.schemas import TailoredCV, TailoredEducationEntry, TailoredEntry
from app.rendercv.build import build_rendercv_yaml
from app.rendercv.compile import CompileError, compile_pdf
from app.rendercv.tailor import tailor_profile

_PROFILE = {
    "contact": {
        "name": "Jane Doe",
        "headline": "Senior Software Engineer",
        "email": "jane@example.com",
        "phone": "+14155552671",
        "location": "Remote",
        "website": "https://janedoe.dev",
        "social_networks": [
            {"network": "GitHub", "username": "janedoe"},
            {"network": "CarrierPigeon", "username": "irrelevant"},
        ],
        "links": ["https://extra-link.example.com"],
    },
    "summary": "Untailored master summary.",
    "skills": [{"label": "Languages", "details": "Python, Go"}],
    "experience": [
        {
            "company": "Acme: The Company",
            "position": "Engineer",
            "start_date": "2020-01",
            "end_date": "2022-01",
            "date": "",
            "location": "Remote",
            "summary": "",
            "highlights": ["Old highlight"],
            "tech": ["Python"],
        },
        {
            "company": "Second Co",
            "position": "Senior Engineer",
            "start_date": "",
            "end_date": "",
            "date": "2022 - present",
            "location": "NYC",
            "summary": "",
            "highlights": ["Another old highlight"],
            "tech": ["Go"],
        },
    ],
    "projects": [
        {
            "name": "Cool Project",
            "link": "https://github.com/janedoe/cool",
            "start_date": "2021-01",
            "end_date": "present",
            "date": "",
            "location": "",
            "summary": "",
            "highlights": ["did stuff"],
            "tech": ["Rust"],
        }
    ],
    "education": [
        {
            "institution": "State University",
            "area": "Computer Science",
            "degree": "B.S.",
            "start_date": "2016-09",
            "end_date": "2020-06",
            "date": "",
            "location": "",
            "summary": "",
            "highlights": ["GPA: 3.9/4.0"],
        }
    ],
    "publications": [
        {
            "title": "A Paper: On Things",
            "authors": ["*Jane Doe*"],
            "doi": "10.1/x",
            "url": "",
            "journal": "Some Journal",
            "summary": "",
            "date": "2019",
        }
    ],
    "extras": [{"title": "Patents", "highlights": ["Patent: caching thing"], "tech": []}],
    "enrichment": [],
}

_JOB = {"keywords": ["Python", "Go", "Distributed Systems"] + [f"kw{i}" for i in range(20)]}


def _tailored(**overrides) -> TailoredCV:
    base = dict(
        summary="Tailored: quantified summary.",
        section_order=["experience", "projects", "education", "skills"],
        skills=[],
        experience=[TailoredEntry(index=0, summary="Tailored role", highlights=["Did X: measured by Y"])],
        projects=[],
        education=[TailoredEducationEntry(index=0, highlights=["GPA: 3.9"])],
        publications=[0],
        extras=[0],
    )
    base.update(overrides)
    return TailoredCV(**base)


class TestBuildRenderCVYaml:
    def test_contact_fields_mapped(self):
        text = build_rendercv_yaml(_PROFILE, _tailored(), _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        cv = doc["cv"]
        assert cv["name"] == "Jane Doe"
        assert "headline" not in cv  # dropped when summary is present
        assert cv["email"] == "jane@example.com"
        assert cv["phone"] == "+14155552671"
        assert cv["website"] == "https://janedoe.dev"

    def test_headline_kept_when_no_summary(self):
        text = build_rendercv_yaml(_PROFILE, _tailored(summary=""), _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        cv = doc["cv"]
        assert cv["headline"] == "Senior Software Engineer"
        assert "Summary" not in doc["cv"].get("sections", {})

    def test_unknown_social_network_dropped(self):
        text = build_rendercv_yaml(_PROFILE, _tailored(), _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        networks = doc["cv"]["social_networks"]
        assert len(networks) == 1
        assert networks[0] == {"network": "GitHub", "username": "janedoe"}

    def test_colon_in_company_name_survives_roundtrip(self):
        text = build_rendercv_yaml(_PROFILE, _tailored(), _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        experience = doc["cv"]["sections"]["Experience"]
        assert experience[0]["company"] == "Acme: The Company"

    def test_experience_uses_tailored_content_not_profile_summary(self):
        text = build_rendercv_yaml(_PROFILE, _tailored(), _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        entry = doc["cv"]["sections"]["Experience"][0]
        assert entry["summary"] == "Tailored role"
        assert entry["highlights"] == ["Did X: measured by Y"]
        assert entry["company"] == "Acme: The Company"  # facts still verbatim

    def test_start_end_date_preferred_over_free_form_date(self):
        text = build_rendercv_yaml(_PROFILE, _tailored(), _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        entry = doc["cv"]["sections"]["Experience"][0]
        assert entry["start_date"] == "2020-01"
        assert entry["end_date"] == "2022-01"
        assert "date" not in entry

    def test_free_form_date_used_when_no_start_date(self):
        tailored = _tailored(
            experience=[TailoredEntry(index=1, summary="s", highlights=["h"])]
        )
        text = build_rendercv_yaml(_PROFILE, tailored, _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        entry = doc["cv"]["sections"]["Experience"][0]
        assert entry["date"] == "2022 - present"
        assert "start_date" not in entry

    def test_empty_sections_omitted(self):
        tailored = _tailored(projects=[], education=[], publications=[], extras=[], skills=[])
        text = build_rendercv_yaml(_PROFILE, tailored, _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        sections = doc["cv"].get("sections", {})
        assert "Projects" not in sections
        assert "Education" not in sections
        assert "Publications" not in sections
        assert "Extras" not in sections

    def test_out_of_range_index_skipped_without_crash(self):
        tailored = _tailored(
            experience=[TailoredEntry(index=99, summary="s", highlights=["h"])]
        )
        text = build_rendercv_yaml(_PROFILE, tailored, _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        assert "Experience" not in doc["cv"].get("sections", {})

    def test_summary_becomes_text_entry_section(self):
        text = build_rendercv_yaml(_PROFILE, _tailored(), _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        assert doc["cv"]["sections"]["Summary"] == ["Tailored: quantified summary."]
        assert "summary" not in doc["cv"]  # Cv has no top-level summary field

    def test_invalid_phone_and_website_omitted(self):
        profile = {**_PROFILE, "contact": {**_PROFILE["contact"], "phone": "555-1234", "website": "not-a-url"}}
        text = build_rendercv_yaml(profile, _tailored(), _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        assert "phone" not in doc["cv"]
        assert "website" not in doc["cv"]

    def test_bold_keywords_capped(self):
        text = build_rendercv_yaml(_PROFILE, _tailored(), _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        assert len(doc["settings"]["bold_keywords"]) == 15

    def test_theme_applied(self):
        text = build_rendercv_yaml(_PROFILE, _tailored(), _JOB, "sb2nov")
        doc = yaml.safe_load(text)
        assert doc["design"]["theme"] == "sb2nov"

    def test_publication_and_extras_selected_by_index_verbatim(self):
        text = build_rendercv_yaml(_PROFILE, _tailored(), _JOB, "engineeringresumes")
        doc = yaml.safe_load(text)
        pub = doc["cv"]["sections"]["Publications"][0]
        assert pub["title"] == "A Paper: On Things"
        extra = doc["cv"]["sections"]["Extras"][0]
        assert extra["name"] == "Patents"
        assert extra["highlights"] == ["Patent: caching thing"]


class TestTailorProfile:
    @pytest.mark.asyncio
    async def test_calls_llm_once(self):
        fake_response = MagicMock()
        fake_response.parsed = _tailored()
        fake_llm = MagicMock()
        fake_llm.invoke = AsyncMock(return_value=fake_response)

        result = await tailor_profile(fake_llm, _PROFILE, _JOB, instructions="Emphasize Go")

        assert fake_llm.invoke.call_count == 1
        assert result.summary == "Tailored: quantified summary."
        # Instructions get folded into the user message.
        call_args = fake_llm.invoke.call_args
        messages = call_args.args[0]
        assert any("Emphasize Go" in m.text for m in messages if hasattr(m, "text"))


class TestCompilePdf:
    def test_valid_yaml_compiles_to_pdf(self):
        text = build_rendercv_yaml(_PROFILE, _tailored(), _JOB, "engineeringresumes")
        pdf_bytes = compile_pdf(text)
        assert pdf_bytes[:4] == b"%PDF"

    def test_invalid_yaml_syntax_raises_yaml_stage_error(self):
        with pytest.raises(CompileError) as exc_info:
            compile_pdf("cv:\n  name: [unterminated")
        assert exc_info.value.stage == "yaml"

    def test_schema_violation_raises_schema_stage_error(self):
        # phone must be E.164 — this is a schema-level validation failure, not YAML syntax.
        bad_yaml = "cv:\n  name: Jane Doe\n  phone: \"555-1234\"\n"
        with pytest.raises(CompileError) as exc_info:
            compile_pdf(bad_yaml)
        assert exc_info.value.stage == "schema"
