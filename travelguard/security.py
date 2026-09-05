"""Secret scrubbing layer for TravelGuard AI.

Ensures that sensitive data (API keys, authorization headers, bearer tokens,
passwords, and database connection strings) are scrubbed before:
  1. Sending prompts or diffs to LLMs (Groq, OpenRouter, Gemini)
  2. Writing structured logs or telemetry events
  3. Generating public artifacts or reports
"""

import re
from typing import Any, Dict, List, Union


class SecretScrubber:
    """Pre-LLM and pre-logging secret scrubber with regex-based redaction."""

    # Patterns matching sensitive token and key formats
    PATTERNS = [
        # Groq API keys: gsk_...
        (r"\bgsk_[A-Za-z0-9]{20,}\b", "[REDACTED_GROQ_KEY]"),
        # OpenRouter API keys: sk-or-v1-...
        (r"\bsk-or-v1-[A-Za-z0-9]{32,}\b", "[REDACTED_OPENROUTER_KEY]"),
        # Google Gemini / AI Studio keys: AIza...
        (r"\bAIza[0-9A-Za-z-_]{35}\b", "[REDACTED_GEMINI_KEY]"),
        # Generic sk-... tokens (OpenAI, Anthropic, etc.)
        (r"\bsk-[A-Za-z0-9]{20,}\b", "[REDACTED_API_KEY]"),
        # Bearer tokens in headers or strings
        (r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer [REDACTED_BEARER_TOKEN]"),
        # HTTP Basic / Token Authorization headers
        (r"(?i)(Authorization:\s*)(Basic|Token)\s+[A-Za-z0-9+/=]+", r"\1\2 [REDACTED_CREDENTIAL]"),
        # Passwords / secrets in database or service connection URLs
        (r"((?:postgres|postgresql|mongodb|mysql|redis)://[^:]+:)([^@]+)(@)", r"\1[REDACTED_PASSWORD]\3"),
        # Key-value assignments for sensitive variable names
        (
            r"(?i)\b(API_KEY|SECRET_KEY|AUTH_TOKEN|ACCESS_TOKEN|PASSWORD|PRIVATE_KEY)\s*[:=]\s*([\"']?)([^\"'\r\n\s]{8,})\2",
            r"\1=\2[REDACTED_SECRET]\2",
        ),
    ]

    def __init__(self):
        self._compiled = [(re.compile(pattern), repl) for pattern, repl in self.PATTERNS]

    def scrub(self, text: str) -> str:
        """Sanitize text by replacing sensitive patterns with redaction placeholders."""
        if not text or not isinstance(text, str):
            return text

        scrubbed = text
        for regex, replacement in self._compiled:
            scrubbed = regex.sub(replacement, scrubbed)
        return scrubbed

    def scrub_object(self, obj: Any) -> Any:
        """Recursively scrub strings within dictionaries, lists, or primitive types."""
        if isinstance(obj, str):
            return self.scrub(obj)
        elif isinstance(obj, dict):
            return {k: self.scrub_object(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.scrub_object(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self.scrub_object(item) for item in obj)
        return obj


_default_scrubber = SecretScrubber()


def scrub_secrets(text: str) -> str:
    """Convenience helper to scrub text using the default scrubber."""
    return _default_scrubber.scrub(text)


def scrub_object(obj: Any) -> Any:
    """Convenience helper to scrub arbitrary python data structures."""
    return _default_scrubber.scrub_object(obj)
