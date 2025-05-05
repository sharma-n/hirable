import logging
from functools import lru_cache
from typing import Literal
from langchain.chat_models import init_chat_model
from langchain_core.rate_limiters import InMemoryRateLimiter

from src.config import llm_config

logger = logging.getLogger(__name__)

@lru_cache(maxsize=2)
def get_llm(size: Literal['small', 'medium']):
    '''
    Returns a pre-trained LLM based on the specified size.

    Args:
        size (Literal['small', 'medium']): The size of the LLM to return. Can be either 'small' or 'medium'.
    '''
    model = llm_config.small if size == 'small' else llm_config.large
    logger.info(f"Loading {model} from {llm_config.provider}.")
    llm = init_chat_model(
        model,
        model_provider=llm_config.provider,
        temperature=llm_config.temperature,
        rate_limiter=InMemoryRateLimiter(requests_per_second=llm_config.requests_per_sec)
    )
    
    return llm
