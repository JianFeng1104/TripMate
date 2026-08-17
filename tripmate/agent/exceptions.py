"""Safe exception types for the TripMate assistant."""


class AgentError(Exception):
    """Base class for errors that may be translated into friendly UI text."""


class MissingDeepSeekConfiguration(AgentError):
    """Raised when no DeepSeek API key is configured."""


class ProviderError(AgentError):
    """Raised for a classified DeepSeek API or network failure."""

    def __init__(self, category: str, status_code: int | None = None):
        super().__init__(category)
        self.category = category
        self.status_code = status_code


class ProviderTimeout(ProviderError):
    """Raised when DeepSeek exceeds the configured timeout."""

    def __init__(self):
        super().__init__("timeout")


class MalformedProviderResponse(AgentError):
    """Raised when DeepSeek does not return a valid assistant message."""


class MaxToolRoundsExceeded(AgentError):
    """Raised when the read-only tool loop reaches its hard limit."""
