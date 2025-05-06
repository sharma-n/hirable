import asyncio

from src.agents.ingest_job import get_graph
from src.states.job_desc import InputURL, JobDescription
from src.utils.utils import setup_logging

setup_logging()

if __name__ == "__main__":
    state = InputURL(url='https://www.google.com/about/careers/applications/jobs/results/110690555461018310-software-engineer-iii-infrastructure-core')
    graph = get_graph()
    resume = asyncio.run(graph.ainvoke(input=state))
    print(JobDescription(**resume))