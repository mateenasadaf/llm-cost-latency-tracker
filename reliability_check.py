
import sqlite3
import pandas as pd
from config import DB_NAME

def check_table(conn, table_name):
    print(f"\n{'=' * 60}")
    print(f"TABLE: {table_name}")
    print("=" * 60)

    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()

    if not exists:
        print("Table not found.")
        return

    df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)

    print(f"Total records: {len(df)}")

    if df.empty:
        print("No records available.")
        return

    # Request status distribution
    if "status" in df.columns:
        print("\nStatus distribution:")
        print(df["status"].value_counts(dropna=False).to_string())

    # Cost information
    if "cost" in df.columns:
        print("\nCost information:")
        print(f"Known costs: {df['cost'].notna().sum()}")
        print(f"Unknown costs: {df['cost'].isna().sum()}")
        print(f"Zero-cost records: {(df['cost'] == 0).sum()}")
        print(f"Negative costs: {(df['cost'] < 0).sum()}")

    # Retry information
    if "retry_count" in df.columns:
        print("\nRetry information:")
        print(f"Total retries: {df['retry_count'].fillna(0).sum()}")
        print(f"Requests with retries: {(df['retry_count'].fillna(0) > 0).sum()}")
        print(f"Negative retry counts: {(df['retry_count'] < 0).sum()}")

    # Timeout information
    if "timed_out" in df.columns:
        print("\nTimeout information:")
        print(df["timed_out"].value_counts(dropna=False).to_string())

    # Performance metrics
    metric_columns = [
        "latency_ms",
        "time_to_first_token_ms",
        "generation_time_ms",
        "throughput_tokens_per_second"
    ]

    print("\nPerformance metric checks:")

    for column in metric_columns:
        if column in df.columns:
            values = pd.to_numeric(df[column], errors="coerce")
            print(
                f"{column}: "
                f"missing={values.isna().sum()}, "
                f"negative={(values < 0).sum()}"
            )

    # Provider distribution
    if "provider" in df.columns:
        print("\nProvider distribution:")
        print(df["provider"].value_counts(dropna=False).to_string())


def main():
    print("LLM TRACKER - FINAL RELIABILITY CHECK")
    print(f"Database: {DB_NAME}")

    with sqlite3.connect(DB_NAME) as conn:
        check_table(conn, "llm_requests")
        check_table(conn, "benchmark_results")

    print("\n" + "=" * 60)
    print("DATABASE CHECK COMPLETED")
    print("No database records were modified.")
    print("=" * 60)


if __name__ == "__main__":
    main()
