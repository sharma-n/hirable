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
