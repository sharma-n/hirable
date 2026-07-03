from __future__ import annotations

import logging

import trafilatura
from fastapi import HTTPException
from llm_kit import LLMClient, Message
from llm_kit.errors import LLMError, ValidationError

from app.llm.schemas import JobModel

logger = logging.getLogger("app.jobs")

_MAX_RAW_TEXT_CHARS = 50_000

_SYSTEM_PROMPT = """You are a job-posting parser. Extract structured fields from the job description text into the schema provided.

Rules:
- company: employer name. title: the job title/role.
- location: city/region, or "Remote" if remote-first, or "" if not stated.
- responsibilities: what the role actually does day-to-day, one per string, without leading dashes or asterisks. This is distinct from must_have/nice_to_have — it describes the job, not the candidate.
- must_have: required qualifications/skills for the candidate, one per string.
- nice_to_have: preferred-but-optional qualifications, one per string.
- keywords: notable skills/tools/technologies/domain terms worth echoing in a tailored resume.
- why_opened_guess: a one-sentence inference of why this role likely opened (growth, backfill, new team, etc.) based on posting language — say so if the text gives no signal.
- seniority: one of junior/mid/senior/staff/principal/lead/manager/director, best guess from title+text.
- company_type: one of startup/scaleup/enterprise/agency/nonprofit/government, best guess.
- team_name: the specific hiring team's name if the posting names one (e.g. "Payments Platform"), otherwise "".
- team_description: a one-line description of that team's focus/mission if stated, otherwise "".
- If a field cannot be determined, leave it as an empty string or empty list. Do NOT fabricate.
"""


def fetch_job_text(url: str) -> str | None:
    """Fetch and extract the main content of a job posting URL via trafilatura.

    Returns None on any failure — blocked response, empty body, or extraction
    producing no usable text. Never raises: many job boards block bots (403,
    empty body, JS-rendered shell), and that is an expected, not exceptional,
    outcome here. The caller treats None as the `needs_paste` signal.
    """
    try:
        html = trafilatura.fetch_url(url)
        if not html:
            logger.info("job fetch: blocked/empty response url=%s", url)
            return None
        text = trafilatura.extract(html, url=url, include_comments=False, include_tables=False)
        if not text or not text.strip():
            logger.info("job fetch: extraction produced no text url=%s", url)
            return None
        return text
    except Exception:
        logger.exception("job fetch: unexpected error url=%s", url)
        return None


async def parse_job(llm: LLMClient, raw_text: str) -> JobModel:
    """Call the LLM to extract a structured JobModel from raw job-posting text.

    JobModel is flat (no nested list-of-object fields), so a single
    llm.invoke() call is expected to work — unlike parse_resume()'s
    Part1/Part2 split, which was needed only because of ProfileModel's nested
    list-of-object fields. See JobModel's docstring if this ever 400s.
    """
    if len(raw_text) > _MAX_RAW_TEXT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Job posting text too large (max {_MAX_RAW_TEXT_CHARS} characters)",
        )
    try:
        result = await llm.invoke(
            [
                Message.system(_SYSTEM_PROMPT),
                Message.user(f"Parse the following job posting:\n\n{raw_text}"),
            ],
            response_model=JobModel,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=502, detail=f"LLM returned malformed job data: {exc}"
        ) from exc
    except LLMError as exc:
        raise HTTPException(
            status_code=502, detail=f"LLM error during job parsing: {exc}"
        ) from exc
    return result.parsed
