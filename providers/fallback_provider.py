
from google.genai import errors

from providers.base import AIProvider
from providers.hosted_provider import GeminiProvider


class FallbackProvider(AIProvider):
    def __init__(self):
        self.providers = [
    GeminiProvider(model="gemini-3.5-flash-lite"),
    GeminiProvider(model="gemini-3.1-flash-lite"),
    GeminiProvider(model="gemini-3.5-flash"),
]

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        last_error = None

        for provider in self.providers:
            try:
                print(f"Trying model: {provider.model}")

                response = provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )

                print(f"Model succeeded: {provider.model}")
                return response

            except (errors.ServerError, errors.ClientError) as exc:
                status = getattr(exc, "code", None)

                if status not in (429, 500, 502, 503, 504):
                    raise

                print(
                    f"Model {provider.model} unavailable "
                    f"(HTTP {status}). Trying fallback..."
                )
                last_error = exc

        raise RuntimeError(
            "All configured Gemini models are currently unavailable."
        ) from last_error
