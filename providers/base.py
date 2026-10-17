
from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Common interface for all AI model providers."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Generate a response using an AI model.

        Args:
            system_prompt: Instructions for the AI.
            user_prompt: Question and retrieved policy evidence.

        Returns:
            Raw AI response as a string.
        """
        pass
