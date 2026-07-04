"""Cover-letter generation: LLM tailoring (prose only) + deterministic RenderCV
YAML assembly. Mirrors tailor.py/build.py's split for the CV — see CLAUDE.md's
M6 notes for the decision to render the letter as a RenderCV document (a
contact header + one section of free-form TextEntry paragraphs) rather than a
separate Typst toolchain, so compile.py/the editor/the preview/versioning are
reused unchanged and the letter shares the CV's theme automatically.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import yaml
from fastapi import HTTPException
from llm_kit import LLMClient, Message
from llm_kit.errors import LLMError, ValidationError

from app.llm.schemas import TailoredCoverLetter
from app.rendercv.build import _build_contact
from app.rendercv.rules import good_resume_rules

_SYSTEM_PROMPT_TEMPLATE = """You are a cover-letter-writing assistant. Given a candidate's master \
profile and a specific job posting, write a short, personalized cover letter — never invent or \
alter facts (employers, dates, metrics) not present in the master profile; only cite real \
qualifications and real proof already in the profile.

Follow §12 of this rulebook (condensed from the project's resume-writing guide) exactly:

{good_resume_rules}

Your output:
- worth_it: true unless this is a well-known large/enterprise company where a cover letter is \
  unlikely to be read (§12) — still write one either way, this is advisory only, the user decides.
- recipient: "Hiring Manager" unless the job posting names a specific person.
- salutation: e.g. "Dear Hiring Manager,".
- body_paragraphs: 3-4 short paragraphs, in this order — (1) the company first, showing you \
  understand its mission/product; (2) demonstrate understanding of the role; (3) tie 2-3 of the \
  candidate's real qualifications to the job's requirements, with proof from the profile; (4) a \
  brief, sincere closing sentence naming the company again. Concise — this is a letter, not a resume; \
  no bullet points, no markdown, no fabricated numbers or employers.
- closing: e.g. "Sincerely,".
"""

_USER_MESSAGE_TEMPLATE = """Candidate's master profile:
{profile_json}

Job posting:
{job_json}
{instructions_block}"""


async def tailor_cover_letter(
    llm: LLMClient,
    profile_data: dict,
    job_parsed: dict,
    instructions: str | None = None,
) -> TailoredCoverLetter:
    """Call the LLM to produce a TailoredCoverLetter for one job."""
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(good_resume_rules=good_resume_rules())
    instructions_block = f"\n\nAdditional instructions from the user:\n{instructions}" if instructions else ""
    user_message = _USER_MESSAGE_TEMPLATE.format(
        profile_json=json.dumps(profile_data),
        job_json=json.dumps(job_parsed),
        instructions_block=instructions_block,
    )
    try:
        result = await llm.invoke(
            [Message.system(system_prompt), Message.user(user_message)],
            response_model=TailoredCoverLetter,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=502, detail=f"LLM returned malformed cover letter data: {exc}"
        ) from exc
    except LLMError as exc:
        raise HTTPException(
            status_code=502, detail=f"LLM error while drafting cover letter: {exc}"
        ) from exc
    return result.parsed


def build_cover_letter_yaml(
    profile_data: dict,
    tailored: TailoredCoverLetter,
    theme: str,
) -> str:
    """Assemble a complete RenderCV YAML document for the cover letter. Facts
    (name, contact details) are copied verbatim from the profile via the same
    ``_build_contact`` helper the CV uses; the letter body is entirely the
    LLM's prose, as a single ``TextEntry`` (plain-string) section — RenderCV
    has no dedicated "letter" entry type, so free-form paragraphs are the
    correct fit (see docs/rendercv.md's TextEntry row)."""
    cv = _build_contact(profile_data.get("contact", {}))

    now = datetime.now(timezone.utc)
    today = f"{now:%B} {now.day}, {now:%Y}"
    name = profile_data.get("contact", {}).get("name", "")
    closing_block = f"{tailored.closing}\n{name}".strip() if tailored.closing or name else ""

    paragraphs = [today, tailored.salutation, *tailored.body_paragraphs, closing_block]
    paragraphs = [p for p in paragraphs if p]

    if paragraphs:
        cv["sections"] = {"Cover Letter": paragraphs}

    doc: dict = {"cv": cv, "design": {"theme": theme}}
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
