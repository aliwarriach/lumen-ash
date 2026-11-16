"""Errors the AI layer raises. `AiError`s turn into clean JSON responses; none is a 500."""

from datetime import datetime


class AiError(Exception):
    """Base class. `code` is stable and meant for the app to branch on."""

    status_code = 503
    code = "unavailable"

    def __init__(self, message: str, *, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after_seconds = retry_after_seconds


class AiLimitError(AiError):
    """The learner is over one of their own limits."""

    status_code = 429

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        resets_at: datetime | None = None,
    ) -> None:
        super().__init__(message, retry_after_seconds=retry_after_seconds)
        self.code = code
        self.resets_at = resets_at


class AiUnavailableError(AiError):
    """No provider could answer: not configured, rate limited, down, or over the shared ceiling."""

    status_code = 503

    def __init__(self, message: str, *, code: str = "unavailable") -> None:
        super().__init__(message)
        self.code = code


class AiBadResponseError(AiError):
    """A provider answered, but not with output that matches the expected shape."""

    status_code = 502
    code = "bad_response"


class AiInputError(AiError):
    """The text to send is too long."""

    status_code = 422
    code = "input_too_long"


# Provider-level failures. The gateway catches these; they never reach the API layer.


class ProviderError(Exception):
    pass


class ProviderRateLimited(ProviderError):
    """Rate limit or quota error (HTTP 429)."""

    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ProviderUnavailable(ProviderError):
    """Outage, timeout or network failure."""


class ProviderMisconfigured(ProviderUnavailable):
    """Our key, billing or model name is wrong (HTTP 401, 402, 403, 404). Trying again won't
    help until the setting is fixed, so the gateway leaves the provider alone for a while."""


class ProviderBadOutput(ProviderError):
    """The provider answered but the text was blocked, cut off or not JSON. Tokens were spent."""

    def __init__(self, message: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        super().__init__(message)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
