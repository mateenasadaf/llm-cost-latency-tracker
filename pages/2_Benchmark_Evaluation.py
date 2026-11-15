
import pandas as pd
import streamlit as st

from benchmark import execute_benchmark, load_benchmark_dataset
from database import get_connection, init_db, save_benchmark_evaluation


st.set_page_config(
    page_title="LLM Benchmark Evaluation",
    page_icon="🧪",
    layout="wide"
)

init_db()
dataset = load_benchmark_dataset()

st.title("🧪 LLM Quality Benchmark")
st.caption(
    "Run identical benchmark prompts across providers, then manually score "
    "each response using a fixed 100-point rubric."
)

questions = dataset["questions"]
rubric = dataset["scoring"]["criteria"]

with st.expander("Benchmark design and scoring rubric", expanded=False):
    st.write(dataset["description"])

    st.markdown("**Benchmark categories**")

    category_counts = pd.Series(
        [q["category"] for q in questions]
    ).value_counts().rename_axis("Category").reset_index(name="Questions")

    st.dataframe(
        category_counts,
        use_container_width=True,
        hide_index=True
    )

    st.markdown("**Manual scoring rubric**")

    st.dataframe(
        pd.DataFrame([
            {
                "Criterion": item["label"],
                "Maximum points": item["max_score"],
                "Weight": f'{item["weight_percent"]}%'
            }
            for item in rubric
        ]),
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Score each criterion from zero to its maximum. The four scores add "
        "directly to a total out of 100."
    )


run_tab, evaluate_tab = st.tabs(
    ["Run Benchmark", "Evaluate Responses"]
)


# ==========================================================
# TAB 1: RUN BENCHMARK
# ==========================================================

with run_tab:

    st.subheader("Execute the standardized benchmark")

    st.write(
        f"The dataset contains **{len(questions)} prompts**. Each selected "
        "provider receives each prompt as a separate, fresh request."
    )

    selected_providers = st.multiselect(
        "Providers to benchmark",
        options=["ollama", "openrouter"],
        default=["ollama", "openrouter"],
        format_func=lambda value: (
            "Ollama (llama3.2)" if value == "ollama"
            else "OpenRouter (openrouter/free; actual routed model recorded)"
        ),
        key="benchmark_providers"
    )

    if "benchmark_run_summary" not in st.session_state:
        st.session_state.benchmark_run_summary = None

    st.warning(
        "A full run sends 12 requests per selected provider (24 requests "
        "when both are selected). Runtime depends on model response times, "
        "rate limits and retries. Benchmark requests are stored separately "
        "and do not enter ordinary Playground request history."
    )

    if st.button(
        "Run selected benchmark(s)",
        type="primary",
        disabled=not selected_providers,
        use_container_width=True
    ):

        total_requests = len(questions) * len(selected_providers)

        progress = st.progress(0)

        status_line = st.empty()

        status_line.info(
            f"Benchmark started. Preparing {total_requests} requests..."
        )

        def update_progress(completed, total, record):

            # Show status BEFORE the model request starts.
            if record.get("status") == "running":

                status_line.info(
                    f"Running request {completed + 1}/{total}: "
                    f"{record.get('provider')} · "
                    f"{record.get('model')} · "
                    f"{record.get('benchmark_id')} — "
                    f"Waiting for model response..."
                )

            # Show progress AFTER the model request finishes.
            else:

                progress.progress(
                    min(completed / total, 1.0)
                )

                status_line.write(
                    f"Completed {completed}/{total}: "
                    f"{record.get('provider')} · "
                    f"{record.get('benchmark_id')} · "
                    f"{record.get('status')}"
                )

        try:

            ids = execute_benchmark(
                selected_providers,
                progress_callback=update_progress
            )

            st.session_state.benchmark_run_summary = {
                "count": len(ids),
                "ids": ids
            }

            progress.progress(1.0)

            status_line.success(
                f"All {len(ids)} benchmark requests have finished."
            )

            st.success(
                f"Benchmark execution finished. {len(ids)} result records "
                "were saved. Open the Evaluate Responses tab to score them."
            )

        except Exception as exc:

            st.error(
                f"Benchmark execution could not be completed: {exc}"
            )

    # Display recent benchmark executions.

    conn = get_connection()

    try:
        recent = pd.read_sql_query(
            """
            SELECT id, benchmark_id, category, provider, model, status,
                   latency_ms, executed_at, quality_score
            FROM benchmark_results
            ORDER BY id DESC
            LIMIT 30
            """,
            conn
        )

    finally:
        conn.close()

    st.markdown("#### Recent benchmark executions")

    if recent.empty:

        st.info(
            "No benchmark executions have been recorded yet."
        )

    else:

        st.dataframe(
            recent,
            use_container_width=True,
            hide_index=True
        )


