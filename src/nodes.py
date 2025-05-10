import logging

from src.states import InputState
from src.states.job_desc import JobDescription
from src.states.resume import Resume
from src.utils.llm import get_llm
from src.prompts import INGEST_JOB_PROMPT, INGEST_RESUME_PROMPT

logger = logging.getLogger(__name__)

async def ingest_job(state: InputState) -> dict:
    """
    Ingest a job description into a structured format from raw text.

    Args:
        state (InputURL): The input state containing the raw job description text.

    Returns:
        Resume: A structured representation of the resume data.
    """
    llm = get_llm(size='small').with_structured_output(JobDescription)
    prompt = INGEST_JOB_PROMPT.format(job_description_raw=state.job_desc_raw)
    job = await llm.ainvoke(prompt)
    return {'job': job}

async def ingest_resume(state: InputState) -> dict:
    """
    Ingest a resume into a structured format from raw text.

    Args:
        state (InputFile): The input state containing the raw resume text.
    Returns:
        Resume: A structured representation of the resume data.
    """
    llm = get_llm(size='small').with_structured_output(Resume)
    prompt = INGEST_RESUME_PROMPT.format(resume_raw=state.resume_raw)
    resume = await llm.ainvoke(prompt)
    return {'resume': resume}