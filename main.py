import asyncio
import yaml
from src.graph import get_graph
from src.states import InputState
from src.utils import setup_logging
from src.utils.parse import parse_file
from src.utils.export import export_resume_to_pdf

setup_logging()

if __name__ == "__main__":
    URL = 'https://www.metacareers.com/jobs/594161082740454/'
    USE_YAML = True
    RESUME_FILE = 'data/CV.tex'
    INPUT_RESUME_YAML = 'data/parsed_resume.yaml'
    RENDERCV_CONFIG_YAML = 'src/config/rendercv_config.yaml'

    graph = get_graph()
    input_params = {
        'job_url': URL,
    }
    if USE_YAML:
        input_params['resume_yaml'] = yaml.safe_load(open(INPUT_RESUME_YAML, 'r'))
    else:
        input_params['resume_raw'] = parse_file(RESUME_FILE)

    input_state = InputState(**input_params)
    output_resume = asyncio.run(graph.ainvoke(input=input_state))

    if not USE_YAML:
        yaml.safe_dump(output_resume['resume'].model_dump(mode='json'), open(INPUT_RESUME_YAML, 'w'), indent=2)

    export_resume_to_pdf(output_resume['resume_out'], keywords=output_resume['job'].keywords, rendercv_config=yaml.safe_load(open(RENDERCV_CONFIG_YAML, 'r')))
