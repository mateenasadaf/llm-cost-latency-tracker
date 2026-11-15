
"""Benchmark execution helpers for LLM performance and cost comparison."""

import json
import os
from datetime import datetime

from database import init_db, insert_benchmark_result
from track import run_request


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(
    BASE_DIR,
    "data",
    "benchmark_dataset.json"
)


# --------------------------------------------------
# 1. Load Benchmark Dataset
# --------------------------------------------------

def load_benchmark_dataset():

    with open(DATASET_PATH, "r", encoding="utf-8") as dataset_file:
        dataset = json.load(dataset_file)

    questions = dataset.get("questions", [])

    if not questions:
        raise ValueError(
            "The benchmark dataset contains no questions."
        )

    return dataset


# --------------------------------------------------
# 2. Execute Benchmark
# --------------------------------------------------

def execute_benchmark(providers, progress_callback=None):
    """
    Run every benchmark prompt independently for each selected provider.

    Benchmark requests bypass ordinary llm_requests history
    and are persisted in benchmark_results.
    """

    dataset = load_benchmark_dataset()
    questions = dataset["questions"]

    if not providers:
        raise ValueError("Select at least one provider.")

    total = len(questions) * len(providers)

    completed = 0
    saved_ids = []

    init_db()

    # --------------------------------------------------
    # Provider Execution
    # --------------------------------------------------

    for provider_name in providers:

        provider_name = provider_name.lower().strip()

        if provider_name not in {"ollama", "openrouter"}:
            raise ValueError(
                f"Unsupported provider: {provider_name}"
            )

        model = (
            "llama3.2"
            if provider_name == "ollama"
            else "openrouter/free"
        )

        # --------------------------------------------------
        # Execute Each Benchmark Question
        # --------------------------------------------------

        for question in questions:

            executed_at = datetime.now().isoformat()

            # Notify UI before request starts.

            if progress_callback:

                progress_callback(
                    completed,
                    total,
                    {
                        "benchmark_id": question["benchmark_id"],
                        "provider": provider_name,
                        "model": model,
                        "status": "running"
                    }
                )

            try:

                result = run_request(
                    prompt=question["prompt"],
                    model=model,
                    provider_name=provider_name,
                    save_to_history=False
                )

                # --------------------------------------------------
                # Prepare Successful/Completed Request Record
                # --------------------------------------------------

                record = {
                    "benchmark_id": question["benchmark_id"],
                    "category": question["category"],

                    "provider": result["provider"],
                    "model": result["model"],

                    "prompt": question["prompt"],
                    "reference_answer": question["reference_answer"],

                    "response": result["response"],

                    # Token Metrics
                    "prompt_tokens": result["prompt_tokens"],
                    "completion_tokens": result["completion_tokens"],
                    "total_tokens": result["total_tokens"],

                    # Performance Metrics
                    "latency_ms": result["latency_ms"],
                    "time_to_first_token_ms": (
                        result["time_to_first_token_ms"]
                    ),
                    "generation_time_ms": (
                        result["generation_time_ms"]
                    ),
                    "throughput_tokens_per_second": (
                        result["throughput_tokens_per_second"]
                    ),

                    # Cost
                    "cost": result.get("cost"),

                    # Reliability Metrics
                    "retry_count": result.get("retry_count", 0),
                    "timeout_seconds": result.get("timeout_seconds"),
                    "timed_out": result.get("timed_out", False),

                    # Request Status
                    "status": result["status"],
                    "error_message": result["error_message"],

                    "executed_at": executed_at
                }

            except Exception as exc:

                # --------------------------------------------------
                # Preserve Failed Requests
                # --------------------------------------------------

                record = {
                    "benchmark_id": question["benchmark_id"],
                    "category": question["category"],

                    "provider": provider_name,
                    "model": model,

                    "prompt": question["prompt"],
                    "reference_answer": question["reference_answer"],

                    "response": "",

                    "status": "error",
                    "error_message": str(exc),

                    "executed_at": executed_at
                }

            # --------------------------------------------------
            # Save Result Immediately
            # --------------------------------------------------

            saved_id = insert_benchmark_result(record)

            saved_ids.append(saved_id)

            completed += 1

            # --------------------------------------------------
            # Notify UI After Saving
            # --------------------------------------------------

            if progress_callback:

                progress_callback(
                    completed,
                    total,
                    record
                )

    return saved_ids
