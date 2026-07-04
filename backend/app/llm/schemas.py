from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _require(*names: str):
    """Force ``names`` into the emitted JSON-Schema ``required`` list.

    Every field below keeps a Python default, so ``ProfileModel`` stays leniently
    constructible (partial kwargs in tests, partial payloads on ``PUT``). But the
    schema we hand the LLM for structured output marks every field required —
    the LLM is instructed (see ``parsing/profile.py``) to emit ``""``/``[]`` for
    absent data instead of omitting the key. This keeps the emitted schema
    slightly smaller/simpler for Anthropic's structured-output grammar compiler,
    though it is NOT sufficient on its own to dodge the "compiled grammar is too
    large" 400 — see ``parsing/profile.py`` for why ``ProfileModel`` extraction
    is split into two calls.
    """

    def _extra(schema: dict[str, Any]) -> None:
        schema["required"] = list(names)

    return _extra


class SocialNetworkItem(BaseModel):
    model_config = ConfigDict(json_schema_extra=_require("network", "username"))

    network: str = ""   # LinkedIn, GitHub, GitLab, X, etc.
    username: str = ""


class ContactInfo(BaseModel):
    model_config = ConfigDict(
        json_schema_extra=_require(
            "name", "headline", "email", "phone", "location", "website",
            "social_networks", "links",
        )
    )

    name: str = ""
    headline: str = ""  # professional tagline (RenderCV cv.headline)
    email: str = ""
    phone: str = ""
    location: str = ""
    website: str = ""
    social_networks: list[SocialNetworkItem] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)  # generic URLs not covered by social_networks


class ExperienceItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra=_require(
            "company", "position", "start_date", "end_date", "date",
            "location", "summary", "highlights", "tech",
        )
    )

    company: str = ""
    position: str = ""       # RenderCV ExperienceEntry.position
    start_date: str = ""     # RenderCV start_date (YYYY-MM or YYYY)
    end_date: str = ""       # RenderCV end_date ("present" or YYYY-MM)
    date: str = ""           # RenderCV date — free-form; mutually exclusive with start/end
    location: str = ""
    summary: str = ""        # RenderCV entry summary (above highlights)
    highlights: list[str] = Field(default_factory=list)  # RenderCV highlights / bullet points
    tech: list[str] = Field(default_factory=list)        # our extension: tech stack


class ProjectItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra=_require(
            "name", "link", "start_date", "end_date", "date",
            "location", "summary", "highlights", "tech",
        )
    )

    name: str = ""
    link: str = ""           # our extension: project URL
    start_date: str = ""
    end_date: str = ""
    date: str = ""
    location: str = ""
    summary: str = ""
    highlights: list[str] = Field(default_factory=list)
    tech: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra=_require(
            "institution", "area", "degree", "start_date", "end_date",
            "date", "location", "summary", "highlights",
        )
    )

    institution: str = ""
    area: str = ""           # RenderCV EducationEntry.area (field of study)
    degree: str = ""         # e.g. "B.S.", "M.S.", "PhD"
    start_date: str = ""
    end_date: str = ""
    date: str = ""
    location: str = ""
    summary: str = ""
    highlights: list[str] = Field(default_factory=list)


class SkillItem(BaseModel):
    model_config = ConfigDict(json_schema_extra=_require("label", "details"))

    label: str = ""          # RenderCV OneLineEntry.label (e.g. "Programming Languages")
    details: str = ""        # RenderCV OneLineEntry.details (e.g. "Python, Go, TypeScript")


class PublicationItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra=_require(
            "title", "authors", "doi", "url", "journal", "summary", "date"
        )
    )

    title: str = ""
    authors: list[str] = Field(default_factory=list)  # use "*Name*" to highlight self
    doi: str = ""
    url: str = ""
    journal: str = ""
    summary: str = ""
    date: str = ""


class ExtrasItem(BaseModel):
    model_config = ConfigDict(json_schema_extra=_require("title", "highlights", "tech"))

    title: str = ""          # section label (maps to NormalEntry.name or BulletEntry)
    highlights: list[str] = Field(default_factory=list)
    tech: list[str] = Field(default_factory=list)


class EnrichmentItem(BaseModel):
    model_config = ConfigDict(json_schema_extra=_require("key", "value"))

    key: str = ""
    value: str = ""


