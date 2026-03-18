from dotenv import load_dotenv
import os

load_dotenv()

# --- City ---
CITY_NAME    = os.getenv("CITY_NAME", "Kolkata, India")
NETWORK_TYPE = "drive"

# --- Paths ---
BASE_DIR        = os.path.dirname(__file__)
GRAPH_CACHE_DIR = os.path.join(BASE_DIR, "data", "graphs")

# --- VRP ---
MAX_DRIVERS      = int(os.getenv("MAX_DRIVERS", 5))
VEHICLE_CAPACITY = int(os.getenv("VEHICLE_CAPACITY", 20))
MAX_ROUTE_TIME   = int(os.getenv("MAX_ROUTE_TIME", 14400))   # seconds (4 hours)
SOLVER_TIME_LIMIT = 30                                        # seconds

# --- Agent coordinator ---
COORDINATOR_POLL_SEC = 5
DELAY_THRESHOLD_SEC  = 300    # 5 min over ETA = delayed
IMBALANCE_THRESHOLD  = 0.3    # 30% load difference = rebalance

# --- Redis ---
REDIS_URL       = os.getenv("REDIS_URL", "redis://localhost:6379")
AGENT_STATE_TTL = 3600        # 1 hour

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hacktrek.db")

# --- LLM ---
LLM_PROVIDER    = os.getenv("LLM_PROVIDER", "ollama")   # "ollama" | "groq"
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL      = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# --- Embeddings ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- API ---
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))