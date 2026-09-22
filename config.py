"""Central config - thresholds, model names, paths. Edit here rather than scattering magic numbers."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env in the project root and sets the values as environment variables

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "docverify.db"
VECTOR_STORE_DIR = DATA_DIR / "chroma"

# Below this, a field is auto-accepted. Below this, it goes to the review queue.
CONFIDENCE_THRESHOLD = float(os.getenv("DOCVERIFY_CONFIDENCE_THRESHOLD", "0.85"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

OCR_ENGINE = os.getenv("DOCVERIFY_OCR_ENGINE", "tesseract")  # "tesseract" or "paddleocr"

ENABLE_VECTOR_INDEX = os.getenv("DOCVERIFY_ENABLE_VECTOR_INDEX", "false").lower() == "true"

DATA_DIR.mkdir(parents=True, exist_ok=True)