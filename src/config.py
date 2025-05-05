from dataclasses import dataclass
import logging
import yaml

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@dataclass
class ModelConfig:
    provider: str = 'openai'
    small: str = 'gpt-4o-mini'
    large: str = 'gpt-4o'
    temperature: float = 0.7
    requests_per_sec: int = 100

llm_config = ModelConfig(**(yaml.safe_load(open('config/params.yaml', 'r'))['llm']))
