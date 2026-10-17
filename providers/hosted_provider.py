
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from providers.base import AIProvider


class GeminiProvider(AIProvider):
    """Generates structured answers using Google's Gemini API."""

    def __init__(self, model: str = "gemini-3.1-flash-lite"):
        load_dotenv()

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing from .env")

        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=20000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

        self.model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        if not response.text:
            raise ValueError("Gemini returned an empty response")

        return response.text
