
import requests
import time

url = "http://localhost:11434/api/generate"

payload = {
    "model": "llama3.2",
    "prompt": "Explain artificial intelligence in 3 sentences.",
    "stream": False
}

# Measure latency
start = time.perf_counter()

response = requests.post(
    url,
    json=payload,
    timeout=120
)

latency = (time.perf_counter() - start) * 1000

# Extract response
data = response.json()

print("\nLLM RESPONSE:")
print(data["response"])

print("\nMETRICS:")
print("Model:", data["model"])
print("Prompt tokens:", data["prompt_eval_count"])
print("Completion tokens:", data["eval_count"])
print(f"Latency: {latency:.2f} ms")
