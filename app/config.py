import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1")
# LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
DEFAULT_RAG_PATH = os.getenv("RAG_PATH", "rag.txt")
DEFAULT_MAPPING_PATH = os.getenv("MAPPING_PATH", "fs_to_udd_mapping.json")

if LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["LANGCHAIN_TRACING_V2"] = "true"

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set. Put it in .env")
