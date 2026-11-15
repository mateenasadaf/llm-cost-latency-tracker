from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    provider: str
    model: str
    response: str

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    latency_ms: float = 0.0
    time_to_first_token_ms: Optional[float] = None
    generation_time_ms: Optional[float] = None

    status: str = "success"
    error_message: Optional[str] = None

    timed_out: bool = False
    retryable: bool = False


class BaseLLMProvider(ABC):

    @abstractmethod
    def generate(self, prompt: str, model: str) -> LLMResponse:
        """
        Generate a response from the selected LLM.
        Every provider returns a standardized LLMResponse.
        """
        pass