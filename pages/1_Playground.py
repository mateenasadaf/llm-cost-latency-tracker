
import streamlit as st

from track import run_request

st.set_page_config(
    page_title="LLM Playground",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 LLM Playground")
st.caption("Chat with LLMs and monitor their inference performance.")

if "messages" not in st.session_state:
    st.session_state.messages = []


# --------------------------------------------------
# 1. SIDEBAR SETTINGS
# --------------------------------------------------

with st.sidebar:
    st.subheader("Playground Settings")

    provider_name = st.selectbox(
        "Select Provider",
        ["ollama", "openrouter"]
    )

    if provider_name == "ollama":
        model = st.selectbox(
            "Select Model",
            ["llama3.2"]
        )
    else:
        model = st.selectbox(
            "Select Model",
            ["openrouter/free"]
        )

    if st.button("Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# --------------------------------------------------
# 2. DISPLAY METRICS
# --------------------------------------------------

def display_metrics(metrics):

    with st.expander("View Request Metrics"):

        col1, col2 = st.columns(2)

        col1.metric("Provider", metrics["provider"])
        col2.metric("Model", metrics["model"])

        col3, col4 = st.columns(2)

        col3.metric("Prompt Tokens", metrics["prompt_tokens"])
        col4.metric("Completion Tokens", metrics["completion_tokens"])

        col5, col6 = st.columns(2)

        col5.metric("Total Tokens", metrics["total_tokens"])

        col6.metric(
            "Total Latency",
            f"{metrics['latency_ms'] / 1000:.2f} sec"
        )

        col7, col8 = st.columns(2)

        ttft = metrics.get("time_to_first_token_ms")
        generation = metrics.get("generation_time_ms")

        col7.metric(
            "Time to First Token",
            f"{ttft:.2f} ms" if ttft is not None else "Unavailable"
        )

        col8.metric(
            "Generation Time",
            f"{generation:.2f} ms"
            if generation is not None else "Unavailable"
        )

        throughput = metrics.get("throughput_tokens_per_second")

        st.metric(
            "Throughput",
            f"{throughput:.2f} tokens/sec"
            if throughput is not None else "Unavailable"
        )

        cost = metrics.get("cost")

        st.metric(
            "Estimated Cost",
            f"${cost:.8f}" if cost is not None else "Unavailable"
        )


# --------------------------------------------------
# 3. DISPLAY CONVERSATION HISTORY
# --------------------------------------------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])

        if message["role"] == "assistant" and "metrics" in message:

            display_metrics(message["metrics"])


# --------------------------------------------------
# 4. CHAT INPUT
# --------------------------------------------------

user_prompt = st.chat_input("Ask your LLM something...")

if user_prompt:

    st.session_state.messages.append({
        "role": "user",
        "content": user_prompt
    })

    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Build conversation context
    conversation_prompt = ""

    for message in st.session_state.messages:

        role = message["role"].upper()

        conversation_prompt += (
            f"{role}: {message['content']}\n"
        )

    # --------------------------------------------------
    # 5. GENERATE RESPONSE
    # --------------------------------------------------

    with st.chat_message("assistant"):

        with st.spinner("Generating response..."):

            try:

                result = run_request(
                    conversation_prompt,
                    model=model,
                    provider_name=provider_name
                )

                if result["status"] == "success":

                    response = result["response"]

                    st.markdown(response)

                    # Collect all request metrics
                    metrics = {
                        "provider": result["provider"],
                        "model": result["model"],
                        "prompt_tokens": result["prompt_tokens"],
                        "completion_tokens": result["completion_tokens"],
                        "total_tokens": result["total_tokens"],
                        "latency_ms": result["latency_ms"],
                        "time_to_first_token_ms": result["time_to_first_token_ms"],
                        "generation_time_ms": result["generation_time_ms"],
                        "throughput_tokens_per_second": result["throughput_tokens_per_second"],
                        "cost": result["cost"]
                    }

                    # Display metrics immediately
                    display_metrics(metrics)

                    # Save response and metrics in session
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response,
                        "metrics": metrics
                    })

                else:

                    error = result["error_message"] or "Unknown error"

                    st.error(f"Request failed: {error}")

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"Request failed: {error}"
                    })

            except Exception as e:

                st.error(f"Request failed: {str(e)}")
