# Benchmark Evaluation Guide

## What was added

- `data/benchmark_dataset.json`: 12 fixed prompts, reference answers, and question-specific evaluation guidance.
- `benchmark.py`: runs each prompt independently for each selected provider.
- `pages/2_Benchmark_Evaluation.py`: benchmark execution and manual response scoring UI.
- `database.py`: creates `benchmark_results` and provides insert/evaluation helpers.
- `dashboard.py`: adds Quality vs Performance analytics.
- `track.py`: supports `save_to_history=False` so benchmark requests do not enter ordinary Playground history.

## Setup

From the project folder in PowerShell:

```powershell
.env\Scripts\Activate.ps1
pip install -r requirements.txt
```

Ensure Ollama is running and `llama3.2` is installed:

```powershell
ollama list
```

For OpenRouter, create a `.env` file in the project root:

```text
OPENROUTER_API_KEY=your_openrouter_api_key
```

Do not commit `.env`.

## Run

```powershell
streamlit run dashboard.py
```

Open **Benchmark Evaluation** in Streamlit's multipage navigation.

1. Select Ollama, OpenRouter, or both.
2. Click **Run selected benchmark(s)**. Each provider receives the same 12 prompts as independent requests.
3. Open **Evaluate Responses**.
4. Select each successful response, compare it with the reference answer, and assign rubric scores.
5. Save each evaluation.
6. Return to the main dashboard and inspect **Quality vs Performance Comparison**.

## Manual scoring rubric

| Criterion | Maximum points |
|---|---:|
| Factual / Technical Correctness | 40 |
| Relevance | 25 |
| Completeness | 20 |
| Clarity | 15 |
| **Total** | **100** |

The total is the sum of the four criterion scores. Unevaluated responses remain unscored; the app does not invent quality scores.

## Data preservation

Benchmark responses are written to `benchmark_results`. They are deliberately not inserted into `llm_requests`, so existing Playground analytics remain separate. `init_db()` uses `CREATE TABLE IF NOT EXISTS` and additive migrations; it does not delete or rebuild existing records.

The actual model returned by OpenRouter is stored for every response because `openrouter/free` can route to different models. OpenRouter generation time and throughput remain estimates in the existing provider implementation.

A full run with both providers executes 24 requests and may take several minutes depending on model latency, retries, and rate limits.
