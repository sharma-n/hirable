import logging
from langgraph.graph import StateGraph, START, END

from src.states import InputState, OutputState, FullState
from src.nodes import ingest_job, ingest_resume, adapt_resume, generate_cover_letter, load_resume_from_yaml_node

logger = logging.getLogger(__name__)

def get_graph():
    """
    Get the LangGraph to run hirable.
    """

    builder = StateGraph(FullState, input=InputState, output=OutputState)
    builder.add_node(ingest_resume, "ingest_resume")
    builder.add_node(ingest_job, "ingest_job")
    builder.add_node(load_resume_from_yaml_node, "load_resume_from_yaml_node")
    builder.add_node(adapt_resume, "adapt_resume")
    builder.add_node(generate_cover_letter, "generate_cover_letter")

    def select_resume_ingestion_path(state: FullState):
        if state.resume_yaml:
            logger.info("Resume YAML provided, loading resume from YAML.")
            return "load_resume_from_yaml_node"
        else:
            logger.info("No resume YAML path provided, ingesting resume from raw text.")
            return "ingest_resume"

    builder.add_edge(START, "ingest_job")
    builder.add_conditional_edges(START, select_resume_ingestion_path)
    builder.add_edge(["ingest_job", "load_resume_from_yaml_node"], "adapt_resume")
    builder.add_edge(["ingest_job", "ingest_resume"], "adapt_resume")
    builder.add_edge("adapt_resume", "generate_cover_letter")
    builder.add_edge("generate_cover_letter", END)

    graph = builder.compile()
    return graph
