from dataclasses import dataclass
import yaml

@dataclass
class ModelConfig:
    provider: str = 'openai'
    small: str = 'gpt-4.1-mini' # gpt-4.1 | gpt-4.1-mini
    large: str = 'gpt-4.1-mini'
    temperature: float = 0.7
    requests_per_sec: int = 100

llm_config = ModelConfig()
