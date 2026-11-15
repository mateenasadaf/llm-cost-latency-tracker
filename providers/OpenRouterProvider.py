import time

from openai import (
    OpenAI,
    APITimeoutError,
    APIConnectionError,
    APIStatusError,
    RateLimitError,
    InternalServerError
)

from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    REQUEST_TIMEOUT
)

from providers.base import BaseLLMProvider, LLMResponse


RETRYABLE_STATUS_CODES = {
    408, 409, 429, 500, 502, 503, 504
}


class OpenRouterProvider(BaseLLMProvider):

    def __init__(self):

        if not OPENROUTER_API_KEY:
            raise ValueError(
                "OPENROUTER_API_KEY is missing. Check your .env file."
            )

        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
            timeout=REQUEST_TIMEOUT,
            max_retries=0
        )

    def generate(self, prompt: str, model: str) -> LLMResponse:

        start_time = time.perf_counter()

        first_token_time = None
        last_token_time = None
        response_text = ""

        prompt_tokens = 0
        completion_tokens = 0
        actual_model = model

        try:
            stream = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                stream=True,
                stream_options={"include_usage": True}
            )

            for chunk in stream:

                actual_model = chunk.model or actual_model

                if chunk.choices:

                    content = (
                        chunk.choices[0].delta.content or ""
                    )

                    if content:

                        current_time = time.perf_counter()

                        if first_token_time is None:
                            first_token_time = current_time

                        last_token_time = current_time

                        response_text += content

                if chunk.usage:

                    prompt_tokens = (
                        chunk.usage.prompt_tokens or 0
                    )

                    completion_tokens = (
                        chunk.usage.completion_tokens or 0
                    )

            latency_ms = (
                time.perf_counter() - start_time
            ) * 1000

            ttft_ms = None

            if first_token_time is not None:
                ttft_ms = (
                    first_token_time - start_time
                ) * 1000

            generation_time_ms = None

            if (
                first_token_time is not None
                and last_token_time is not None
            ):
                measured_generation_time = (
                    last_token_time - first_token_time
                ) * 1000

                if measured_generation_time > 0:
                    generation_time_ms = measured_generation_time

            if not response_text.strip():

                return LLMResponse(
                    provider="openrouter",
                    model=actual_model,
                    response=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    latency_ms=latency_ms,
                    time_to_first_token_ms=ttft_ms,
                    generation_time_ms=generation_time_ms,
                    status="error",
                    error_message=(
                        "OpenRouter returned no text content."
                    )
                )

            return LLMResponse(
                provider="openrouter",
                model=actual_model,
                response=response_text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=latency_ms,
                time_to_first_token_ms=ttft_ms,
                generation_time_ms=generation_time_ms,
                status="success"
            )

        except APITimeoutError as e:

            return LLMResponse(
                provider="openrouter",
                model=actual_model,
                response=response_text,
                latency_ms=(
                    time.perf_counter() - start_time
                ) * 1000,
                status="error",
                error_message=f"Request timed out: {e}",
                timed_out=True,
                retryable=True
            )

        except (
            APIConnectionError,
            RateLimitError,
            InternalServerError
        ) as e:

            return LLMResponse(
                provider="openrouter",
                model=actual_model,
                response=response_text,
                latency_ms=(
                    time.perf_counter() - start_time
                ) * 1000,
                status="error",
                error_message=str(e),
                retryable=True
            )

        except APIStatusError as e:

            retryable = (
                e.status_code in RETRYABLE_STATUS_CODES
            )

            return LLMResponse(
                provider="openrouter",
                model=actual_model,
                response=response_text,
                latency_ms=(
                    time.perf_counter() - start_time
                ) * 1000,
                status="error",
                error_message=str(e),
                retryable=retryable
            )

        except Exception as e:

            return LLMResponse(
                provider="openrouter",
                model=actual_model,
                response=response_text,
                latency_ms=(
                    time.perf_counter() - start_time
                ) * 1000,
                status="error",
                error_message=str(e)
            )