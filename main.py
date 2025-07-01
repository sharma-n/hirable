import asyncio
import yaml
from src.graph import get_graph
from src.states import InputState
from src.utils.utils import setup_logging
from src.utils.parse import parse_file

setup_logging()

if __name__ == "__main__":
    graph = get_graph()

    # Example 1: Parse resume from raw file and save to YAML
    print("\n--- Running example 1: Parsing resume from raw file and saving to YAML ---")
    state_raw_resume = InputState(
        job_url='https://www.google.com/about/careers/applications/jobs/results/110690555461018310-software-engineer-iii-infrastructure-core',
        resume_raw=parse_file('data/Resume_example.pdf')
    )
    output_raw_resume = asyncio.run(graph.ainvoke(input=state_raw_resume))
    print("--- Parsed Resume (from raw) ---")
    print(output_raw_resume['resume'])
    yaml.safe_dump(output_raw_resume['resume'].model_dump(mode='json'), open('data/Resume_example.yaml', 'w'), indent=2)
    print("Resume saved to data/Resume_example.yaml")

    # Example 2: Load resume from YAML
    # print("\n--- Running example 2: Loading resume from YAML ---")
    # state_yaml_resume = InputState(
    #     job_url='https://www.google.com/about/careers/applications/jobs/results/110690555461018310-software-engineer-iii-infrastructure-core',
    #     resume_yaml = yaml.safe_load(open('data/Resume_example.yaml', 'r'))
    # )
    # output_yaml_resume = asyncio.run(graph.ainvoke(input=state_yaml_resume))
    # print("--- Parsed Resume (from YAML) ---")
    # print(output_yaml_resume['resume'])
    # print("--- Parsed Job Description ---")
    # print(output_yaml_resume['job'])
    # print("--- Adapted Resume ---")
    # print(output_yaml_resume['resume_out'])
    # print("--- Cover Letter ---")
    # print(output_yaml_resume['cover_letter'])
