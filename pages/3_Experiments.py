import sys
from pathlib import Path

# Add project root to Python import path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from database import (
    create_experiment,
    create_experiment_run,
    associate_existing_benchmark_results,
    list_experiments,
    get_unassigned_benchmark_results,
    get_experiment_runs,
    get_benchmark_results_for_experiment,
)

st.set_page_config(
    page_title="Experiment Management",
    page_icon="🧪",
    layout="wide"
)

st.title("🧪 Experiment Management")
st.caption(
    "Create experiments and organize existing benchmark results "
    "without sending new requests to any LLM provider."
)

# --------------------------------------------------
# 1. CREATE EXPERIMENT
# --------------------------------------------------

st.subheader("Create a new experiment")

with st.form("create_experiment_form", clear_on_submit=True):
    experiment_name = st.text_input(
        "Experiment name",
        placeholder="e.g. Local vs Cloud Model Comparison"
    )

    experiment_description = st.text_area(
        "Description",
        placeholder="Describe the objective of this experiment."
    )

    submitted = st.form_submit_button(
        "Create experiment",
        type="primary",
        use_container_width=True
    )

    if submitted:
        if not experiment_name.strip():
            st.error("Please enter an experiment name.")
        else:
            try:
                experiment_id = create_experiment(
                    experiment_name=experiment_name,
                    description=experiment_description,
                    configuration={
                        "source": "existing_benchmark_results",
                        "created_from": "experiment_management_page"
                    }
                )
                st.success(
                    f"Experiment created successfully. "
                    f"Experiment ID: {experiment_id}"
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Could not create experiment: {exc}")

st.divider()

# --------------------------------------------------
# 2. EXISTING EXPERIMENTS
# --------------------------------------------------

st.subheader("Existing experiments")

try:
    experiments = list_experiments()
except Exception as exc:
    st.error(f"Could not load experiments: {exc}")
    st.stop()

if not experiments:
    st.info(
        "No experiments have been created yet. "
        "Create your first experiment above."
    )
    st.stop()

experiment_rows = [dict(row) for row in experiments]
experiment_df = pd.DataFrame(experiment_rows)

display_columns = [
    "id",
    "experiment_name",
    "description",
    "status",
    "run_count",
    "benchmark_result_count",
    "created_at"
]

st.dataframe(
    experiment_df[display_columns],
    use_container_width=True,
    hide_index=True
)

st.divider()

# --------------------------------------------------
# 3. SELECT EXPERIMENT
# --------------------------------------------------

st.subheader("Manage an experiment")

experiment_lookup = {
    row["id"]: row
    for row in experiments
}

selected_experiment_id = st.selectbox(
    "Select an experiment",
    options=list(experiment_lookup.keys()),
    format_func=lambda experiment_id: (
        f"#{experiment_id} — "
        f"{experiment_lookup[experiment_id]['experiment_name']}"
    ),
    key="selected_experiment_id"
)

selected_experiment = experiment_lookup[selected_experiment_id]

st.markdown(f"**Description:** {selected_experiment['description'] or 'No description provided.'}")

# --------------------------------------------------
# 4. ASSOCIATE EXISTING BENCHMARK RESULTS
# --------------------------------------------------

st.subheader("Add existing benchmark results")

st.caption(
    "Select historical benchmark records to associate with this experiment. "
    "This operation does not rerun models or modify their responses, "
    "performance metrics, costs or manual evaluation scores."
)

try:
    unassigned_results = get_unassigned_benchmark_results()
except Exception as exc:
    st.error(f"Could not load unassigned benchmark results: {exc}")
    st.stop()

if not unassigned_results:
    st.info(
        "There are no unassigned benchmark results available. "
        "All currently available records may already belong to experiments."
    )
else:
    result_rows = [dict(row) for row in unassigned_results]
    results_df = pd.DataFrame(result_rows)

    result_display_columns = [
        "id",
        "benchmark_id",
        "category",
        "provider",
        "model",
        "status",
        "latency_ms",
        "cost",
        "quality_score",
        "executed_at"
    ]

    st.dataframe(
        results_df[result_display_columns],
        use_container_width=True,
        hide_index=True
    )

    result_lookup = {
        row["id"]: row
        for row in unassigned_results
    }

    select_all_results = st.checkbox(
        f"Select all {len(result_lookup)} unassigned benchmark results"
    )

    if select_all_results:
        selected_result_ids = list(result_lookup.keys())
        st.info(f"{len(selected_result_ids)} benchmark results selected.")
    else:
        selected_result_ids = st.multiselect(
            "Select benchmark result IDs",
            options=list(result_lookup.keys()),
            format_func=lambda result_id: (
                f"#{result_id} | "
                f"{result_lookup[result_id]['provider']} | "
                f"{result_lookup[result_id]['model']} | "
                f"{result_lookup[result_id]['benchmark_id']} | "
                f"{result_lookup[result_id]['category']}"
            ),
            help="Only unassigned historical records are shown."
        )

    run_notes = st.text_input(
        "Import notes (optional)",
        placeholder="e.g. Historical benchmark results imported for comparison"
    )

    if st.button(
        "Add selected results to experiment",
        type="primary",
        disabled=not selected_result_ids,
        use_container_width=True
    ):
        try:
            run_id = create_experiment_run(
                experiment_id=selected_experiment_id,
                run_type="historical_import",
                status="completed",
                notes=run_notes
            )

            associated_count = associate_existing_benchmark_results(
                experiment_run_id=run_id,
                result_ids=selected_result_ids
            )

            st.success(
                f"Successfully associated {associated_count} existing "
                f"benchmark result(s) with experiment "
                f"#{selected_experiment_id}. Run ID: {run_id}."
            )
            st.rerun()

        except Exception as exc:
            st.error(
                "Could not associate the selected results. "
                f"Please inspect the experiment run before retrying: {exc}"
            )

st.divider()

# --------------------------------------------------
# 5. EXPERIMENT RUN HISTORY
# --------------------------------------------------

st.subheader("Experiment run history")

try:
    runs = get_experiment_runs(selected_experiment_id)
except Exception as exc:
    st.error(f"Could not load experiment runs: {exc}")
    st.stop()

if not runs:
    st.info("No runs have been associated with this experiment yet.")
else:
    runs_df = pd.DataFrame([dict(row) for row in runs])

    st.dataframe(
        runs_df[
            [
                "id",
                "run_number",
                "run_type",
                "status",
                "benchmark_result_count",
                "started_at",
                "completed_at",
                "notes"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

# --------------------------------------------------
# 6. ASSOCIATED BENCHMARK RESULTS
# --------------------------------------------------

st.subheader("Benchmark results in this experiment")

try:
    associated_results = get_benchmark_results_for_experiment(
        selected_experiment_id
    )
except Exception as exc:
    st.error(f"Could not load associated benchmark results: {exc}")
    st.stop()

if not associated_results:
    st.info(
        "No benchmark results are associated with this experiment yet."
    )
else:
    associated_df = pd.DataFrame(
        [dict(row) for row in associated_results]
    )

    associated_display_columns = [
        "id",
        "run_number",
        "benchmark_id",
        "category",
        "provider",
        "model",
        "status",
        "latency_ms",
        "time_to_first_token_ms",
        "generation_time_ms",
        "throughput_tokens_per_second",
        "cost",
        "quality_score",
        "executed_at"
    ]

    st.dataframe(
        associated_df[associated_display_columns],
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Performance metrics and manual quality scores are displayed "
        "separately and retain their original stored values."
    )
