from langgraph.graph import StateGraph, START, END

from src.states import InputState, OutputState, FullState
from src.nodes import ingest_job, ingest_resume, adapt_resume, generate_cover_letter

def get_graph():
    """
    Get the LangGraph to run hirable.
    """

    builder = StateGraph(FullState, input=InputState, output=OutputState)
    builder.add_node(ingest_resume, "ingest_resume")
    builder.add_node(ingest_job, "ingest_job")
    builder.add_node(adapt_resume, "adapt_resume")
    builder.add_node(generate_cover_letter, "generate_cover_letter")

    builder.add_edge(START, "ingest_resume")
    builder.add_edge(START, "ingest_job")
    builder.add_edge(["ingest_resume", "ingest_job"], "adapt_resume")
    builder.add_edge("adapt_resume", "generate_cover_letter")
    builder.add_edge("generate_cover_letter", END)

    graph = builder.compile()
    return graph