class ProfileModel(BaseModel):
    model_config = ConfigDict(
        json_schema_extra=_require(
            "contact", "summary", "skills", "experience", "projects",
            "publications", "education", "extras", "enrichment",
        )
    )

    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str = ""
    skills: list[SkillItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    publications: list[PublicationItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    extras: list[ExtrasItem] = Field(default_factory=list)
    enrichment: list[EnrichmentItem] = Field(default_factory=list)


class ProfileModelPart1(BaseModel):
    """First half of ``ProfileModel`` extraction — see ``parsing/profile.py``.

    Anthropic's structured-output grammar compiler rejects the full 9-field
    ``ProfileModel`` schema with a 400 ("compiled grammar is too large"). Bisection
    showed the four nested list-of-object fields — ``experience``, ``projects``,
    ``education``, ``publications`` — are the heavy contributors: any 3 of the 4
    fit under the limit together with the light fields, but all 4 together do not.
    Grammar size is a function of the schema alone, not resume content/length.
    This half carries ``experience`` + ``projects`` (2 heavy fields) plus the
    lightweight identity fields, leaving comfortable margin under the limit.
    """

    model_config = ConfigDict(
        json_schema_extra=_require("contact", "summary", "skills", "experience", "projects")
    )

    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str = ""
    skills: list[SkillItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)


class ProfileModelPart2(BaseModel):
    """Second half of ``ProfileModel`` extraction — see ``ProfileModelPart1``."""

    model_config = ConfigDict(
        json_schema_extra=_require("education", "publications", "extras", "enrichment")
    )

    education: list[EducationItem] = Field(default_factory=list)
    publications: list[PublicationItem] = Field(default_factory=list)
    extras: list[ExtrasItem] = Field(default_factory=list)
    enrichment: list[EnrichmentItem] = Field(default_factory=list)


class TailoredEntry(BaseModel):
    """Tailoring decision for one experience/project item, referenced by its
    index into the master profile's list. The LLM never re-emits company
    names, dates, or links — only which items to include (by index, in CV
    order) and how to reword their summary/highlights for this job. See
    ``backend/app/rendercv/tailor.py``."""

    model_config = ConfigDict(json_schema_extra=_require("index", "summary", "highlights"))

    index: int
    summary: str = ""
    highlights: list[str] = Field(default_factory=list)


class TailoredEducationEntry(BaseModel):
    model_config = ConfigDict(json_schema_extra=_require("index", "highlights"))

    index: int
    highlights: list[str] = Field(default_factory=list)


class TailoredCV(BaseModel):
    """LLM output for CV tailoring — a *selection and rewording* of the master
    profile's content for one job, never the facts themselves (dates, company
    names, emails, URLs are copied verbatim from the profile in Python — see
    ``backend/app/rendercv/build.py``). Index-based selection keeps this schema
    far lighter than ``ProfileModel`` per item (2-3 fields vs. 7-9) and
    structurally rules out factual hallucination.

    Unlike ``ProfileModel``, this fits in a single ``llm.invoke()`` call —
    confirmed against the real Anthropic API with an 8-experience/4-project
    profile (502 completion tokens, no grammar-size 400). If a future field
    addition makes this schema heavier, re-bisect per ``ProfileModel``'s
    Part1/Part2 precedent rather than assuming margin still exists.
    """

    model_config = ConfigDict(
        json_schema_extra=_require(
            "summary", "section_order", "skills", "experience", "projects",
            "education", "publications", "extras",
        )
    )

    summary: str = ""
    section_order: list[str] = Field(default_factory=list)
    skills: list[SkillItem] = Field(default_factory=list)
    experience: list[TailoredEntry] = Field(default_factory=list)
    projects: list[TailoredEntry] = Field(default_factory=list)
    education: list[TailoredEducationEntry] = Field(default_factory=list)
    publications: list[int] = Field(default_factory=list)
    extras: list[int] = Field(default_factory=list)


class JobModel(BaseModel):
    """Structured extraction of a job posting — see ``parsing/jobs.py``.

    Unlike ``ProfileModel``, every field here is a scalar string or a flat
    ``list[str]`` — no nested list-of-object fields — so this has stayed under
    Anthropic's structured-output grammar-size limit in a single ``llm.invoke()``
    call (the M2 "compiled grammar is too large" 400 was traced specifically to
    nested list-of-object fields like ``ExperienceItem``, not flat schemas). If a
    future field addition makes this nested, re-bisect per the ``ProfileModel``
    gotcha rather than assuming margin still exists.
    """

    model_config = ConfigDict(
        json_schema_extra=_require(
            "company", "title", "location", "responsibilities", "must_have",
            "nice_to_have", "keywords", "why_opened_guess", "seniority",
            "company_type", "team_name", "team_description",
        )
    )

    company: str = ""
    title: str = ""
    location: str = ""
    responsibilities: list[str] = Field(default_factory=list)  # what the role actually does
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)  # skills/tools/terms for résumé-tailoring
    why_opened_guess: str = ""
    seniority: str = ""       # e.g. junior/mid/senior/staff/principal/lead/manager/director
    company_type: str = ""    # e.g. startup/scaleup/enterprise/agency/nonprofit/government
    team_name: str = ""       # specific hiring team, e.g. "Payments Platform" — "" if not stated
    team_description: str = ""  # one-line team focus/mission — "" if not stated