# ==========================================================
# TAB 2: EVALUATE RESPONSES
# ==========================================================

with evaluate_tab:

    st.subheader("Manual response evaluation")

    conn = get_connection()

    try:
        results = pd.read_sql_query(
            """
            SELECT * FROM benchmark_results
            WHERE status = 'success' AND response IS NOT NULL
            ORDER BY id DESC
            """,
            conn
        )

    finally:
        conn.close()

    if results.empty:

        st.info(
            "Run the benchmark first. Successful responses will appear here."
        )

    else:

        def result_label(row):

            score = (
                f" · Score {row['quality_score']:.1f}/100"
                if pd.notna(row["quality_score"])
                else " · Not evaluated"
            )

            return (
                f"#{int(row['id'])} | {row['provider']} | {row['model']} | "
                f"{row['benchmark_id']} | {row['category']}{score}"
            )

        result_ids = results["id"].astype(int).tolist()

        selected_id = st.selectbox(
            "Select a response to evaluate",
            options=result_ids,
            format_func=lambda rid: result_label(
                results.loc[results["id"] == rid].iloc[0]
            ),
            key="benchmark_result_to_score"
        )

        selected = results.loc[
            results["id"] == selected_id
        ].iloc[0]

        left, right = st.columns(2)

        with left:

            st.markdown("**Benchmark prompt**")
            st.write(selected["prompt"])

            st.markdown("**Reference answer**")
            st.write(selected["reference_answer"])

        with right:

            st.markdown("**Model response**")
            st.write(selected["response"])

            st.caption(
                f"Provider: {selected['provider']} · "
                f"Model: {selected['model']} · "
                f"Latency: {selected['latency_ms'] / 1000:.2f} sec"
                if pd.notna(selected["latency_ms"])
                else (
                    f"Provider: {selected['provider']} · "
                    f"Model: {selected['model']}"
                )
            )

        question = next(
            q for q in questions
            if q["benchmark_id"] == selected["benchmark_id"]
        )

        with st.expander(
            "Question-specific evaluation guidance",
            expanded=True
        ):

            for criterion in question["evaluation_criteria"]:
                st.markdown(f"- {criterion}")

        st.markdown("#### Assign rubric scores")

        st.caption(
            "Compare the response with the reference answer and evaluation "
            "criteria. Award only points supported by the response."
        )

        score_cols = st.columns(2)

        score_values = {}

        for index, item in enumerate(rubric):

            key = item["key"]
            old_value = selected[key]

            default_value = (
                int(old_value) if pd.notna(old_value) else 0
            )

            with score_cols[index % 2]:

                score_values[key] = st.slider(
                    f"{item['label']} (/{item['max_score']})",
                    min_value=0,
                    max_value=item["max_score"],
                    value=min(
                        item["max_score"],
                        max(0, default_value)
                    ),
                    key=f"score_{selected_id}_{key}"
                )

        total_score = sum(score_values.values())

        st.metric(
            "Total Quality Score",
            f"{total_score}/100"
        )

        notes_value = selected["evaluator_notes"]

        notes_default = (
            "" if pd.isna(notes_value)
            else str(notes_value)
        )

        notes = st.text_area(
            "Evaluator notes (optional)",
            value=notes_default,
            key=f"notes_{selected_id}",
            placeholder="Briefly explain deductions or notable strengths."
        )

        if st.button(
            "Save evaluation",
            type="primary",
            key=f"save_eval_{selected_id}"
        ):

            try:

                saved_score = save_benchmark_evaluation(
                    selected_id,
                    score_values["correctness_score"],
                    score_values["relevance_score"],
                    score_values["completeness_score"],
                    score_values["clarity_score"],
                    notes
                )

                st.success(
                    f"Evaluation saved: {saved_score:.0f}/100. "
                    "The dashboard will use this score."
                )

                st.rerun()

            except Exception as exc:

                st.error(
                    f"Could not save evaluation: {exc}"
                )
