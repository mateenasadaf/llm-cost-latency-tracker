
import sqlite3
import pandas as pd
from config import DB_NAME

with sqlite3.connect(DB_NAME) as conn:

    print("\n--- LLM REQUESTS: MISSING PERFORMANCE METRICS ---")

    query = """
    SELECT id, provider, model, status,
           latency_ms, time_to_first_token_ms,
           generation_time_ms, throughput_tokens_per_second,
           retry_count, timed_out
    FROM llm_requests
    WHERE time_to_first_token_ms IS NULL
       OR generation_time_ms IS NULL
       OR throughput_tokens_per_second IS NULL
    """

    df = pd.read_sql_query(query, conn)
    print(df.to_string(index=False))

    print("\n--- LLM REQUESTS: TIMEOUT RECORDS ---")

    query = """
    SELECT id, provider, model, status,
           latency_ms, retry_count, timeout_seconds, timed_out
    FROM llm_requests
    WHERE timed_out = 1
    """

    df = pd.read_sql_query(query, conn)
    print(df.to_string(index=False))

    print("\n--- BENCHMARK RESULTS: TIMEOUT RECORDS ---")

    query = """
    SELECT *
    FROM benchmark_results
    WHERE timed_out = 1
    """

    df = pd.read_sql_query(query, conn)
    print(df.to_string(index=False))

    print("\n--- LLM REQUESTS: RETRIED RECORDS ---")

    query = """
    SELECT id, provider, model, status,
           retry_count, timed_out, latency_ms
    FROM llm_requests
    WHERE retry_count > 0
    """

    df = pd.read_sql_query(query, conn)
    print(df.to_string(index=False))

    print("\n--- BENCHMARK RESULTS: RETRIED RECORDS ---")

    query = """
    SELECT *
    FROM benchmark_results
    WHERE retry_count > 0
    """

    df = pd.read_sql_query(query, conn)
    print(df.to_string(index=False))

print("\nDetailed reliability inspection completed.")
