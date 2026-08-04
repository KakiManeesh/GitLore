import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    ROOT_DIR = Path(__file__).resolve().parent.parent
    OUTPUT_DIR = ROOT_DIR / "Output"
    REPOSITORIES_DIR = OUTPUT_DIR / "repositories"
    LOCAL_CHROMA_DIR = OUTPUT_DIR / "chroma"

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.2"))

    CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")
    CHROMA_TENANT = os.getenv("CHROMA_TENANT")
    CHROMA_DATABASE = os.getenv("CHROMA_DATABASE")

    GITHUB_TOKEN = os.getenv("GIT_TOKEN") or os.getenv("GIT_KEY")
    DEFAULT_REPOSITORY = os.getenv("REPO_NAME", "daily-drive")

    MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "4500"))
    MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "8"))
    HYBRID_SEARCH_RESULTS = int(os.getenv("HYBRID_SEARCH_RESULTS", "10"))
    HYBRID_TOP_K = int(os.getenv("HYBRID_TOP_K", "5"))

    @classmethod
    def ensure_directories(cls) -> None:
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.REPOSITORIES_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOCAL_CHROMA_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
config.ensure_directories()
