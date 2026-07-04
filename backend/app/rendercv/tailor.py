"""LLM-driven CV tailoring — decides *which* profile items to include and how
to reword them for a specific job. Never touches facts (dates, company names,
emails, URLs) — those are copied verbatim from the profile by build.py. See
TailoredCV's docstring in app/llm/schemas.py for why this fits a single
structured-output call (confirmed against the real Anthropic API), unlike
ProfileModel's Part1/Part2 split.
"""
from __future__ import annotations

import json

from fastapi import HTTPException
from llm_kit import LLMClient, Message
from llm_kit.errors import LLMError, ValidationError

from app.llm.schemas import TailoredCV
from app.rendercv.rules import good_resume_rules

_SYSTEM_PROMPT_TEMPLATE = """You are a resume-tailoring assistant. Given a candidate's master \
profile and a specific job posting, decide which profile items to feature in a tailored CV and \
how to present them — never invent or alter facts (dates, company/institution names, emails, \
URLs, degrees) that are not yours to change; those are applied verbatim separately.

Never introduce numbers, metrics, dates, employers, or any fact not present in the master \
profile. If a bullet has no real metric to cite, keep it qualitative — do not fabricate one. \
Bending or inventing facts is disqualifying.

Follow this rulebook (condensed from the project's resume-writing guide):

{good_resume_rules}

Your output:
- summary: a short, tailored professional summary (empty string if not warranted for this \
  candidate's level/situation — see the rulebook's guidance on when a summary helps).
- section_order: ordered list of section names to include, from {{"experience", "projects", \
  "education", "skills", "publications", "extras"}} — most JD-relevant first; omit sections with \
  nothing worth including.
- skills: regrouped/reworded {{label, details}} pairs — JD-relevant tech first, no self-ratings, \
  omit trivial/irrelevant tools.
- experience: return **one entry for every experience item** in the profile, each with its 0-based \
  `index`, an `include` flag, and a rewritten `summary`/`highlights` — quantified, active-voice, \
  JD-mirrored, tech named at the end of each bullet, at least one *real* number per bullet where \
  the profile supports one. Set `include: false` ONLY for an early role that is clearly unrelated \
  to this job AND ended more than 5 years ago; NEVER exclude a role held within the last 5 years, \
  and never exclude one you are unsure about. Make older or less-relevant *included* roles \
  progressively terser (fewer, tighter bullets) rather than dropping them. Do not reorder — CV \
  order follows the profile (reverse-chronological).
- projects: for each project worth including, its 0-based `index` plus a rewritten `summary`/ \
  `highlights` (same bullet rules). Omit projects not worth including for this job — projects are \
  optional. Order = CV order.
- education: return reworded `highlights` for education entries by 0-based `index`. Every degree \
  is always included in the CV regardless — never drop one; provide highlights for each entry \
  worth embellishing (entries you omit still appear, just without reworded highlights).
- publications / extras: 0-based indices only, no rewriting — just which ones are worth \
  including for this job.
"""

_USER_MESSAGE_TEMPLATE = """Master profile (list items are 0-indexed within each list):
{profile_json}

Job posting:
{job_json}
{instructions_block}"""


async def tailor_profile(
    llm: LLMClient,
    profile_data: dict,
    job_parsed: dict,
    instructions: str | None = None,
) -> TailoredCV:
    """Call the LLM to produce a TailoredCV selection/rewrite for one job."""
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
            response_model=TailoredCV,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=502, detail=f"LLM returned malformed tailoring data: {exc}"
        ) from exc
    except LLMError as exc:
        raise HTTPException(
            status_code=502, detail=f"LLM error while tailoring CV: {exc}"
        ) from exc
    return result.parsed
