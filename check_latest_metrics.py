
import sqlite3
from config import DB_NAME

conn = sqlite3.connect(DB_NAME)
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT
        id,
        provider,
        model,
        status,
        latency_ms,
        time_to_first_token_ms,
        generation_time_ms,
        throughput_tokens_per_second
    FROM llm_requests
    ORDER BY id DESC
    LIMIT 2
""").fetchall()

for row in rows:
    print(dict(row))

conn.close()
