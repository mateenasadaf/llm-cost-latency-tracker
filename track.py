
import time
from datetime import datetime

from config import (
    DEFAULT_MODEL,
    MODEL_RATES,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_BACKOFF_SECONDS
)

from database import get_connection, init_db

from providers.ollama_provider import OllamaProvider
from providers.OpenRouterProvider import OpenRouterProvider


# --------------------------------------------------
# 1. Provider Registry
# --------------------------------------------------

# Lazy construction prevents a missing OpenRouter key from disabling Ollama.
PROVIDERS = {
    "ollama": OllamaProvider,
    "openrouter": OpenRouterProvider
}


# --------------------------------------------------
# 2. Cost Calculation
# --------------------------------------------------

def calculate_cost(
    provider,
    model,
    prompt_tokens,
    completion_tokens
):
    provider = provider.lower().strip()
    model = model.strip()

    # Ollama runs locally.
    # API usage cost is zero, excluding electricity and hardware costs.
    if provider == "ollama":
        return 0.0

    # OpenRouter free models have no API usage charge.
    if provider == "openrouter" and model.endswith(":free"):
        return 0.0

    # Look up configured pricing for other models.
    provider_rates = MODEL_RATES.get(provider)

    if provider_rates is None:
        return None

    rates = provider_rates.get(model)

    if rates is None:
        return None

    input_cost = (
        prompt_tokens / 1_000_000
    ) * rates["input"]

    output_cost = (
        completion_tokens / 1_000_000
    ) * rates["output"]

    return input_cost + output_cost


# --------------------------------------------------
# 3. Run LLM Request with Retry Handling
# --------------------------------------------------

def run_request(
    prompt,
    model=DEFAULT_MODEL,
    provider_name="ollama",
    save_to_history=True
):

    provider_name = provider_name.lower().strip()

    provider_class = PROVIDERS.get(provider_name)

    if provider_class is None:
        raise ValueError(
            f"Unsupported provider: {provider_name}"
        )

    provider = provider_class()

    request_start = time.perf_counter()

    retry_count = 0
    had_timeout = False

    result = None

    for attempt in range(MAX_RETRIES + 1):

        result = provider.generate(prompt, model)

        # Validate provider identity.
        if result.provider.lower() != provider_name:
            raise ValueError(
                f"Provider mismatch: selected '{provider_name}', "
                f"but received '{result.provider}'."
            )

        had_timeout = had_timeout or result.timed_out

        if result.status.lower() == "success":
            break

        if not result.retryable:
            break

        if attempt == MAX_RETRIES:
            break

        retry_count += 1

        wait_seconds = (
            RETRY_BACKOFF_SECONDS * (2 ** attempt)
        )

        print(
            f"Attempt {attempt + 1} failed. "
            f"Retrying in {wait_seconds} seconds..."
        )

        time.sleep(wait_seconds)

    # Overall elapsed time includes retries and backoff.
    total_latency_ms = (
        time.perf_counter() - request_start
    ) * 1000

    # Calculate cost using the actual returned model.
    cost = calculate_cost(
        result.provider,
        result.model,
        result.prompt_tokens,
        result.completion_tokens
    )

    # Calculate generation throughput.
    throughput = None

    if (
        result.generation_time_ms is not None
        and result.generation_time_ms > 0
    ):
        throughput = (
            result.completion_tokens
            / (result.generation_time_ms / 1000)
        )

    request_id = None

    # Save request metrics to SQLite.
    if save_to_history:

        conn = get_connection()

        try:
            cursor = conn.execute("""
                INSERT INTO llm_requests (
                    timestamp,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    latency_ms,
                    cost,
                    prompt,
                    response,
                    status,
                    error_message,
                    provider,
                    time_to_first_token_ms,
                    generation_time_ms,
                    throughput_tokens_per_second,
                    retry_count,
                    timeout_seconds,
                    timed_out
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                result.model,
                result.prompt_tokens,
                result.completion_tokens,
                result.total_tokens,
                total_latency_ms,
                cost,
                prompt,
                result.response,
                result.status,
                result.error_message,
                result.provider,
                result.time_to_first_token_ms,
                result.generation_time_ms,
                throughput,
                retry_count,
                REQUEST_TIMEOUT,
                int(had_timeout)
            ))

            request_id = cursor.lastrowid

            conn.commit()

        finally:
            conn.close()

    # Return standardized request metrics.
    return {
        "provider": result.provider,
        "model": result.model,
        "response": result.response,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
        "latency_ms": total_latency_ms,
        "time_to_first_token_ms": result.time_to_first_token_ms,
        "generation_time_ms": result.generation_time_ms,
        "throughput_tokens_per_second": throughput,
        "cost": cost,
        "status": result.status,
        "error_message": result.error_message,
        "retry_count": retry_count,
        "timeout_seconds": REQUEST_TIMEOUT,
        "timed_out": had_timeout,
        "request_id": request_id
    }


# --------------------------------------------------
# 4. Main Execution
# --------------------------------------------------

if __name__ == "__main__":

    init_db()

    print("\nAvailable Providers:")
    print("1. Ollama (Local)")
    print("2. OpenRouter (Cloud)")

    choice = input("\nSelect provider (1 or 2): ").strip()

    if choice == "1":
        provider_name = "ollama"
        model = DEFAULT_MODEL

    elif choice == "2":
        provider_name = "openrouter"
        model = "openrouter/free"

    else:
        print("Invalid provider selection.")
        raise SystemExit(1)

    prompt = input("\nEnter your prompt: ")

    result = run_request(
        prompt,
        model=model,
        provider_name=provider_name
    )

    print("\n" + "=" * 45)
    print("LLM RESPONSE")
    print("=" * 45)

    print(result["response"])

    print("\n" + "=" * 45)
    print("REQUEST METRICS")
    print("=" * 45)

    print("Provider:", result["provider"])
    print("Model:", result["model"])
    print("Prompt Tokens:", result["prompt_tokens"])
    print("Completion Tokens:", result["completion_tokens"])
    print("Total Tokens:", result["total_tokens"])

    print(f"Total Latency: {result['latency_ms']:.2f} ms")

    if result["time_to_first_token_ms"] is not None:
        print(
            f"TTFT: {result['time_to_first_token_ms']:.2f} ms"
        )

    if result["generation_time_ms"] is not None:
        print(
            f"Generation Time: "
            f"{result['generation_time_ms']:.2f} ms"
        )

    if result["throughput_tokens_per_second"] is not None:
        print(
            f"Throughput: "
            f"{result['throughput_tokens_per_second']:.2f} tokens/sec"
        )

    if result["cost"] is not None:
        print(f"Estimated Cost: ${result['cost']:.8f}")
    else:
        print("Estimated Cost: Unavailable")

    print("Status:", result["status"])
    print("Retry Count:", result["retry_count"])
    print("Maximum Attempts:", MAX_RETRIES + 1)
    print("Timeout:", result["timeout_seconds"], "seconds")
    print("Timed Out During Request:", result["timed_out"])

    if result["error_message"]:
        print("Error:", result["error_message"])
