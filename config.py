import os
from dotenv import load_dotenv

load_dotenv()

# Project directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_NAME = os.path.join(DATA_DIR, "llm_metrics.db")

os.makedirs(DATA_DIR, exist_ok=True)

# Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2"

# Request reliability
REQUEST_TIMEOUT = 120
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "openrouter/free"

# Model pricing: USD per million tokens
MODEL_RATES = {
    "ollama": {
        "llama3.2": {
            "input": 0.0,
            "output": 0.0
        }
    },
    "openrouter": {
        "nvidia/nemotron-3-ultra-550b-a55b:free": {
            "input": 0.0,
            "output": 0.0
        }
    }
}