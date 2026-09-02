from __future__ import annotations

import requests
from langchain_groq import ChatGroq

from backend.config import config


_PREFERRED_MODELS = (
    config.GROQ_MODEL,
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "qwen/qwen3.6-27b",
    "groq/compound-mini",
    "groq/compound",
)


def _available_groq_models() -> set[str]:
    if not config.GROQ_API_KEY:
        return set()

    response = requests.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()
    return {model["id"] for model in payload.get("data", []) if model.get("id")}


def create_chat_model() -> ChatGroq:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured.")

    try:
        available_models = _available_groq_models()
    except Exception:
        available_models = set()
    selected_model = config.GROQ_MODEL

    if available_models:
        for candidate in _PREFERRED_MODELS:
            if candidate in available_models:
                selected_model = candidate
                break

    return ChatGroq(
        api_key=config.GROQ_API_KEY,
        model=selected_model,
        temperature=config.GROQ_TEMPERATURE,
    )
