
from unittest.mock import Mock

from google.genai import errors

from providers.fallback_provider import FallbackProvider


def test_fallback_to_second_model(monkeypatch):
    # No network call is made; the providers below are replaced by controlled mocks.
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder-not-a-real-key")
    provider = FallbackProvider()

    first = Mock()
    first.model = "first-model"
    first.generate.side_effect = errors.ServerError(
        503,
        {
            "error": {
                "code": 503,
                "message": "Temporarily unavailable",
                "status": "UNAVAILABLE",
            }
        },
        None,
    )

    second = Mock()
    second.model = "second-model"
    second.generate.return_value = '{"status": "SUPPORTED"}'

    provider.providers = [first, second]

    result = provider.generate(
        system_prompt="Test system prompt",
        user_prompt="Test question",
    )

    assert result == '{"status": "SUPPORTED"}'
    assert first.generate.call_count == 1
    assert second.generate.call_count == 1

