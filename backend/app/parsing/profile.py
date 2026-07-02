from __future__ import annotations

import asyncio

from fastapi import HTTPException
from llm_kit import LLMClient, Message
from llm_kit.errors import LLMError, ValidationError

from app.llm.schemas import ProfileModel, ProfileModelPart1, ProfileModelPart2

_SYSTEM_PROMPT = """You are a resume parser. Extract every piece of information from the resume into the structured JSON schema provided.

Rules:
- Extract ALL experience, education, and project entries — do not omit any.
- contact.headline: the person's professional tagline or title if present (e.g. "Senior Software Engineer").
- contact.social_networks: extract LinkedIn, GitHub, GitLab, X, etc. as {network, username} pairs.
- contact.website: personal website/portfolio URL (not social networks).
- contact.links: any remaining URLs not captured as social_networks or website.
- experience[].position: job title. experience[].company: employer name.
- experience[].highlights: each bullet point as a separate string, without leading dashes or asterisks.
- experience[].tech: technology/tool names explicitly mentioned in that entry.
- experience[].start_date / end_date: use "YYYY-MM" format if month is available, "YYYY" otherwise. Use "present" for current roles. Use date (free-form) only when a range cannot be parsed.
- projects[].highlights: bullet points. projects[].tech: tech stack.
- education[].area: field of study. education[].degree: degree level (B.S., M.S., PhD, etc.).
- education[].highlights: notable achievements, GPA, honours, coursework.
- skills: list of {label, details} pairs — group related skills (e.g. label="Languages" details="Python, Go, TypeScript").
- publications: extract any papers, articles, or books with title, authors, journal, doi, url, date.
- extras: use for patents, talks, awards, certifications, volunteering, interests. Each entry has title and highlights list.
- enrichment: leave as empty list — populated later by the assistant.
- If a field is absent from the resume, leave it as an empty string or empty list. Do NOT fabricate information.
"""


async def parse_resume(llm: LLMClient, raw_text: str) -> ProfileModel:
    """Call the LLM to extract a structured ProfileModel from raw resume text.

    Extraction is split into two concurrent structured-output calls rather than
    one. Anthropic's structured-output grammar compiler 400s on the full 9-field
    ``ProfileModel`` schema ("compiled grammar is too large") — bisection showed
    the four nested list-of-object fields (``experience``, ``projects``,
    ``education``, ``publications``) are the heavy contributors; any 3 of the 4
    fit under the limit, all 4 together do not. ``ProfileModelPart1`` carries
    ``experience`` + ``projects`` (2 heavy fields), ``ProfileModelPart2`` carries
    ``education`` + ``publications`` — well under the limit with margin to spare.
    """
    user_msg = Message.user(f"Parse the following resume:\n\n{raw_text}")
    try:
        part1_result, part2_result = await asyncio.gather(
            llm.invoke(
                [Message.system(_SYSTEM_PROMPT), user_msg], response_model=ProfileModelPart1
            ),
            llm.invoke(
                [Message.system(_SYSTEM_PROMPT), user_msg], response_model=ProfileModelPart2
            ),
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM returned malformed profile data: {exc}",
        ) from exc
    except LLMError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM error during resume parsing: {exc}",
        ) from exc

    part1: ProfileModelPart1 = part1_result.parsed
    part2: ProfileModelPart2 = part2_result.parsed
    return ProfileModel(
        contact=part1.contact,
        summary=part1.summary,
        skills=part1.skills,
        experience=part1.experience,
        projects=part1.projects,
        education=part2.education,
        publications=part2.publications,
        extras=part2.extras,
        enrichment=part2.enrichment,
    )
