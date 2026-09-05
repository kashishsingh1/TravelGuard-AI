"""Unit tests for pre-LLM secret scrubbing in TravelGuard AI."""

import pytest
from travelguard.security import SecretScrubber, scrub_secrets, scrub_object


class TestSecretScrubber:
    """Validate that sensitive credentials are redacted while preserving benign text."""

    def test_redacts_groq_api_key(self):
        text = "Using GROQ_API_KEY=gsk_abcdef1234567890abcdef1234567890 to call LLM"
        scrubbed = scrub_secrets(text)
        assert "gsk_abcdef1234567890abcdef1234567890" not in scrubbed
        assert "[REDACTED_GROQ_KEY]" in scrubbed

    def test_redacts_openrouter_api_key(self):
        text = "Authorization: sk-or-v1-abcdef0123456789abcdef0123456789abcdef0123456789"
        scrubbed = scrub_secrets(text)
        assert "sk-or-v1-abcdef" not in scrubbed
        assert "[REDACTED_OPENROUTER_KEY]" in scrubbed

    def test_redacts_gemini_api_key(self):
        text = "GEMINI_API_KEY=AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q"
        scrubbed = scrub_secrets(text)
        assert "AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q" not in scrubbed
        assert "[REDACTED_GEMINI_KEY]" in scrubbed

    def test_redacts_bearer_token(self):
        text = "headers: {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIx'}"
        scrubbed = scrub_secrets(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in scrubbed
        assert "Bearer [REDACTED_BEARER_TOKEN]" in scrubbed

    def test_redacts_database_password_in_url(self):
        text = "Connecting to postgres://admin:SuperSecretPass123!@db.internal:5432/travelguard"
        scrubbed = scrub_secrets(text)
        assert "SuperSecretPass123!" not in scrubbed
        assert "[REDACTED_PASSWORD]" in scrubbed

    def test_preserves_legitimate_identifiers(self):
        benign = "Flight code SKB-101 from Delhi to Dubai with button class btn-primary and testid=book-flight"
        scrubbed = scrub_secrets(benign)
        assert scrubbed == benign

    def test_scrub_nested_dict_and_list(self):
        data = {
            "prompt": "Call with gsk_abcdef1234567890abcdef1234567890",
            "items": ["token: AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q", 42, True],
        }
        cleaned = scrub_object(data)
        assert "gsk_abcdef" not in cleaned["prompt"]
        assert "AIzaSy" not in cleaned["items"][0]
        assert cleaned["items"][1] == 42
        assert cleaned["items"][2] is True
