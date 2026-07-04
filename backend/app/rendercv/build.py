"""Deterministic assembly of a RenderCV YAML document from a master profile +
a TailoredCV selection. Facts (company/institution names, dates, contact
details, links) are copied verbatim from the profile — never LLM-generated —
so there is no factual-hallucination surface here. See app/llm/schemas.py's
TailoredCV docstring and CLAUDE.md's "RenderCV integration" mapping table.
"""
from __future__ import annotations

import re

import yaml

from app.llm.schemas import TailoredCV

_PHONE_RE = re.compile(r"^\+[1-9]\d{6,14}$")  # E.164
_KNOWN_SOCIAL_NETWORKS = {
    "linkedin": "LinkedIn", "github": "GitHub", "gitlab": "GitLab", "imdb": "IMDB",
    "instagram": "Instagram", "orcid": "ORCID", "mastodon": "Mastodon",
    "stackoverflow": "StackOverflow", "researchgate": "ResearchGate", "youtube": "YouTube",
    "google scholar": "Google Scholar", "telegram": "Telegram", "whatsapp": "WhatsApp",
    "leetcode": "Leetcode", "x": "X", "twitter": "X", "bluesky": "Bluesky", "reddit": "Reddit",
}
_MAX_BOLD_KEYWORDS = 15


def _dates(item: dict) -> dict:
    """RenderCV's date/start_date/end_date are mutually exclusive; prefer the
    structured range when present, falling back to the free-form date."""
    if item.get("start_date"):
        out = {"start_date": item["start_date"]}
        if item.get("end_date"):
            out["end_date"] = item["end_date"]
        return out
    if item.get("date"):
        return {"date": item["date"]}
    return {}


def _build_contact(contact: dict) -> dict:
    cv: dict = {}
    if contact.get("name"):
        cv["name"] = contact["name"]
    if contact.get("headline"):
        cv["headline"] = contact["headline"]
    if contact.get("location"):
        cv["location"] = contact["location"]
    if contact.get("email") and "@" in contact["email"]:
        cv["email"] = contact["email"]
    phone = contact.get("phone", "")
    if phone and _PHONE_RE.match(phone):
        cv["phone"] = phone
    website = contact.get("website", "")
    if website and website.startswith(("http://", "https://")):
        cv["website"] = website
    networks = []
    for net in contact.get("social_networks", []):
        canonical = _KNOWN_SOCIAL_NETWORKS.get(net.get("network", "").strip().lower())
        if canonical and net.get("username"):
            networks.append({"network": canonical, "username": net["username"]})
    if networks:
        cv["social_networks"] = networks
    return cv


def _build_experience_section(profile_experience: list[dict], tailored: list) -> list[dict]:
    entries = []
    for t in tailored:
        if not (0 <= t.index < len(profile_experience)):
            continue
        item = profile_experience[t.index]
        entry = {"company": item.get("company", ""), "position": item.get("position", "")}
        entry.update(_dates(item))
        if item.get("location"):
            entry["location"] = item["location"]
        if t.summary:
            entry["summary"] = t.summary
        if t.highlights:
            entry["highlights"] = t.highlights
        entries.append(entry)
    return entries


def _build_projects_section(profile_projects: list[dict], tailored: list) -> list[dict]:
    entries = []
    for t in tailored:
        if not (0 <= t.index < len(profile_projects)):
            continue
        item = profile_projects[t.index]
        name = item.get("name", "")
        if item.get("link"):
            name = f"[{name}]({item['link']})"
        entry: dict = {"name": name}
        entry.update(_dates(item))
        if item.get("location"):
            entry["location"] = item["location"]
        if t.summary:
            entry["summary"] = t.summary
        if t.highlights:
            entry["highlights"] = t.highlights
        entries.append(entry)
    return entries


def _build_education_section(profile_education: list[dict], tailored: list) -> list[dict]:
    entries = []
    for t in tailored:
        if not (0 <= t.index < len(profile_education)):
            continue
        item = profile_education[t.index]
        entry = {"institution": item.get("institution", ""), "area": item.get("area", "")}
        if item.get("degree"):
            entry["degree"] = item["degree"]
        entry.update(_dates(item))
        if item.get("location"):
            entry["location"] = item["location"]
        if item.get("summary"):
            entry["summary"] = item["summary"]
        if t.highlights:
            entry["highlights"] = t.highlights
        entries.append(entry)
    return entries


def _build_publications_section(profile_publications: list[dict], indices: list[int]) -> list[dict]:
    entries = []
    for i in indices:
        if not (0 <= i < len(profile_publications)):
            continue
        item = profile_publications[i]
        entry = {"title": item.get("title", ""), "authors": item.get("authors", [])}
        for field in ("doi", "url", "journal", "summary", "date"):
            if item.get(field):
                entry[field] = item[field]
        entries.append(entry)
    return entries


def _build_extras_section(profile_extras: list[dict], indices: list[int]) -> list[dict]:
    entries = []
    for i in indices:
        if not (0 <= i < len(profile_extras)):
            continue
        item = profile_extras[i]
        entry: dict = {"name": item.get("title", "")}
        if item.get("highlights"):
            entry["highlights"] = item["highlights"]
        entries.append(entry)
    return entries


_SECTION_TITLES = {
    "experience": "Experience",
    "projects": "Projects",
    "education": "Education",
    "skills": "Skills",
    "publications": "Publications",
    "extras": "Extras",
}


def build_rendercv_yaml(
    profile_data: dict,
    tailored: TailoredCV,
    job_parsed: dict,
    theme: str,
) -> str:
    """Assemble a complete RenderCV YAML document. Never raises on bad/missing
    profile data — omits fields that don't parse rather than producing invalid
    YAML; rendercv's own validation (at compile time) is the final gate."""
    sections: dict[str, list] = {}

    built = {
        "experience": _build_experience_section(profile_data.get("experience", []), tailored.experience),
        "projects": _build_projects_section(profile_data.get("projects", []), tailored.projects),
        "education": _build_education_section(profile_data.get("education", []), tailored.education),
        "skills": [
            {"label": s.label, "details": s.details} for s in tailored.skills if s.label or s.details
        ],
        "publications": _build_publications_section(
            profile_data.get("publications", []), tailored.publications
        ),
        "extras": _build_extras_section(profile_data.get("extras", []), tailored.extras),
    }

    # Cv has no top-level "summary" field — a tailored summary is its own
    # TextEntry (plain-string) section, placed first per good_resume.md §11.
    if tailored.summary:
        sections["Summary"] = [tailored.summary]

    # Order per the LLM's section_order, then append any non-empty section it
    # omitted (safety net — never silently drop content the LLM forgot to order).
    order = [s for s in tailored.section_order if s in built]
    order += [s for s in built if s not in order]
    for key in order:
        entries = built[key]
        if entries:
            sections[_SECTION_TITLES[key]] = entries

    cv: dict = _build_contact(profile_data.get("contact", {}))
    if tailored.summary:
        cv.pop("headline", None)  # summary already covers this — avoid duplicating it
    if sections:
        cv["sections"] = sections

    doc: dict = {"cv": cv, "design": {"theme": theme}}

    bold_keywords = [k for k in job_parsed.get("keywords", []) if k][:_MAX_BOLD_KEYWORDS]
    if bold_keywords:
        doc["settings"] = {"bold_keywords": bold_keywords}

    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
