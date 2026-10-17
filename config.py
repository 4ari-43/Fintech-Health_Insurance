
import os

from dotenv import load_dotenv

from providers.ollama_provider import OllamaProvider
from providers.hosted_provider import GeminiProvider
from providers.fallback_provider import FallbackProvider


load_dotenv()


def get_provider():
    provider_name = os.getenv("AI_PROVIDER", "ollama").lower()

    if provider_name == "ollama":
        return OllamaProvider(model="qwen3:8b")

    if provider_name == "gemini":
        return GeminiProvider(model="gemini-3.5-flash-lite")

    if provider_name == "auto":
        return FallbackProvider()

    raise ValueError(
        f"Unknown AI_PROVIDER: {provider_name}. "
        "Choose 'ollama', 'gemini', or 'auto'."
    )
