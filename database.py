import json
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_NAME = os.path.join(DATA_DIR, "llm_metrics.db")


def get_connection():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create/migrate application tables without deleting historical records."""

    conn = get_connection()

    try:
        # --------------------------------------------------
        # 1. Ordinary LLM Requests Table
        # --------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                latency_ms REAL DEFAULT 0,
                cost REAL DEFAULT 0,
                prompt TEXT,
                response TEXT,
                status TEXT NOT NULL,
                error_message TEXT
            )
        """)

        existing_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(llm_requests)"
            ).fetchall()
        }

        new_columns = {
            "provider": "TEXT DEFAULT 'ollama'",
            "time_to_first_token_ms": "REAL",
            "generation_time_ms": "REAL",
            "throughput_tokens_per_second": "REAL",
            "retry_count": "INTEGER DEFAULT 0",
            "timeout_seconds": "REAL",
            "timed_out": "INTEGER DEFAULT 0"
        }

        for column, definition in new_columns.items():
            if column not in existing_columns:
                conn.execute(
                    f"ALTER TABLE llm_requests ADD COLUMN "
                    f"{column} {definition}"
                )

        # --------------------------------------------------
        # 2. Benchmark Results Table
        # --------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS benchmark_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                benchmark_id TEXT NOT NULL,
                category TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt TEXT NOT NULL,
                reference_answer TEXT NOT NULL,
                response TEXT,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                latency_ms REAL,
                time_to_first_token_ms REAL,
                generation_time_ms REAL,
                throughput_tokens_per_second REAL,
                retry_count INTEGER DEFAULT 0,
                timeout_seconds REAL,
                timed_out INTEGER DEFAULT 0,
                cost REAL,
                status TEXT NOT NULL,
                error_message TEXT,
                correctness_score REAL,
                relevance_score REAL,
                completeness_score REAL,
                clarity_score REAL,
                quality_score REAL,
                evaluator_notes TEXT,
                executed_at TEXT NOT NULL,
                evaluated_at TEXT
            )
        """)

        benchmark_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(benchmark_results)"
            ).fetchall()
        }

        benchmark_new_columns = {
            "retry_count": "INTEGER DEFAULT 0",
            "timeout_seconds": "REAL",
            "timed_out": "INTEGER DEFAULT 0",
            "cost": "REAL"
        }

        for column, definition in benchmark_new_columns.items():
            if column not in benchmark_columns:
                conn.execute(
                    f"ALTER TABLE benchmark_results ADD COLUMN "
                    f"{column} {definition}"
                )

        # --------------------------------------------------
        # 3. Experiment Management Tables
        # --------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_name TEXT NOT NULL,
                description TEXT DEFAULT '',
                configuration TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'created',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS experiment_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                run_number INTEGER NOT NULL,
                run_type TEXT NOT NULL DEFAULT 'historical_import',
                status TEXT NOT NULL DEFAULT 'completed',
                started_at TEXT,
                completed_at TEXT,
                notes TEXT DEFAULT '',
                FOREIGN KEY (experiment_id)
                    REFERENCES experiments(id)
                    ON DELETE RESTRICT,
                UNIQUE (experiment_id, run_number)
            )
        """)

        # A nullable foreign-key column keeps all historical benchmark
        # records intact and unassigned until the user explicitly selects them.
        benchmark_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(benchmark_results)"
            ).fetchall()
        }

        if "experiment_run_id" not in benchmark_columns:
            conn.execute("""
                ALTER TABLE benchmark_results
                ADD COLUMN experiment_run_id INTEGER
                REFERENCES experiment_runs(id)
                ON DELETE RESTRICT
            """)

        # --------------------------------------------------
        # 4. Database Indexes
        # --------------------------------------------------

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_benchmark_results_lookup
            ON benchmark_results(provider, model, benchmark_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_benchmark_results_evaluated
            ON benchmark_results(quality_score, category)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_benchmark_results_experiment_run
            ON benchmark_results(experiment_run_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_experiment_runs_experiment
            ON experiment_runs(experiment_id, run_number)
        """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# --------------------------------------------------
# 5. Insert Benchmark Result
# --------------------------------------------------

def insert_benchmark_result(result):
    """Persist one benchmark response independently of Playground history."""

    conn = get_connection()

    try:
        cursor = conn.execute("""
            INSERT INTO benchmark_results (
                benchmark_id,
                category,
                provider,
                model,
                prompt,
                reference_answer,
                response,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                latency_ms,
                time_to_first_token_ms,
                generation_time_ms,
                throughput_tokens_per_second,
                retry_count,
                timeout_seconds,
                timed_out,
                cost,
                status,
                error_message,
                executed_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            result["benchmark_id"],
            result["category"],
            result["provider"],
            result["model"],
            result["prompt"],
            result["reference_answer"],
            result.get("response"),
            result.get("prompt_tokens", 0),
            result.get("completion_tokens", 0),
            result.get("total_tokens", 0),
            result.get("latency_ms"),
            result.get("time_to_first_token_ms"),
            result.get("generation_time_ms"),
            result.get("throughput_tokens_per_second"),
            result.get("retry_count", 0),
            result.get("timeout_seconds"),
            int(bool(result.get("timed_out", False))),
            result.get("cost"),
            result["status"],
            result.get("error_message"),
            result["executed_at"]
        ))

        conn.commit()
        return cursor.lastrowid

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# --------------------------------------------------
# 6. Save Manual Evaluation
# --------------------------------------------------

def save_benchmark_evaluation(
    result_id,
    correctness_score,
    relevance_score,
    completeness_score,
    clarity_score,
    evaluator_notes=""
):
    """Save the four manual rubric scores and their 100-point total."""

    quality_score = (
        float(correctness_score)
        + float(relevance_score)
        + float(completeness_score)
        + float(clarity_score)
    )

    conn = get_connection()

    try:
        cursor = conn.execute("""
            UPDATE benchmark_results
            SET correctness_score = ?,
                relevance_score = ?,
                completeness_score = ?,
                clarity_score = ?,
                quality_score = ?,
                evaluator_notes = ?,
                evaluated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            correctness_score,
            relevance_score,
            completeness_score,
            clarity_score,
            quality_score,
            evaluator_notes,
            result_id
        ))

        if cursor.rowcount == 0:
            raise ValueError(
                f"Benchmark result {result_id} was not found."
            )

        conn.commit()
        return quality_score

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# --------------------------------------------------
# 7. Experiment Creation and Retrieval
# --------------------------------------------------

def create_experiment(
    experiment_name,
    description="",
    configuration=None
):
    """
    Create an experiment definition.

    Configuration is stored as JSON. This function does not execute
    benchmarks or modify existing benchmark results.
    """

    name = str(experiment_name).strip() if experiment_name is not None else ""

    if not name:
        raise ValueError("Experiment name cannot be empty.")

    if configuration is None:
        configuration = {}

    if not isinstance(configuration, dict):
        raise ValueError("Experiment configuration must be a dictionary.")

    configuration_json = json.dumps(configuration)
    now = datetime.now().isoformat(timespec="seconds")

    conn = get_connection()

    try:
        cursor = conn.execute("""
            INSERT INTO experiments (
                experiment_name,
                description,
                configuration,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'created', ?, ?)
        """, (
            name,
            str(description or "").strip(),
            configuration_json,
            now,
            now
        ))

        conn.commit()
        return cursor.lastrowid

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_experiment(experiment_id):
    """Return one experiment, or None if it does not exist."""

    conn = get_connection()

    try:
        return conn.execute("""
            SELECT *
            FROM experiments
            WHERE id = ?
        """, (experiment_id,)).fetchone()

    finally:
        conn.close()


def list_experiments():
    """Return experiments with counts of associated runs and results."""

    conn = get_connection()

    try:
        return conn.execute("""
            SELECT
                e.*,
                COUNT(DISTINCT er.id) AS run_count,
                COUNT(br.id) AS benchmark_result_count
            FROM experiments AS e
            LEFT JOIN experiment_runs AS er
                ON er.experiment_id = e.id
            LEFT JOIN benchmark_results AS br
                ON br.experiment_run_id = er.id
            GROUP BY e.id
            ORDER BY e.created_at DESC, e.id DESC
        """).fetchall()

    finally:
        conn.close()


# --------------------------------------------------
# 8. Experiment Runs and Historical Result Association
# --------------------------------------------------

def create_experiment_run(
    experiment_id,
    run_number=None,
    run_type="historical_import",
    status="completed",
    started_at=None,
    completed_at=None,
    notes=""
):
    """Create a run record under an existing experiment."""

    now = datetime.now().isoformat(timespec="seconds")

    conn = get_connection()

    try:
        experiment = conn.execute(
            "SELECT id FROM experiments WHERE id = ?",
            (experiment_id,)
        ).fetchone()

        if experiment is None:
            raise ValueError(
                f"Experiment {experiment_id} was not found."
            )

        if run_number is None:
            row = conn.execute("""
                SELECT COALESCE(MAX(run_number), 0) + 1 AS next_number
                FROM experiment_runs
                WHERE experiment_id = ?
            """, (experiment_id,)).fetchone()
            run_number = row["next_number"]

        if int(run_number) < 1:
            raise ValueError("Run number must be at least 1.")

        cursor = conn.execute("""
            INSERT INTO experiment_runs (
                experiment_id,
                run_number,
                run_type,
                status,
                started_at,
                completed_at,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            experiment_id,
            int(run_number),
            str(run_type),
            str(status),
            started_at or now,
            completed_at or now,
            str(notes or "")
        ))

        conn.commit()
        return cursor.lastrowid

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def associate_existing_benchmark_results(experiment_run_id, result_ids):
    """
    Associate selected historical benchmark result IDs with an experiment run.

    Existing result data and manual evaluation fields are not changed.
    Results already assigned to another run are rejected.
    """

    if not result_ids:
        raise ValueError("Select at least one benchmark result.")

    normalized_ids = []
    for result_id in result_ids:
        value = int(result_id)
        if value < 1:
            raise ValueError("Benchmark result IDs must be positive integers.")
        normalized_ids.append(value)

    # Remove duplicate IDs while preserving their original order.
    normalized_ids = list(dict.fromkeys(normalized_ids))

    conn = get_connection()

    try:
        run = conn.execute(
            "SELECT id FROM experiment_runs WHERE id = ?",
            (experiment_run_id,)
        ).fetchone()

        if run is None:
            raise ValueError(
                f"Experiment run {experiment_run_id} was not found."
            )

        placeholders = ",".join("?" for _ in normalized_ids)

        existing_rows = conn.execute(
            f"""
            SELECT id, experiment_run_id
            FROM benchmark_results
            WHERE id IN ({placeholders})
            """,
            normalized_ids
        ).fetchall()

        existing_by_id = {row["id"]: row for row in existing_rows}
        missing_ids = [
            result_id for result_id in normalized_ids
            if result_id not in existing_by_id
        ]

        if missing_ids:
            raise ValueError(
                f"Benchmark result IDs not found: {missing_ids}"
            )

        already_assigned = [
            result_id
            for result_id in normalized_ids
            if existing_by_id[result_id]["experiment_run_id"] is not None
            and existing_by_id[result_id]["experiment_run_id"] != experiment_run_id
        ]

        if already_assigned:
            raise ValueError(
                "These benchmark results already belong to another "
                f"experiment run: {already_assigned}"
            )

        conn.execute(
            f"""
            UPDATE benchmark_results
            SET experiment_run_id = ?
            WHERE id IN ({placeholders})
              AND experiment_run_id IS NULL
            """,
            [experiment_run_id, *normalized_ids]
        )

        conn.commit()
        return len(normalized_ids)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_experiment_runs(experiment_id):
    """Return all runs belonging to an experiment."""

    conn = get_connection()

    try:
        return conn.execute("""
            SELECT
                er.*,
                COUNT(br.id) AS benchmark_result_count
            FROM experiment_runs AS er
            LEFT JOIN benchmark_results AS br
                ON br.experiment_run_id = er.id
            WHERE er.experiment_id = ?
            GROUP BY er.id
            ORDER BY er.run_number
        """, (experiment_id,)).fetchall()

    finally:
        conn.close()


def get_benchmark_results_for_experiment(experiment_id):
    """Return benchmark results associated with any run of an experiment."""

    conn = get_connection()

    try:
        return conn.execute("""
            SELECT br.*, er.run_number, er.run_type
            FROM benchmark_results AS br
            INNER JOIN experiment_runs AS er
                ON er.id = br.experiment_run_id
            WHERE er.experiment_id = ?
            ORDER BY er.run_number, br.id
        """, (experiment_id,)).fetchall()

    finally:
        conn.close()


def get_unassigned_benchmark_results():
    """Return benchmark records not yet associated with an experiment run."""

    conn = get_connection()

    try:
        return conn.execute("""
            SELECT *
            FROM benchmark_results
            WHERE experiment_run_id IS NULL
            ORDER BY id DESC
        """).fetchall()

    finally:
        conn.close()


# --------------------------------------------------
# 9. Main Execution
# --------------------------------------------------

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")

    conn = get_connection()

    try:
        for table_name in (
            "llm_requests",
            "benchmark_results",
            "experiments",
            "experiment_runs"
        ):
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            print(f"{table_name}: {count} records")

        print("\nBenchmark Results Columns:")
        columns = conn.execute(
            "PRAGMA table_info(benchmark_results)"
        ).fetchall()

        for column in columns:
            print("-", column["name"])

        print(
            "\nForeign key check:",
            conn.execute("PRAGMA foreign_key_check").fetchall()
        )

    finally:
        conn.close()
