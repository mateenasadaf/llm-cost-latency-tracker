import json
import time
import requests

from config import OLLAMA_URL, REQUEST_TIMEOUT
from providers.base import BaseLLMProvider, LLMResponse


RETRYABLE_HTTP_STATUS_CODES = {
    408, 429, 500, 502, 503, 504
}


class OllamaProvider(BaseLLMProvider):

    def generate(self, prompt: str, model: str) -> LLMResponse:

        start_time = time.perf_counter()

        first_token_time = None
        response_text = ""

        prompt_tokens = 0
        completion_tokens = 0
        generation_time_ms = None

        try:
            with requests.post(
                OLLAMA_URL,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": True
                },
                stream=True,
                timeout=REQUEST_TIMEOUT
            ) as response:

                response.raise_for_status()

                for line in response.iter_lines():

                    if not line:
                        continue

                    data = json.loads(line.decode("utf-8"))

                    chunk = data.get("response", "")

                    if chunk:
                        if first_token_time is None:
                            first_token_time = time.perf_counter()

                        response_text += chunk

                    if data.get("done"):

                        prompt_tokens = data.get(
                            "prompt_eval_count", 0
                        )

                        completion_tokens = data.get(
                            "eval_count", 0
                        )

                        generation_time_ms = (
                            data.get("eval_duration", 0)
                            / 1_000_000
                        )

            latency_ms = (
                time.perf_counter() - start_time
            ) * 1000

            ttft_ms = None

            if first_token_time is not None:
                ttft_ms = (
                    first_token_time - start_time
                ) * 1000

            if not response_text.strip():
                return LLMResponse(
                    provider="ollama",
                    model=model,
                    response=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    latency_ms=latency_ms,
                    time_to_first_token_ms=ttft_ms,
                    generation_time_ms=generation_time_ms,
                    status="error",
                    error_message="Ollama returned no text content."
                )

            return LLMResponse(
                provider="ollama",
                model=model,
                response=response_text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=latency_ms,
                time_to_first_token_ms=ttft_ms,
                generation_time_ms=generation_time_ms,
                status="success"
            )

        except requests.exceptions.Timeout as e:

            return LLMResponse(
                provider="ollama",
                model=model,
                response=response_text,
                latency_ms=(
                    time.perf_counter() - start_time
                ) * 1000,
                status="error",
                error_message=f"Request timed out: {e}",
                timed_out=True,
                retryable=True
            )

        except requests.exceptions.ConnectionError as e:

            return LLMResponse(
                provider="ollama",
                model=model,
                response=response_text,
                latency_ms=(
                    time.perf_counter() - start_time
                ) * 1000,
                status="error",
                error_message=f"Connection error: {e}",
                retryable=True
            )

        except requests.exceptions.HTTPError as e:

            status_code = (
                e.response.status_code
                if e.response is not None
                else None
            )

            retryable = (
                status_code in RETRYABLE_HTTP_STATUS_CODES
            )

            return LLMResponse(
                provider="ollama",
                model=model,
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
                provider="ollama",
                model=model,
                response=response_text,
                latency_ms=(
                    time.perf_counter() - start_time
                ) * 1000,
                status="error",
                error_message=str(e)
            )