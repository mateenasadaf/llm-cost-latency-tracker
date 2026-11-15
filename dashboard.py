
import streamlit as st
import pandas as pd
import plotly.express as px

from database import get_connection, init_db



# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="LLM Cost & Latency Tracker",
    page_icon="📊",
    layout="wide"
)

st.title("LLM Cost & Latency Tracker")
st.caption("Monitor token usage, latency, cost and request performance.")


# --------------------------------------------------
# LOAD DATABASE RECORDS
# --------------------------------------------------

def load_data():
    conn = get_connection()

    try:
        df = pd.read_sql_query(
            "SELECT * FROM llm_requests ORDER BY timestamp DESC",
            conn
        )
    finally:
        conn.close()

    return df


init_db()
df = load_data()

if df.empty:
    st.info("No ordinary LLM requests recorded yet.")
    st.stop()

# Preserve the complete dataset before applying filters.
# Model comparison will use all recorded requests.
all_requests_df = df.copy()

df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce"
)


# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------

st.sidebar.header("Filters")

providers = ["All"] + sorted(
    df["provider"].dropna().unique().tolist()
)

selected_provider = st.sidebar.selectbox(
    "Select Provider",
    providers
)

if selected_provider != "All":
    df = df[df["provider"] == selected_provider]


models = ["All"] + sorted(
    df["model"].dropna().unique().tolist()
)

selected_model = st.sidebar.selectbox(
    "Select Model",
    models
)

if selected_model != "All":
    df = df[df["model"] == selected_model]


if df.empty:
    st.warning("No ordinary request records found for this filter.")
    st.stop()


# --------------------------------------------------
# KPI CALCULATIONS
# --------------------------------------------------

total_requests = len(df)

total_tokens = df["total_tokens"].sum()

avg_latency = df["latency_ms"].mean()

known_costs = df["cost"].dropna()

total_cost = (
    known_costs.sum()
    if not known_costs.empty
    else None
)

cost_coverage = (
    len(known_costs) / total_requests
) * 100

successful_requests = (
    df["status"] == "success"
).sum()

success_rate = (
    successful_requests / total_requests
) * 100


# --------------------------------------------------
# MAIN KPI CARDS
# --------------------------------------------------

st.subheader("Overview")

col1, col2, col3 = st.columns(3)

col1.metric(
    "Total Requests",
    f"{total_requests:,}"
)

col2.metric(
    "Total Tokens",
    f"{total_tokens:,}"
)

col3.metric(
    "Average Latency",
    f"{avg_latency / 1000:.2f} sec"
)


col4, col5, col6 = st.columns(3)

col4.metric(
    "Known Total Cost",
    f"${total_cost:.8f}" if total_cost is not None
    else "Unavailable"
)

col5.metric(
    "Success Rate",
    f"{success_rate:.2f}%"
)

col6.metric(
    "Successful Requests",
    f"{successful_requests:,}"
)


st.divider()


# --------------------------------------------------
# ADVANCED PERFORMANCE ANALYTICS
# --------------------------------------------------

st.subheader("Advanced Performance Analytics")

filtered_successful_df = df[
    df["status"] == "success"
].copy()


if not filtered_successful_df.empty:

    # Latency percentiles
    latency_values = filtered_successful_df[
        "latency_ms"
    ].dropna()

    if not latency_values.empty:

        p50 = latency_values.quantile(0.50)
        p95 = latency_values.quantile(0.95)
        p99 = latency_values.quantile(0.99)

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "P50 Latency",
            f"{p50 / 1000:.2f} sec"
        )

        col2.metric(
            "P95 Latency",
            f"{p95 / 1000:.2f} sec"
        )

        col3.metric(
            "P99 Latency",
            f"{p99 / 1000:.2f} sec"
        )

    else:
        st.info("Latency data is unavailable.")


    # Generation performance
    st.markdown("#### Generation Performance")

    ttft_values = filtered_successful_df[
        "time_to_first_token_ms"
    ].dropna()

    throughput_values = filtered_successful_df[
        "throughput_tokens_per_second"
    ].dropna()

    col1, col2 = st.columns(2)

    if not ttft_values.empty:

        col1.metric(
            "Average TTFT",
            f"{ttft_values.mean() / 1000:.2f} sec"
        )

    else:
        col1.metric(
            "Average TTFT",
            "Unavailable"
        )


    if not throughput_values.empty:

        col2.metric(
            "Average Throughput",
            f"{throughput_values.mean():.2f} tokens/sec"
        )

    else:
        col2.metric(
            "Average Throughput",
            "Unavailable"
        )


    st.caption(
        "OpenRouter generation time and throughput are estimates "
        "based on latency minus TTFT. Ollama uses provider-reported "
        "generation timing."
    )

else:

    st.info(
        "No successful requests available for performance analysis."
    )


st.divider()


# --------------------------------------------------
# MODEL-WISE PERFORMANCE COMPARISON
# --------------------------------------------------

st.header("Model-wise Performance Comparison")

comparison_df = all_requests_df[
    all_requests_df["status"] == "success"
].copy()

if not comparison_df.empty:

    model_comparison = comparison_df.groupby(
        ["provider", "model"]
    ).agg(
        requests=("id", "count"),
        avg_latency=("latency_ms", "mean"),
        p50_latency=("latency_ms", "median"),
        p95_latency=(
            "latency_ms",
            lambda x: x.quantile(0.95)
        ),
        p99_latency=(
            "latency_ms",
            lambda x: x.quantile(0.99)
        ),
        avg_ttft=("time_to_first_token_ms", "mean"),
        avg_throughput=(
            "throughput_tokens_per_second",
            "mean"
        ),
        avg_cost=("cost", "mean"),
        avg_tokens=("total_tokens", "mean")
    ).reset_index()

    model_comparison = model_comparison.rename(
        columns={
            "provider": "Provider",
            "model": "Model",
            "requests": "Successful Requests",
            "avg_latency": "Avg Latency (ms)",
            "p50_latency": "P50 Latency (ms)",
            "p95_latency": "P95 Latency (ms)",
            "p99_latency": "P99 Latency (ms)",
            "avg_ttft": "Avg TTFT (ms)",
            "avg_throughput": "Avg Throughput (tokens/sec)",
            "avg_cost": "Avg Cost per Request ($)",
            "avg_tokens": "Avg Tokens per Request"
        }
    )

    st.caption(
        "This comparison uses all successful requests in the database, "
        "independent of the selected provider and model filters above."
    )

    # Comparison table
    st.subheader("Performance Metrics by Model")

    st.dataframe(
        model_comparison.round(4),
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Average cost excludes requests with unknown pricing. "
        "OpenRouter throughput is estimated in the current implementation."
    )

    # Average latency comparison
    st.subheader("Average Latency by Model")

    latency_chart = px.bar(
        model_comparison,
        x="Model",
        y="Avg Latency (ms)",
        color="Provider",
        barmode="group",
        hover_data=["Successful Requests"],
        title="Average Response Latency"
    )

    st.plotly_chart(
        latency_chart,
        use_container_width=True
    )

    # Throughput comparison
    st.subheader("Average Throughput by Model")

    throughput_chart = px.bar(
        model_comparison,
        x="Model",
        y="Avg Throughput (tokens/sec)",
        color="Provider",
        barmode="group",
        hover_data=["Successful Requests"],
        title="Average Generation Throughput"
    )

    st.plotly_chart(
        throughput_chart,
        use_container_width=True
    )

    # Average cost comparison
    st.subheader("Average Cost per Request")

    cost_chart = px.bar(
        model_comparison,
        x="Model",
        y="Avg Cost per Request ($)",
        color="Provider",
        barmode="group",
        hover_data=["Successful Requests"],
        title="Average Cost Comparison"
    )

    st.plotly_chart(
        cost_chart,
        use_container_width=True
    )

