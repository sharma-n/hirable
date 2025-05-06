import asyncio
import logging
from langgraph.graph import StateGraph, START, END

from src.states.resume import InputFile, Resume, FullState
from src.prompts import INGEST_RESUME_PROMPT
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)

async def ingest_resume(state: InputFile) -> Resume:
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
    return resume

def get_graph():
    """
    Get the LangGraph for the resume ingestion process.
    """

    builder = StateGraph(FullState, input=InputFile, output=Resume)
    builder.add_node(ingest_resume, "ingest_resume")

    builder.add_edge(START, "ingest_resume")
    builder.add_edge("ingest_resume", END)

    graph = builder.compile()
    return graph
