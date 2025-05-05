import asyncio

from src.agents.ingest_resume import get_graph
from src.states.resume import InputFile
from src.utils.utils import setup_logging

setup_logging()

if __name__ == "__main__":
    state = InputFile(filepath='data/Resume_example.pdf')
    graph = get_graph()
    resume = asyncio.run(graph.ainvoke(input=state))
    print(str(resume))