else:

    st.info(
        "No successful requests available for model comparison."
    )


st.divider()

# --------------------------------------------------
# PROVIDER-WISE PERFORMANCE COMPARISON
# --------------------------------------------------

st.header("Provider-wise Performance Comparison")

provider_all_df = all_requests_df.copy()

# Overall provider statistics, including failed requests
provider_overview = provider_all_df.groupby(
    "provider"
).agg(
    total_requests=("id", "count"),
    successful_requests=(
        "status",
        lambda x: (x == "success").sum()
    ),
    avg_cost=("cost", "mean"),
    known_cost_requests=("cost", "count")
).reset_index()

provider_overview["success_rate"] = (
    provider_overview["successful_requests"]
    / provider_overview["total_requests"]
) * 100


# Performance metrics using successful requests only
provider_success_df = provider_all_df[
    provider_all_df["status"] == "success"
].copy()

if not provider_success_df.empty:

    provider_performance = provider_success_df.groupby(
        "provider"
    ).agg(
        avg_latency=("latency_ms", "mean"),
        p50_latency=(
            "latency_ms",
            "median"
        ),
        p95_latency=(
            "latency_ms",
            lambda x: x.quantile(0.95)
        ),
        p99_latency=(
            "latency_ms",
            lambda x: x.quantile(0.99)
        ),
        avg_ttft=("time_to_first_token_ms", "mean"),
        avg_throughput=(
            "throughput_tokens_per_second",
            "mean"
        )
    ).reset_index()

    provider_comparison = provider_overview.merge(
        provider_performance,
        on="provider",
        how="left"
    )

else:
    provider_comparison = provider_overview.copy()

    for column in [
        "avg_latency",
        "p50_latency",
        "p95_latency",
        "p99_latency",
        "avg_ttft",
        "avg_throughput"
    ]:
        provider_comparison[column] = None


provider_comparison = provider_comparison.rename(
    columns={
        "provider": "Provider",
        "total_requests": "Total Requests",
        "successful_requests": "Successful Requests",
        "success_rate": "Success Rate (%)",
        "avg_latency": "Avg Latency (ms)",
        "p50_latency": "P50 Latency (ms)",
        "p95_latency": "P95 Latency (ms)",
        "p99_latency": "P99 Latency (ms)",
        "avg_ttft": "Avg TTFT (ms)",
        "avg_throughput": "Avg Throughput (tokens/sec)",
        "avg_cost": "Avg Cost per Request ($)",
        "known_cost_requests": "Requests with Known Cost"
    }
)

st.caption(
    "Provider comparison uses all database records, independent "
    "of the sidebar filters. Reliability metrics include failed "
    "requests; performance metrics use successful requests only."
)

st.subheader("Provider Performance Metrics")

