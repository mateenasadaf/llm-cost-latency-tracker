
import sqlite3

DB_PATH = "data/llm_metrics.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("\n========== DATABASE INTEGRITY AUDIT ==========\n")

# 1. SQLite integrity
result = conn.execute("PRAGMA integrity_check").fetchone()[0]
print("1. SQLite integrity:", result)

# 2. Table record counts
for table in ["llm_requests", "benchmark_results"]:
    count = conn.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]
    print(f"\n2. {table}: {count} records")

# 3. Benchmark status distribution
print("\n3. Benchmark status distribution:")
rows = conn.execute("""
    SELECT status, COUNT(*) AS count
    FROM benchmark_results
    GROUP BY status
""").fetchall()

for row in rows:
    print(dict(row))

# 4. Missing performance metrics
print("\n4. Missing benchmark metrics:")

metric_columns = [
    "latency_ms",
    "time_to_first_token_ms",
    "generation_time_ms",
    "throughput_tokens_per_second"
]

for column in metric_columns:
    count = conn.execute(
        f"SELECT COUNT(*) FROM benchmark_results WHERE {column} IS NULL"
    ).fetchone()[0]
    print(f"{column}: {count}")

# 5. Quality score validation
print("\n5. Quality evaluation validation:")

invalid_scores = conn.execute("""
    SELECT COUNT(*) FROM benchmark_results
    WHERE
        (correctness_score IS NOT NULL AND
         (correctness_score < 0 OR correctness_score > 40))
        OR
        (relevance_score IS NOT NULL AND
         (relevance_score < 0 OR relevance_score > 25))
        OR
        (completeness_score IS NOT NULL AND
         (completeness_score < 0 OR completeness_score > 20))
        OR
        (clarity_score IS NOT NULL AND
         (clarity_score < 0 OR clarity_score > 15))
""").fetchone()[0]

print("Invalid rubric scores:", invalid_scores)

mismatched_totals = conn.execute("""
    SELECT COUNT(*) FROM benchmark_results
    WHERE quality_score IS NOT NULL
      AND quality_score != (
          correctness_score + relevance_score
          + completeness_score + clarity_score
      )
""").fetchone()[0]

print("Mismatched quality totals:", mismatched_totals)

# 6. Duplicate benchmark IDs
duplicates = conn.execute("""
    SELECT COUNT(*) FROM (
        SELECT id
        FROM benchmark_results
        GROUP BY id
        HAVING COUNT(*) > 1
    )
""").fetchone()[0]

print("Duplicate benchmark IDs:", duplicates)

print("\n========== AUDIT COMPLETED ==========\n")

conn.close()
