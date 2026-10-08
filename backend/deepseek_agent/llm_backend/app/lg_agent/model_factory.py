from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_ollama import ChatOllama
from app.core.config import settings, ServiceType


def get_agent_model(tags: list[str] | None = None) -> BaseChatModel:
    tags = tags or []
    if settings.AGENT_SERVICE == ServiceType.DEEPSEEK:
        return ChatDeepSeek(
            api_key=settings.DEEPSEEK_API_KEY,
            model_name=settings.DEEPSEEK_MODEL,
            temperature=0.7,
            tags=tags,
        )
    return ChatOllama(
        model=settings.OLLAMA_AGENT_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.7,
        tags=tags,
    )