st.dataframe(
    provider_comparison.round(4),
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# PROVIDER COMPARISON CHARTS
# --------------------------------------------------

st.subheader("Average Latency by Provider")

latency_provider_chart = px.bar(
    provider_comparison,
    x="Provider",
    y="Avg Latency (ms)",
    color="Provider",
    title="Average Response Latency"
)

st.plotly_chart(
    latency_provider_chart,
    use_container_width=True
)


st.subheader("Average Throughput by Provider")

throughput_provider_chart = px.bar(
    provider_comparison,
    x="Provider",
    y="Avg Throughput (tokens/sec)",
    color="Provider",
    title="Average Generation Throughput"
)

st.plotly_chart(
    throughput_provider_chart,
    use_container_width=True
)


st.subheader("Success Rate by Provider")

success_provider_chart = px.bar(
    provider_comparison,
    x="Provider",
    y="Success Rate (%)",
    color="Provider",
    title="Provider Reliability"
)

success_provider_chart.update_yaxes(
    range=[0, 100]
)

st.plotly_chart(
    success_provider_chart,
    use_container_width=True
)


st.subheader("Average Cost per Request by Provider")

cost_provider_chart = px.bar(
    provider_comparison,
    x="Provider",
    y="Avg Cost per Request ($)",
    color="Provider",
    title="Average Request Cost"
)

st.plotly_chart(
    cost_provider_chart,
    use_container_width=True
)


# --------------------------------------------------
# ERROR AND FAILURE ANALYSIS
# --------------------------------------------------

st.header("Error and Failure Analysis")

failure_df = all_requests_df.copy()

# Normalize status values
failure_df["status_normalized"] = (
    failure_df["status"]
    .fillna("unknown")
    .astype(str)
    .str.strip()
    .str.lower()
)

# A request is considered unsuccessful if its status is not success
failure_df["is_failed"] = (
    failure_df["status_normalized"] != "success"
)

total_failure_requests = len(failure_df)

failed_requests = failure_df[
    failure_df["is_failed"]
].copy()

total_failed = len(failed_requests)

failure_rate = (
    total_failed / total_failure_requests * 100
    if total_failure_requests > 0
    else 0
)

# Overview KPIs
st.subheader("Failure Overview")

col1, col2, col3 = st.columns(3)

col1.metric(
    "Total Failed Requests",
    f"{total_failed:,}"
)

col2.metric(
    "Failure Rate",
    f"{failure_rate:.2f}%"
)

col3.metric(
    "Total Requests",
    f"{total_failure_requests:,}"
)

st.divider()


if not failed_requests.empty:

    # --------------------------------------------------
    # PROVIDER-WISE FAILURE ANALYSIS
    # --------------------------------------------------

    st.subheader("Failures by Provider")

    provider_failure = failure_df.groupby(
        "provider",
        dropna=False
    ).agg(
        total_requests=("is_failed", "size"),
        failed_requests=("is_failed", "sum")
    ).reset_index()

    provider_failure["failure_rate"] = (
        provider_failure["failed_requests"]
        / provider_failure["total_requests"]
    ) * 100

    provider_failure = provider_failure.rename(
        columns={
            "provider": "Provider",
            "total_requests": "Total Requests",
            "failed_requests": "Failed Requests",
            "failure_rate": "Failure Rate (%)"
        }
    )

    st.dataframe(
        provider_failure.round(2),
        use_container_width=True,
        hide_index=True
    )

    provider_failure_chart = px.bar(
        provider_failure,
        x="Provider",
        y="Failed Requests",
        color="Provider",
        title="Failed Requests by Provider",
        hover_data=["Total Requests", "Failure Rate (%)"]
    )

    st.plotly_chart(
        provider_failure_chart,
        use_container_width=True
    )

    st.divider()

    # --------------------------------------------------
    # MODEL-WISE FAILURE ANALYSIS
    # --------------------------------------------------

    st.subheader("Failures by Model")

    model_failure = failure_df.groupby(
        ["provider", "model"],
        dropna=False
    ).agg(
        total_requests=("is_failed", "size"),
        failed_requests=("is_failed", "sum")
    ).reset_index()

    model_failure["failure_rate"] = (
        model_failure["failed_requests"]
        / model_failure["total_requests"]
    ) * 100

    model_failure = model_failure.rename(
        columns={
            "provider": "Provider",
            "model": "Model",
            "total_requests": "Total Requests",
            "failed_requests": "Failed Requests",
            "failure_rate": "Failure Rate (%)"
        }
    )

    st.dataframe(
        model_failure.round(2),
        use_container_width=True,
        hide_index=True
    )

    model_failure_chart = px.bar(
        model_failure,
        x="Model",
        y="Failed Requests",
        color="Provider",
        barmode="group",
        title="Failed Requests by Model",
        hover_data=["Total Requests", "Failure Rate (%)"]
    )

    st.plotly_chart(
        model_failure_chart,
        use_container_width=True
    )

    st.divider()

    # --------------------------------------------------
    # COMMON ERROR MESSAGES
    # --------------------------------------------------

    st.subheader("Common Error Messages")

    failed_requests["error_message"] = (
        failed_requests["error_message"]
        .fillna("No error message recorded")
        .astype(str)
        .str.strip()
        .replace("", "No error message recorded")
    )

    error_summary = (
        failed_requests["error_message"]
        .value_counts()
        .reset_index()
    )

    error_summary.columns = [
        "Error Message",
        "Occurrences"
    ]

    st.dataframe(
        error_summary.head(10),
        use_container_width=True,
        hide_index=True
    )

    error_chart = px.bar(
        error_summary.head(10),
        x="Occurrences",
        y="Error Message",
        orientation="h",
        title="Most Common Errors",
        text="Occurrences"
    )

    error_chart.update_layout(
        yaxis={"categoryorder": "total ascending"}
    )

    st.plotly_chart(
        error_chart,
        use_container_width=True
    )

    st.divider()

    # --------------------------------------------------
    # FAILURE TRENDS OVER TIME
    # --------------------------------------------------

    st.subheader("Failure Trends Over Time")

    failed_requests["timestamp"] = pd.to_datetime(
        failed_requests["timestamp"],
        errors="coerce"
    )

    trend_df = failed_requests.dropna(
        subset=["timestamp"]
    ).copy()

    if not trend_df.empty:

        trend_df["date"] = (
            trend_df["timestamp"].dt.date
        )

        daily_failures = trend_df.groupby(
            "date"
        ).size().reset_index(name="Failed Requests")

        failure_trend_chart = px.line(
            daily_failures,
            x="date",
            y="Failed Requests",
            markers=True,
            title="Daily Failed Requests"
        )

        st.plotly_chart(
            failure_trend_chart,
            use_container_width=True
        )

    else:
        st.info("No valid timestamps available for failure trends.")

    st.divider()

    # --------------------------------------------------
    # FAILED REQUEST DETAILS
    # --------------------------------------------------

    st.subheader("Failed Request Details")

    failure_columns = [
        "timestamp",
        "provider",
        "model",
        "status",
        "error_message",
        "prompt"
    ]

    st.dataframe(
        failed_requests[failure_columns],
        use_container_width=True,
        hide_index=True
    )

else:

    st.success(
        "No failed requests recorded. All recorded requests "
        "have a successful status."
    )

# --------------------------------------------------
# REQUEST SUCCESS AND FAILURE TRENDS
# --------------------------------------------------

st.header("Request Success and Failure Trends")

trend_df = all_requests_df.copy()

# Prepare timestamp and status columns
trend_df["timestamp"] = pd.to_datetime(
    trend_df["timestamp"],
    errors="coerce"
)

trend_df["status_normalized"] = (
    trend_df["status"]
    .fillna("unknown")
    .astype(str)
    .str.strip()
    .str.lower()
)

# Remove records without valid timestamps
trend_df = trend_df.dropna(
    subset=["timestamp"]
).copy()

if not trend_df.empty:

    # Extract date
    trend_df["date"] = trend_df["timestamp"].dt.date

    # Identify successful and failed requests
    trend_df["successful"] = (
        trend_df["status_normalized"] == "success"
    )

    trend_df["failed"] = ~trend_df["successful"]

    # --------------------------------------------------
    # DAILY REQUEST VOLUME
    # --------------------------------------------------

    st.subheader("Daily Request Volume")

    daily_requests = trend_df.groupby(
        "date"
    ).agg(
        total_requests=("status_normalized", "size"),
        successful_requests=("successful", "sum"),
        failed_requests=("failed", "sum")
    ).reset_index()

    daily_requests = daily_requests.rename(
        columns={
            "date": "Date",
            "total_requests": "Total Requests",
            "successful_requests": "Successful Requests",
            "failed_requests": "Failed Requests"
        }
    )

    st.dataframe(
        daily_requests,
        use_container_width=True,
        hide_index=True
    )

    volume_chart = px.bar(
        daily_requests,
        x="Date",
        y="Total Requests",
        title="Total Requests per Day",
        text="Total Requests"
    )

    st.plotly_chart(
        volume_chart,
        use_container_width=True
    )

    # --------------------------------------------------
    # SUCCESSFUL VS FAILED REQUESTS
    # --------------------------------------------------

    st.subheader("Successful vs Failed Requests")

    request_status_trend = daily_requests.melt(
        id_vars="Date",
        value_vars=[
            "Successful Requests",
            "Failed Requests"
        ],
        var_name="Request Status",
        value_name="Number of Requests"
    )

    status_trend_chart = px.bar(
        request_status_trend,
        x="Date",
        y="Number of Requests",
        color="Request Status",
        barmode="group",
        title="Daily Successful and Failed Requests"
    )

    st.plotly_chart(
        status_trend_chart,
        use_container_width=True
    )

    # --------------------------------------------------
    # DAILY SUCCESS RATE
    # --------------------------------------------------

    st.subheader("Daily Success Rate")

    daily_requests["Success Rate (%)"] = (
        daily_requests["Successful Requests"]
        / daily_requests["Total Requests"]
    ) * 100

    success_rate_chart = px.line(
        daily_requests,
        x="Date",
        y="Success Rate (%)",
        markers=True,
        title="Success Rate Over Time"
    )

    success_rate_chart.update_yaxes(
        range=[0, 100]
    )

    st.plotly_chart(
        success_rate_chart,
        use_container_width=True
    )

    # --------------------------------------------------
    # PROVIDER-WISE SUCCESS RATE TRENDS
    # --------------------------------------------------

    st.subheader("Provider-wise Success Rate Trends")

    provider_daily = trend_df.groupby(
        ["date", "provider"],
        dropna=False
    ).agg(
        total_requests=("successful", "size"),
        successful_requests=("successful", "sum")
    ).reset_index()

    provider_daily["Success Rate (%)"] = (
        provider_daily["successful_requests"]
        / provider_daily["total_requests"]
    ) * 100

    provider_daily = provider_daily.rename(
        columns={
            "date": "Date",
            "provider": "Provider",
            "total_requests": "Total Requests",
            "successful_requests": "Successful Requests"
        }
    )

    provider_success_chart = px.line(
        provider_daily,
        x="Date",
        y="Success Rate (%)",
        color="Provider",
        markers=True,
        hover_data=[
            "Total Requests",
            "Successful Requests"
        ],
        title="Provider Reliability Over Time"
    )

    provider_success_chart.update_yaxes(
        range=[0, 100]
    )

    st.plotly_chart(
        provider_success_chart,
        use_container_width=True
    )

else:

    st.info(
        "No valid timestamp records available for request trend analysis."
    )

# --------------------------------------------------
# TIMEOUT AND RETRY ANALYTICS
# --------------------------------------------------

st.header("Timeout and Retry Analytics")

# Use all database records, independent of sidebar filters.
reliability_df = all_requests_df.copy()

# Convert reliability columns to numeric values.
reliability_df["retry_count"] = pd.to_numeric(
    reliability_df["retry_count"],
    errors="coerce"
).fillna(0)

reliability_df["timed_out"] = pd.to_numeric(
    reliability_df["timed_out"],
    errors="coerce"
).fillna(0)

reliability_df["timeout_seconds"] = pd.to_numeric(
    reliability_df["timeout_seconds"],
    errors="coerce"
)

# Identify requests that experienced retries or timeouts.
reliability_df["was_retried"] = (
    reliability_df["retry_count"] > 0
)

reliability_df["experienced_timeout"] = (
    reliability_df["timed_out"] == 1
)

total_reliability_requests = len(reliability_df)

total_retries = int(
    reliability_df["retry_count"].sum()
)

retried_requests = int(
    reliability_df["was_retried"].sum()
)

timeout_requests = int(
    reliability_df["experienced_timeout"].sum()
)

retry_rate = (
    retried_requests / total_reliability_requests * 100
    if total_reliability_requests > 0 else 0
)

timeout_rate = (
    timeout_requests / total_reliability_requests * 100
    if total_reliability_requests > 0 else 0
)

# --------------------------------------------------
# RELIABILITY KPI CARDS
# --------------------------------------------------

st.subheader("Reliability Overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Total Retries",
    f"{total_retries:,}"
)

col2.metric(
    "Retried Requests",
    f"{retried_requests:,}"
)

col3.metric(
    "Timed-out Requests",
    f"{timeout_requests:,}"
)

col4.metric(
    "Timeout Rate",
    f"{timeout_rate:.2f}%"
)

st.caption(
    f"Retry rate: {retry_rate:.2f}% of all recorded requests."
)

st.divider()

# --------------------------------------------------
# RETRY COUNT DISTRIBUTION
# --------------------------------------------------

st.subheader("Retry Count Distribution")

retry_distribution = (
    reliability_df["retry_count"]
    .value_counts()
    .sort_index()
    .reset_index()
)

retry_distribution.columns = [
    "Retry Count",
    "Number of Requests"
]

retry_chart = px.bar(
    retry_distribution,
    x="Retry Count",
    y="Number of Requests",
    text="Number of Requests",
    title="Requests by Number of Retry Attempts"
)

st.plotly_chart(
    retry_chart,
    use_container_width=True
)

# --------------------------------------------------
# PROVIDER-WISE RELIABILITY
# --------------------------------------------------

st.subheader("Provider-wise Reliability")

provider_reliability = reliability_df.groupby(
    "provider",
    dropna=False
).agg(
    total_requests=("id", "count"),
    total_retries=("retry_count", "sum"),
    retried_requests=("was_retried", "sum"),
    timeout_requests=("experienced_timeout", "sum")
).reset_index()

provider_reliability["Retry Rate (%)"] = (
    provider_reliability["retried_requests"]
    / provider_reliability["total_requests"]
) * 100

provider_reliability["Timeout Rate (%)"] = (
    provider_reliability["timeout_requests"]
    / provider_reliability["total_requests"]
) * 100

provider_reliability = provider_reliability.rename(
    columns={
        "provider": "Provider",
        "total_requests": "Total Requests",
        "total_retries": "Total Retries",
        "retried_requests": "Retried Requests",
        "timeout_requests": "Timed-out Requests"
    }
)

st.dataframe(
    provider_reliability.round(2),
    use_container_width=True,
    hide_index=True
)

# Provider retry comparison
provider_retry_chart = px.bar(
    provider_reliability,
    x="Provider",
    y="Total Retries",
    color="Provider",
    title="Total Retry Attempts by Provider"
)

st.plotly_chart(
    provider_retry_chart,
    use_container_width=True
)

# Provider timeout comparison
provider_timeout_chart = px.bar(
    provider_reliability,
    x="Provider",
    y="Timed-out Requests",
    color="Provider",
    title="Timed-out Requests by Provider"
)

st.plotly_chart(
    provider_timeout_chart,
    use_container_width=True
)

st.divider()

# --------------------------------------------------
# TIMEOUT AND RETRY TRENDS
# --------------------------------------------------

st.subheader("Timeout and Retry Trends Over Time")

reliability_df["timestamp"] = pd.to_datetime(
    reliability_df["timestamp"],
    errors="coerce"
)

reliability_trend = reliability_df.dropna(
    subset=["timestamp"]
).copy()

if not reliability_trend.empty:

    reliability_trend["Date"] = (
        reliability_trend["timestamp"].dt.date
    )

    daily_reliability = reliability_trend.groupby(
        "Date"
    ).agg(
        Total_Retries=("retry_count", "sum"),
        Timed_Out_Requests=("experienced_timeout", "sum")
    ).reset_index()

    daily_reliability = daily_reliability.rename(
        columns={
            "Total_Retries": "Total Retries",
            "Timed_Out_Requests": "Timed-out Requests"
        }
    )

    retry_trend_chart = px.line(
        daily_reliability,
        x="Date",
        y="Total Retries",
        markers=True,
        title="Daily Retry Attempts"
    )

    st.plotly_chart(
        retry_trend_chart,
        use_container_width=True
    )

    timeout_trend_chart = px.line(
        daily_reliability,
        x="Date",
        y="Timed-out Requests",
        markers=True,
        title="Daily Timeout Frequency"
    )

    st.plotly_chart(
        timeout_trend_chart,
        use_container_width=True
    )

else:

    st.info(
        "No valid timestamps available for reliability trends."
    )

st.divider()

# --------------------------------------------------
# RETRIED AND TIMED-OUT REQUEST DETAILS
# --------------------------------------------------

st.subheader("Retried and Timed-out Request Details")

problem_requests = reliability_df[
    (reliability_df["retry_count"] > 0)
    | (reliability_df["timed_out"] == 1)
].copy()

if not problem_requests.empty:

    reliability_columns = [
        "timestamp",
        "provider",
        "model",
        "status",
        "retry_count",
        "timeout_seconds",
        "timed_out",
        "latency_ms",
        "error_message"
    ]

    st.dataframe(
        problem_requests[reliability_columns],
        use_container_width=True,
        hide_index=True
    )

else:

    st.success(
        "No retried or timed-out requests recorded."
    )


# --------------------------------------------------
# REPEATED-RUN PERFORMANCE COMPARISON
# --------------------------------------------------

st.header("Performance Comparison Across Repeated Runs")

# Use all database records, independent of sidebar filters.
repeated_df = all_requests_df.copy()

# Only successful requests are suitable for performance comparison.
repeated_df = repeated_df[
    repeated_df["status"] == "success"
].copy()

# Prepare columns.
repeated_df["timestamp"] = pd.to_datetime(
    repeated_df["timestamp"],
    errors="coerce"
)

repeated_df["prompt"] = (
    repeated_df["prompt"]
    .fillna("")
    .astype(str)
    .str.strip()
)

repeated_df["latency_ms"] = pd.to_numeric(
    repeated_df["latency_ms"],
    errors="coerce"
)

repeated_df["throughput_tokens_per_second"] = pd.to_numeric(
    repeated_df["throughput_tokens_per_second"],
    errors="coerce"
)

# Remove incomplete records.
repeated_df = repeated_df[
    (repeated_df["prompt"] != "")
    & repeated_df["latency_ms"].notna()
].copy()

if not repeated_df.empty:

    # Group identical prompts by provider and model.
    repeated_groups = repeated_df.groupby(
        ["provider", "model", "prompt"]
    ).agg(
        runs=("id", "count"),
        avg_latency=("latency_ms", "mean"),
        std_latency=("latency_ms", "std"),
        min_latency=("latency_ms", "min"),
        max_latency=("latency_ms", "max"),
        p50_latency=(
            "latency_ms",
            "median"
        ),
        p95_latency=(
            "latency_ms",
            lambda x: x.quantile(0.95)
        ),
        avg_throughput=(
            "throughput_tokens_per_second",
            "mean"
        )
    ).reset_index()

    # Retain prompts executed at least twice.
    repeated_groups = repeated_groups[
        repeated_groups["runs"] >= 2
    ].copy()

    if not repeated_groups.empty:

        # Calculate latency consistency.
        repeated_groups["latency_cv"] = (
            repeated_groups["std_latency"]
            / repeated_groups["avg_latency"]
        ) * 100

        # Handle zero or unavailable standard deviation.
        repeated_groups["latency_cv"] = (
            repeated_groups["latency_cv"]
            .fillna(0)
        )

        # --------------------------------------------------
        # REPEATED-RUN SUMMARY TABLE
        # --------------------------------------------------

        st.subheader("Repeated Prompt Performance Summary")

        st.caption(
            "Only successful requests with identical provider, "
            "model and prompt are grouped together."
        )

        display_repeated = repeated_groups.rename(
            columns={
                "provider": "Provider",
                "model": "Model",
                "prompt": "Prompt",
                "runs": "Number of Runs",
                "avg_latency": "Average Latency (ms)",
                "std_latency": "Latency Std Dev (ms)",
                "min_latency": "Minimum Latency (ms)",
                "max_latency": "Maximum Latency (ms)",
                "p50_latency": "P50 Latency (ms)",
                "p95_latency": "P95 Latency (ms)",
                "avg_throughput": "Average Throughput (tokens/sec)",
                "latency_cv": "Latency CV (%)"
            }
        )

        st.dataframe(
            display_repeated.round(3),
            use_container_width=True,
            hide_index=True
        )

        # --------------------------------------------------
        # LATENCY CONSISTENCY COMPARISON
        # --------------------------------------------------

        st.subheader("Latency Consistency Across Repeated Runs")

        consistency_chart = px.bar(
            display_repeated,
            x="Model",
            y="Latency CV (%)",
            color="Provider",
            barmode="group",
            hover_data=[
                "Number of Runs",
                "Average Latency (ms)"
            ],
            title="Latency Variation (Lower is More Consistent)"
        )

        st.plotly_chart(
            consistency_chart,
            use_container_width=True
        )

        # --------------------------------------------------
        # SELECT A PROMPT TO INSPECT INDIVIDUAL RUNS
        # --------------------------------------------------

        st.subheader("Individual Run Analysis")

        prompt_options = [
            (row["provider"], row["model"], row["prompt"])
            for _, row in repeated_groups.iterrows()
        ]

        selected_group = st.selectbox(
            "Select a repeated prompt",
            prompt_options,
            format_func=lambda x: (
                f"{x[0]} | {x[1]} | {x[2][:70]}"
            )
        )

        selected_runs = repeated_df[
            (repeated_df["provider"] == selected_group[0])
            & (repeated_df["model"] == selected_group[1])
            & (repeated_df["prompt"] == selected_group[2])
        ].copy()

        selected_runs = selected_runs.sort_values(
            ["timestamp", "id"]
        )

        selected_runs["Run Number"] = range(
            1, len(selected_runs) + 1
        )

        # Latency per run.
        run_latency_chart = px.line(
            selected_runs,
            x="Run Number",
            y="latency_ms",
            markers=True,
            title="Response Latency for Each Run"
        )

        st.plotly_chart(
            run_latency_chart,
            use_container_width=True
        )

        # Throughput per run.
        throughput_runs = selected_runs.dropna(
            subset=["throughput_tokens_per_second"]
        )

        if not throughput_runs.empty:

            run_throughput_chart = px.line(
                throughput_runs,
                x="Run Number",
                y="throughput_tokens_per_second",
                markers=True,
                title="Throughput for Each Run"
            )

            st.plotly_chart(
                run_throughput_chart,
                use_container_width=True
            )

        st.caption(
            "Latency CV is calculated as standard deviation divided "
            "by average latency. A lower value indicates more "
            "consistent response times. These comparisons are "
            "descriptive and do not establish causation."
        )

    else:

        st.info(
            "No identical successful prompts have been executed "
            "at least twice for the same provider and model. "
            "Run the same prompt multiple times in the Playground "
            "to generate comparison data."
        )

else:

    st.info(
        "No successful requests with valid prompts and latency "
        "are available for repeated-run analysis."
    )


# --------------------------------------------------

# --------------------------------------------------
# ZERO-COST PERFORMANCE COMPARISON
# --------------------------------------------------

st.header("Zero-Cost Performance Comparison")

# Create a separate copy of database records.
performance_df = all_requests_df.copy()

# Exclude the historical provider/model mismatch.
invalid_record = (
    (performance_df["provider"].str.lower() == "ollama") &
    (performance_df["model"] == "openrouter/free")
)

performance_df = performance_df[~invalid_record].copy()

# Convert metric columns to numeric.
performance_df["latency_ms"] = pd.to_numeric(
    performance_df["latency_ms"], errors="coerce"
)
performance_df["throughput_tokens_per_second"] = pd.to_numeric(
    performance_df["throughput_tokens_per_second"], errors="coerce"
)
performance_df["cost"] = pd.to_numeric(
    performance_df["cost"], errors="coerce"
)

# Current usage is free for Ollama and OpenRouter models marked :free.
# Apply confirmed zero API cost to this dashboard copy only; SQLite history
# remains unchanged. Any other missing cost stays unknown (NaN).
provider_normalized = performance_df["provider"].fillna("").astype(str).str.lower()
model_normalized = performance_df["model"].fillna("").astype(str).str.lower()
free_usage_mask = (
    (provider_normalized == "ollama")
    | (
        (provider_normalized == "openrouter")
        & (
            model_normalized.str.endswith(":free")
            | (model_normalized == "openrouter/free")
        )
    )
)
performance_df.loc[free_usage_mask, "cost"] = 0.0

# Identify successful requests.
performance_df["is_success"] = (
    performance_df["status"].fillna("").astype(str).str.lower() == "success"
)

# --------------------------------------------------
# CURRENT COST OVERVIEW
# --------------------------------------------------

st.subheader("Current Usage Cost")

ollama_rows = performance_df[provider_normalized == "ollama"]
openrouter_rows = performance_df[provider_normalized == "openrouter"]

ollama_known_cost = ollama_rows["cost"].dropna().sum()
openrouter_known_cost = openrouter_rows["cost"].dropna().sum()
combined_known_cost = performance_df["cost"].dropna().sum()
unknown_cost_requests = int(performance_df["cost"].isna().sum())

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ollama Usage Cost", f"${ollama_known_cost:.4f}")
col2.metric("OpenRouter Usage Cost", f"${openrouter_known_cost:.4f}")
col3.metric("Combined Known Cost", f"${combined_known_cost:.4f}")
col4.metric("Unknown-Cost Requests", f"{unknown_cost_requests:,}")

st.caption(
    "Ollama usage and OpenRouter models marked :free are counted as $0 API cost. "
    "Missing prices for other models remain unknown, not zero. These figures "
    "exclude local hardware and electricity costs."
)

st.divider()

# --------------------------------------------------
# PROVIDER AND MODEL PERFORMANCE
# --------------------------------------------------

st.subheader("Provider-wise and Model-wise Performance")

if not performance_df.empty:

    performance_summary = performance_df.groupby(
        ["provider", "model"],
        dropna=False
    ).agg(
        total_requests=("id", "count"),
        successful_requests=("is_success", "sum"),
        avg_latency=(
            "latency_ms",
            lambda x: x[performance_df.loc[x.index, "is_success"]].mean()
        ),
        avg_throughput=(
            "throughput_tokens_per_second",
            lambda x: x[performance_df.loc[x.index, "is_success"]].mean()
        ),
        avg_cost=("cost", "mean"),
        total_known_cost=("cost", "sum"),
        known_cost_requests=("cost", "count")
    ).reset_index()

    performance_summary["success_rate"] = (
        performance_summary["successful_requests"]
        / performance_summary["total_requests"]
    ) * 100

    performance_summary = performance_summary.rename(
        columns={
            "provider": "Provider",
            "model": "Model",
            "total_requests": "Total Requests",
            "successful_requests": "Successful Requests",
            "avg_latency": "Average Latency (ms)",
            "avg_throughput": "Average Throughput (tokens/sec)",
            "avg_cost": "Average Cost per Request ($)",
            "total_known_cost": "Total Known Cost ($)",
            "known_cost_requests": "Requests with Known Cost",
            "success_rate": "Success Rate (%)"
        }
    )

    st.dataframe(
        performance_summary.round(2),
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Average cost is calculated using requests with known cost only. "
        "The known-cost request count shows the coverage used for each average."
    )

    st.divider()

    # --------------------------------------------------
    # LATENCY COMPARISON
    # --------------------------------------------------

    st.subheader("Average Latency Comparison")

    latency_data = performance_summary.dropna(
        subset=["Average Latency (ms)"]
    )

    if not latency_data.empty:

        latency_comparison = px.bar(
            latency_data,
            x="Model",
            y="Average Latency (ms)",
            color="Provider",
            barmode="group",
            title="Average Response Latency by Provider and Model"
        )

        st.plotly_chart(
            latency_comparison,
            use_container_width=True
        )

    else:
        st.info("No successful requests available for latency comparison.")

    # --------------------------------------------------
    # COST VS LATENCY ANALYSIS
    # --------------------------------------------------

    st.subheader("Cost vs Latency Analysis")

    cost_latency_data = performance_summary.dropna(
        subset=["Average Cost per Request ($)", "Average Latency (ms)"]
    ).copy()

    if not cost_latency_data.empty:
        cost_latency_chart = px.scatter(
            cost_latency_data,
            x="Average Cost per Request ($)",
            y="Average Latency (ms)",
            color="Provider",
            size="Successful Requests",
            hover_name="Model",
            hover_data=[
                "Total Requests",
                "Successful Requests",
                "Requests with Known Cost",
                "Success Rate (%)"
            ],
            title="Average API Usage Cost vs Response Latency"
        )
        st.plotly_chart(cost_latency_chart, use_container_width=True)
        st.caption(
            "Each point represents a provider/model combination. Lower latency "
            "and lower API usage cost are preferable. Unknown-cost requests are "
            "not treated as zero in the cost comparison."
        )
        if (cost_latency_data["Average Cost per Request ($)"] == 0).all():
            st.info(
                "All displayed models currently have $0 API usage cost, so the "
                "points align at zero cost. A paid-model comparison will show "
                "a cost trade-off when paid models are used."
            )
    else:
        st.info("There are not enough known cost and latency values to plot this comparison.")

    # --------------------------------------------------
    # THROUGHPUT COMPARISON
    # --------------------------------------------------

    st.subheader("Average Throughput Comparison")

    throughput_data = performance_summary.dropna(
        subset=["Average Throughput (tokens/sec)"]
    )

    if not throughput_data.empty:

        throughput_comparison = px.bar(
            throughput_data,
            x="Model",
            y="Average Throughput (tokens/sec)",
            color="Provider",
            barmode="group",
            title="Average Token Generation Speed"
        )

        st.plotly_chart(
            throughput_comparison,
            use_container_width=True
        )

    else:
        st.info("No throughput data available.")

    # --------------------------------------------------
    # SUCCESS RATE COMPARISON
    # --------------------------------------------------

    st.subheader("Request Success Rate Comparison")

    success_comparison = px.bar(
        performance_summary,
        x="Model",
        y="Success Rate (%)",
        color="Provider",
        barmode="group",
        title="Successful Requests by Provider and Model",
        range_y=[0, 100]
    )

    st.plotly_chart(
        success_comparison,
        use_container_width=True
    )

else:

    st.info("No request records available for performance comparison.")

st.divider()

# --------------------------------------------------
# LATENCY CHART
# --------------------------------------------------

st.subheader("Request Latency Over Time")

latency_df = (
    df.dropna(subset=["timestamp"])
    .sort_values("timestamp")
)

if not latency_df.empty:

    fig_latency = px.line(
        latency_df,
        x="timestamp",
        y="latency_ms",
        color="model",
        markers=True,
        title="Latency (milliseconds)"
    )

    st.plotly_chart(
        fig_latency,
        use_container_width=True
    )

else:
    st.info("No valid timestamp data available.")


# --------------------------------------------------
# TOKEN USAGE CHART
# --------------------------------------------------

st.subheader("Token Usage Analysis")

token_df = df.groupby(
    "model",
    as_index=False
)[
    ["prompt_tokens", "completion_tokens"]
].sum()

token_df = token_df.melt(
    id_vars="model",
    var_name="Token Type",
    value_name="Tokens"
)

fig_tokens = px.bar(
    token_df,
    x="model",
    y="Tokens",
    color="Token Type",
    barmode="group",
    title="Input vs Output Tokens"
)

st.plotly_chart(
    fig_tokens,
    use_container_width=True
)


# --------------------------------------------------
# REQUEST STATUS CHART
# --------------------------------------------------

st.subheader("Request Status")

status_df = (
    df["status"]
    .value_counts()
    .reset_index()
)

status_df.columns = [
    "Status",
    "Count"
]

fig_status = px.pie(
    status_df,
    names="Status",
    values="Count",
    hole=0.4,
    title="Success vs Failed Requests"
)

st.plotly_chart(
    fig_status,
    use_container_width=True
)


# --------------------------------------------------
# REQUEST HISTORY
# --------------------------------------------------

st.subheader("Request History")

display_columns = [
    "timestamp",
    "provider",
    "model",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "latency_ms",
    "time_to_first_token_ms",
    "generation_time_ms",
    "throughput_tokens_per_second",
    "cost",
    "status"
]

st.dataframe(
    df[display_columns],
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# PROMPT AND RESPONSE DETAILS
# --------------------------------------------------

with st.expander("View Prompt and Response Details"):

    for _, row in df.iterrows():

        st.markdown(f"**Provider:** {row['provider']}")
        st.markdown(f"**Model:** {row['model']}")
        st.markdown(f"**Status:** {row['status']}")

        st.markdown("**Prompt:**")
        st.write(row["prompt"])

        st.markdown("**Response:**")
        st.write(row["response"])

        st.divider()


# --------------------------------------------------
# --------------------------------------------------
# QUALITY VS PERFORMANCE COMPARISON
# --------------------------------------------------

st.divider()
st.header("Quality vs Performance Comparison")
st.caption(
    "This section combines benchmark performance metrics with manually entered "
    "quality evaluations. It does not generate or modify evaluation scores."
)


def load_quality_data():
    quality_conn = get_connection()
    try:
        quality_df = pd.read_sql_query(
            """
            SELECT
                id,
                benchmark_id,
                category,
                provider,
                model,
                prompt,
                response,
                latency_ms,
                time_to_first_token_ms,
                generation_time_ms,
                throughput_tokens_per_second,
                correctness_score,
                relevance_score,
                completeness_score,
                clarity_score,
                quality_score,
                evaluator_notes,
                status,
                executed_at,
                evaluated_at
            FROM benchmark_results
            WHERE status = 'success'
            ORDER BY executed_at DESC
            """,
            quality_conn
        )
    finally:
        quality_conn.close()
    return quality_df


quality_all_df = load_quality_data()

if quality_all_df.empty:
    st.info(
        "No successful benchmark responses are available yet. Run the benchmark "
        "from the Benchmark Evaluation page before reviewing quality analytics."
    )
else:
    quality_all_df["quality_score"] = pd.to_numeric(
        quality_all_df["quality_score"], errors="coerce"
    )

    quality_evaluated_all = quality_all_df[
        quality_all_df["quality_score"].notna()
    ].copy()

    coverage_col1, coverage_col2, coverage_col3 = st.columns(3)
    successful_benchmarks = len(quality_all_df)
    evaluated_benchmarks = len(quality_evaluated_all)
    pending_evaluations = successful_benchmarks - evaluated_benchmarks
    evaluation_coverage = (
        evaluated_benchmarks / successful_benchmarks * 100
        if successful_benchmarks else 0
    )

    coverage_col1.metric("Successful Benchmark Responses", f"{successful_benchmarks:,}")
    coverage_col2.metric("Manually Evaluated Responses", f"{evaluated_benchmarks:,}")
    coverage_col3.metric("Pending Evaluations", f"{pending_evaluations:,}")
    st.progress(evaluation_coverage / 100)
    st.caption(f"Evaluation coverage: {evaluation_coverage:.1f}% of successful benchmark responses")

    if quality_evaluated_all.empty:
        st.info(
            "There are no saved manual evaluations yet. Open the **Benchmark Evaluation** "
            "page, select an existing successful response, enter the four rubric scores, "
            "and save. This dashboard will then display the results."
        )
    else:
        st.markdown("#### Quality analytics filters")
        quality_filter_col1, quality_filter_col2, quality_filter_col3 = st.columns(3)

        quality_providers = ["All"] + sorted(
            quality_evaluated_all["provider"].dropna().astype(str).unique().tolist()
        )
        quality_selected_provider = quality_filter_col1.selectbox(
            "Provider", quality_providers, key="quality_provider_filter"
        )

        quality_provider_df = quality_evaluated_all.copy()
        if quality_selected_provider != "All":
            quality_provider_df = quality_provider_df[
                quality_provider_df["provider"] == quality_selected_provider
            ]

        quality_models = ["All"] + sorted(
            quality_provider_df["model"].dropna().astype(str).unique().tolist()
        )
        quality_selected_model = quality_filter_col2.selectbox(
            "Model", quality_models, key="quality_model_filter"
        )

        quality_model_df = quality_provider_df.copy()
        if quality_selected_model != "All":
            quality_model_df = quality_model_df[
                quality_model_df["model"] == quality_selected_model
            ]

        quality_categories = ["All"] + sorted(
            quality_model_df["category"].dropna().astype(str).unique().tolist()
        )
        quality_selected_category = quality_filter_col3.selectbox(
            "Benchmark category", quality_categories, key="quality_category_filter"
        )

        quality_df = quality_model_df.copy()
        if quality_selected_category != "All":
            quality_df = quality_df[
                quality_df["category"] == quality_selected_category
            ]

        if quality_df.empty:
            st.warning("No evaluated benchmark responses match these filters.")
        else:
            rubric_columns = [
                "correctness_score",
                "relevance_score",
                "completeness_score",
                "clarity_score"
            ]
            for score_column in rubric_columns + ["latency_ms", "throughput_tokens_per_second"]:
                quality_df[score_column] = pd.to_numeric(
                    quality_df[score_column], errors="coerce"
                )

            avg_quality = quality_df["quality_score"].mean()
            avg_correctness = quality_df["correctness_score"].mean()
            avg_relevance = quality_df["relevance_score"].mean()
            avg_completeness = quality_df["completeness_score"].mean()
            avg_clarity = quality_df["clarity_score"].mean()

            st.markdown("#### Manual evaluation summary")
            qk1, qk2, qk3, qk4, qk5 = st.columns(5)
            qk1.metric("Evaluated Responses", f"{len(quality_df):,}")
            qk2.metric("Average Quality", f"{avg_quality:.1f}/100")
            qk3.metric("Correctness", f"{avg_correctness:.1f}/40")
            qk4.metric("Relevance", f"{avg_relevance:.1f}/25")
            qk5.metric("Completeness", f"{avg_completeness:.1f}/20")

            st.metric("Average Clarity", f"{avg_clarity:.1f}/15")

            st.caption(
                "Correctness: 40 points | Relevance: 25 points | "
                "Completeness: 20 points | Clarity: 15 points. "
                "These are subjective human evaluations, not objective ground-truth labels."
            )

            st.markdown("#### Average quality score by provider and model")
            quality_grouped = (
                quality_df.groupby(["provider", "model"], dropna=False)
                .agg(
                    average_quality=("quality_score", "mean"),
                    evaluated_responses=("id", "count")
                )
                .reset_index()
            )
            quality_grouped["provider_model"] = (
                quality_grouped["provider"].astype(str)
                + " / " + quality_grouped["model"].astype(str)
            )
            quality_fig = px.bar(
                quality_grouped,
                x="average_quality",
                y="provider_model",
                orientation="h",
                text="evaluated_responses",
                hover_data={
                    "evaluated_responses": True,
                    "average_quality": ":.1f"
                },
                labels={
                    "provider_model": "Provider / Model",
                    "average_quality": "Average quality score (/100)",
                    "evaluated_responses": "Evaluated responses"
                },
                range_x=[0, 100]
            )

            quality_fig.update_traces(
                texttemplate="%{text} evaluations",
                textposition="outside",
                cliponaxis=False
            )

            quality_fig.update_layout(
                yaxis={"categoryorder": "total ascending"},
                xaxis_title="Average quality score (/100)"
            )

            st.plotly_chart(quality_fig, use_container_width=True)

            st.markdown("#### Rubric criterion comparison")

            rubric_max_scores = {
                "correctness_score": 40,
                "relevance_score": 25,
                "completeness_score": 20,
                "clarity_score": 15
            }

            rubric_labels = {
                "correctness_score": "Correctness",
                "relevance_score": "Relevance",
                "completeness_score": "Completeness",
                "clarity_score": "Clarity"
            }

            rubric_long = quality_df.melt(
                id_vars=["provider", "model"],
                value_vars=rubric_columns,
                var_name="criterion",
                value_name="score"
            ).dropna(subset=["score"])

            rubric_long["maximum_score"] = rubric_long["criterion"].map(
                rubric_max_scores
            )

            rubric_long["score_percentage"] = (
                rubric_long["score"] /
                rubric_long["maximum_score"]
            ) * 100

            rubric_long["criterion"] = rubric_long["criterion"].map(
                rubric_labels
            )

            rubric_long["provider_model"] = (
                rubric_long["provider"].astype(str)
                + " / "
                + rubric_long["model"].astype(str)
            )

            rubric_summary = (
                rubric_long.groupby(
                    ["provider_model", "criterion"],
                    as_index=False
                )["score_percentage"].mean()
            )

            rubric_fig = px.bar(
                rubric_summary,
                x="provider_model",
                y="score_percentage",
                color="criterion",
                barmode="group",
                labels={
                    "provider_model": "Provider / Model",
                    "score_percentage": "Average score (% of maximum)",
                    "criterion": "Evaluation criterion"
                },
                range_y=[0, 100]
            )

            rubric_fig.update_layout(xaxis_tickangle=-25)

            st.plotly_chart(rubric_fig, use_container_width=True)

            st.markdown("#### Quality score vs latency")
            latency_quality_df = quality_df.dropna(subset=["latency_ms", "quality_score"])
            if not latency_quality_df.empty:
                latency_fig = px.scatter(
                    latency_quality_df,
                    x="latency_ms",
                    y="quality_score",
                    color="provider",
                    symbol="model",
                    hover_data=["benchmark_id", "category", "evaluated_at"],
                    labels={
                        "latency_ms": "Latency (ms)",
                        "quality_score": "Manual quality score (/100)"
                    }
                )
                latency_fig.update_layout(yaxis_range=[0, 100])
                st.plotly_chart(latency_fig, use_container_width=True)
            else:
                st.info("Latency values are unavailable for the evaluated responses in this filter.")

            st.markdown("#### Quality score vs throughput")
            throughput_quality_df = quality_df.dropna(
                subset=["throughput_tokens_per_second", "quality_score"]
            )
            if not throughput_quality_df.empty:
                throughput_fig = px.scatter(
                    throughput_quality_df,
                    x="throughput_tokens_per_second",
                    y="quality_score",
                    color="provider",
                    symbol="model",
                    hover_data=["benchmark_id", "category", "evaluated_at"],
                    labels={
                        "throughput_tokens_per_second": "Throughput (tokens/second)",
                        "quality_score": "Manual quality score (/100)"
                    }
                )
                throughput_fig.update_layout(yaxis_range=[0, 100])
                st.plotly_chart(throughput_fig, use_container_width=True)
            else:
                st.info("Throughput values are unavailable for the evaluated responses in this filter.")

            st.markdown("#### Average quality by benchmark category")
            category_quality = (
                quality_df.groupby(["category", "provider"], as_index=False)
                .agg(average_quality=("quality_score", "mean"), responses=("id", "count"))
            )
            category_fig = px.bar(
                category_quality,
                x="category",
                y="average_quality",
                color="provider",
                barmode="group",
                hover_data={"responses": True, "average_quality": ":.1f"},
                labels={
                    "category": "Benchmark category",
                    "average_quality": "Average quality score (/100)",
                    "provider": "Provider"
                },
                range_y=[0, 100]
            )
            st.plotly_chart(category_fig, use_container_width=True)

            st.markdown("#### Saved evaluation records")
            quality_display_columns = [
                "id", "benchmark_id", "category", "provider", "model",
                "correctness_score", "relevance_score", "completeness_score",
                "clarity_score", "quality_score", "latency_ms",
                "throughput_tokens_per_second", "evaluated_at", "evaluator_notes"
            ]
            st.dataframe(
                quality_df[quality_display_columns].sort_values(
                    "evaluated_at", ascending=False, na_position="last"
                ),
                use_container_width=True,
                hide_index=True
            )

            st.caption(
                "Compare models on the same benchmark questions and categories where possible. "
                "Different question sets or evaluation coverage can affect the averages."
            )
