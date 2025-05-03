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

if __name__ == "__main__":
    from langchain.chat_models import init_chat_model
    from langchain_core.rate_limiters import InMemoryRateLimiter
    logger.info(f"Loading {llm_config.small} from {llm_config.provider}.")
    llm = init_chat_model(
        llm_config.small,
        model_provider=llm_config.provider,
        temperature=llm_config.temperature,
        rate_limiter=InMemoryRateLimiter(requests_per_second=llm_config.requests_per_sec)
    )
    
    print(llm.invoke('Do you even work?'))