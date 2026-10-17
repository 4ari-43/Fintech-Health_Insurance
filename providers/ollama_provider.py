
import ollama

from providers.base import AIProvider


class OllamaProvider(AIProvider):
    """Runs an AI model locally through Ollama."""

    def __init__(self, model: str = "qwen3:8b"):
        self.model = model

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        response = ollama.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            format="json",
            options={
                "temperature": 0,
            },
            think=False,
        )

        return response["message"]["content"]
