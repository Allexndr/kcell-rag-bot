import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8337768970:AAH4A5kd08XZyjDPTHviAopFlXTuBQwHrHs")

DOCS_DIR = os.path.join(BASE_DIR, "data", "documents")
DB_DIR = os.path.join(BASE_DIR, "data", "chroma_db")

COLLECTION_NAME = "kcell_docs"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
GENERATION_MODEL = "gemini-2.0-flash"

# Performance and observability
CACHE_SIZE = 200  # LRU cache size for answers
ANALYTICS_LOG = "analytics/usage.log"  # JSONL usage log path

# Access control
ALLOWED_USER_IDS = {
    # заполни ID разрешённых пользователей Telegram
    # пример: 123456789,
}

# Rate limiting (per user)
RATE_LIMIT_WINDOW_SEC = 5   # окно в секундах
RATE_LIMIT_MAX = 5          # максимум сообщений в окне
