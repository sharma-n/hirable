import asyncio
import logging

from src.states import FullState, InputState, CoverLetter
from src.states.job_desc import JobDescription
from src.states.resume import (
    Resume,
    BasicInfo,
    Experiences,
    Educations,
    Projects,
    Publications,
    Skills
)
from src.utils.llm import get_llm
from src.prompts import (
    INGEST_JOB_PROMPT,
    INGEST_RESUME_PROMPT,
    ADAPT_SYSTEM_PROMPT,
    ADAPT_BASIC_INFO_PROMPT,
    ADAPT_EXPERIENCES_PROMPT,
    ADAPT_EDUCATION_PROMPT,
    ADAPT_PROJECTS_PROMPT,
    ADAPT_PUBLICATIONS_PROMPT,
    ADAPT_SKILLS_PROMPT,
    COVER_LETTER_PROMPT
)

logger = logging.getLogger(__name__)

async def ingest_job(state: InputState) -> dict:
    """
    Ingest a job description into a structured format from raw text.

    Args:
        state (InputURL): The input state containing the raw job description text.

    Returns:
        Resume: A structured representation of the resume data.
    """
    logger.info("Starting ingest_job function.")
    llm = get_llm(size='small').with_structured_output(JobDescription)
    prompt = INGEST_JOB_PROMPT.format(job_description_raw=state.job_desc_raw)
    job = await llm.ainvoke(prompt)
    logger.info("Finished ingest_job function.")
    return {'job': job}

async def ingest_resume(state: InputState) -> dict:
    """
    Ingest a resume into a structured format from raw text.

    Args:
        state (InputFile): The input state containing the raw resume text.
    Returns:
        Resume: A structured representation of the resume data.
    """
    logger.info("Starting ingest_resume function.")
    llm = get_llm(size='small').with_structured_output(Resume)
    prompt = INGEST_RESUME_PROMPT.format(resume_raw=state.resume_raw)
    resume = await llm.ainvoke(prompt)
    logger.info("Finished ingest_resume function.")
    return {'resume': resume}

async def adapt_resume(state: FullState) -> dict:
    """
    Adapt the resume to the job description.

    Args:
        state (FullState): The state containing the job description and resume.
    
    Returns:
        dict: A dictionary containing the adapted resume.
    """
    logger.info("Starting adapt_resume function.")
    system_prompt = ADAPT_SYSTEM_PROMPT.format(job_description=state.job)

    sections_to_adapt = [
        (ADAPT_BASIC_INFO_PROMPT.format(basic_info=state.resume.basic_info), BasicInfo, 'small'),
        (ADAPT_EXPERIENCES_PROMPT.format(experiences=state.resume.experience), Experiences, 'medium'),
        (ADAPT_EDUCATION_PROMPT.format(education=state.resume.education), Educations, 'small'),
        (ADAPT_PROJECTS_PROMPT.format(projects=state.resume.projects), Projects, 'medium'),
        (ADAPT_PUBLICATIONS_PROMPT.format(publications=state.resume.publications), Publications, 'small'),
        (ADAPT_SKILLS_PROMPT.format(skills=state.resume.skills), Skills, 'small')
    ]

    tasks = []
    for prompt, pydantic_obj, size in sections_to_adapt:
        llm = get_llm(size=size).with_structured_output(pydantic_obj)
        tasks.append(llm.ainvoke(system_prompt + prompt))

    results = await asyncio.gather(*tasks)

    resume_out = Resume(
        basic_info=results[0],
        experience=results[1],
        education=results[2], 
        projects=results[3],
        publications=results[4],
        skills=results[5],
        awards=state.resume.awards,
        certifications=state.resume.certifications,
        languages=state.resume.languages,
        other_info=state.resume.other_info
    )

    return {'resume_out': resume_out}

async def generate_cover_letter(state: FullState) -> dict:
    """
    Generate a custom cover letter based on the job description and adapted resume.
    
    Args:
        state (FullState): The state containing the job description and adapted resume.

    Returns:
        dict: A dictionary containing the generated cover letter.
    """
    logger.info("Starting generate_cover_letter function.")
    llm = get_llm(size='small').with_structured_output(CoverLetter)
    prompt = COVER_LETTER_PROMPT.format(
        job_description=state.job,
        adapted_resume=state.resume_out
    )
    cover_letter = await llm.ainvoke(prompt)
    logger.info("Finished generate_cover_letter function.")
    return {'cover_letter': cover_letter}
