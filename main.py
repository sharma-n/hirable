import asyncio

from src.graph import get_graph
from src.states import InputState
from src.utils.utils import setup_logging

setup_logging()

if __name__ == "__main__":
    state = InputState(
        job_url='https://www.google.com/about/careers/applications/jobs/results/110690555461018310-software-engineer-iii-infrastructure-core',
        resume_path='data/Resume_example.pdf'
    )
    graph = get_graph()
    output = asyncio.run(graph.ainvoke(input=state))
    print("--- Parsed Resume ---")
    print(output['resume'])
    print("--- Parsed Job Description ---")
    print(output['job'])
    print("--- Adapted Resume ---")
    print(output['resume_out'])
    print("--- Cover Letter ---")
    print(output['cover_letter'])