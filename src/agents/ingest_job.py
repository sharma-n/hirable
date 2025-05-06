import asyncio
import logging
from langgraph.graph import StateGraph, START, END

from src.states.job_desc import InputURL, JobDescription, FullState
from src.prompts import INGEST_JOB_PROMPT
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)

async def ingest_job(state: InputURL) -> JobDescription:
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
    return job

def get_graph():
    """
    Get the LangGraph for the job ingestion process.
    """

    builder = StateGraph(FullState, input=InputURL, output=JobDescription)
    builder.add_node(ingest_job, "ingest_job")

    builder.add_edge(START, "ingest_job")
    builder.add_edge("ingest_job", END)

    graph = builder.compile()
    return graph
