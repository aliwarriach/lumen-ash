"""One interface over the AI providers, so the rest of the app never knows which one answered.

Both providers are called over plain HTTPS with httpx: no vendor SDKs, nothing extra to install.
Each is asked for JSON only; the gateway checks the JSON against the template's Pydantic model.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.ai.errors import (
    ProviderBadOutput,
    ProviderMisconfigured,
    ProviderRateLimited,
    ProviderUnavailable,
)
from app.core.config import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AiRequest:
    system: str
    user: str
    max_output_tokens: int


@dataclass(frozen=True)
class AiResponse:
    data: dict[str, Any]
    # Token counts as reported by the provider, never our own estimate.
    input_tokens: int
    output_tokens: int
    provider: str
    model: str


class AiProvider(Protocol):
    name: str
    model: str

    async def generate(self, request: AiRequest) -> AiResponse: ...


def _retry_after(response: httpx.Response) -> int | None:
    value = response.headers.get("retry-after", "")
    return int(value) if value.isdigit() else None


# What each of these statuses means for us. None of them goes away by trying again.
_MISCONFIGURED = {
    401: "the API key was rejected",
    402: "the account has no credit: use a key from a free-tier project, or add billing",
    403: "the API key may not use this model or service",
    404: "the model name is wrong or the model was retired: check the *_MODEL setting",
}


def _error_code(response: httpx.Response) -> str | None:
    """The provider's own error code from an error response, if it sent one."""
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return None
    return str(error.get("code")) if isinstance(error, dict) and error.get("code") else None


async def _post(
    client: httpx.AsyncClient,
    provider: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """Sends the request and turns every failure into one of our three provider errors."""
    try:
        response = await client.post(url, headers=headers, json=body, timeout=timeout_seconds)
    except httpx.HTTPError as exc:  # timeouts, connection errors
        raise ProviderUnavailable(f"{provider}: {type(exc).__name__}") from exc

    status = response.status_code
    if status == 429:
        raise ProviderRateLimited(f"{provider}: rate limited", _retry_after(response))
    if status == 400 and _error_code(response) == "json_validate_failed":
        # Groq's JSON mode: the model ran out of room or wrote something that isn't JSON. The
        # provider itself is fine, so this is a bad answer, not an outage.
        raise ProviderBadOutput(f"{provider}: output was not valid JSON")
    if status in _MISCONFIGURED:
        # Our side is wrong (key, billing, model name) and will stay wrong until someone fixes
        # it. Logged loudly so Sentry sees it; the gateway then leaves the provider alone.
        reason = _MISCONFIGURED[status]
        log.error("%s returned HTTP %s: %s", provider, status, reason)
        raise ProviderMisconfigured(f"{provider}: HTTP {status} ({reason})")
    if status >= 400:
        log.warning("%s returned HTTP %s", provider, status)
        raise ProviderUnavailable(f"{provider}: HTTP {status}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderBadOutput(f"{provider}: response was not JSON") from exc
    if not isinstance(payload, dict):
        raise ProviderBadOutput(f"{provider}: unexpected response shape")
    return payload


def _parse_json_object(
    provider: str, text: str, input_tokens: int, output_tokens: int
) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ProviderBadOutput(
            f"{provider}: output was not JSON", input_tokens, output_tokens
        ) from exc
    if not isinstance(data, dict):
        raise ProviderBadOutput(
            f"{provider}: output was not a JSON object", input_tokens, output_tokens
        )
    return data


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta"
GROQ_API_URL = "https://api.groq.com/openai/v1"


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        model: str,
        timeout: float = 20.0,
        *,
        api_url: str = GEMINI_API_URL,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self.model = model
        self._timeout = timeout
        self._api_url = api_url.rstrip("/")

    async def generate(self, request: AiRequest) -> AiResponse:
        payload = await _post(
            self._client,
            self.name,
            f"{self._api_url}/models/{self.model}:generateContent",
            {"x-goog-api-key": self._api_key},  # in a header, so it can't leak through a URL
            {
                "systemInstruction": {"parts": [{"text": request.system}]},
                "contents": [{"role": "user", "parts": [{"text": request.user}]}],
                "generationConfig": {
                    "maxOutputTokens": request.max_output_tokens,
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            },
            self._timeout,
        )
        usage = payload.get("usageMetadata") or {}
        input_tokens = int(usage.get("promptTokenCount") or 0)
        # Thinking tokens are billed against the output limit, so they count too.
        output_tokens = int(usage.get("candidatesTokenCount") or 0) + int(
            usage.get("thoughtsTokenCount") or 0
        )
        candidates = payload.get("candidates") or []
        if not candidates:  # the prompt was blocked
            raise ProviderBadOutput("gemini: no answer", input_tokens, output_tokens)
        candidate = candidates[0]
        if candidate.get("finishReason") not in (None, "STOP"):  # cut off or blocked
            raise ProviderBadOutput(
                f"gemini: finished with {candidate.get('finishReason')}",
                input_tokens,
                output_tokens,
            )
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(str(p.get("text", "")) for p in parts)
        data = _parse_json_object(self.name, text, input_tokens, output_tokens)
        return AiResponse(data, input_tokens, output_tokens, self.name, self.model)


# A reasoning model's thinking is billed against the same limit as its answer. Without extra room
# the thinking alone can use the limit up, and the answer is cut off (seen live: 315 of 388
# tokens went on thinking). The template's own cap still bounds the answer we accept.
REASONING_HEADROOM_TOKENS = 600


class GroqProvider:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        model: str,
        timeout: float = 20.0,
        *,
        name: str = "groq",
        reasoning_effort: str = "",
        api_url: str = GROQ_API_URL,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self.model = model
        self._timeout = timeout
        self._api_url = api_url.rstrip("/")
        self.name = name  # "groq" or "groq_backup": usage and ceilings are kept per name
        self._reasoning_effort = reasoning_effort

    def _body(self, request: AiRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "max_completion_tokens": request.max_output_tokens,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        if self._reasoning_effort:
            body["reasoning_effort"] = self._reasoning_effort
            body["include_reasoning"] = False  # we only want the answer
            body["max_completion_tokens"] = request.max_output_tokens + REASONING_HEADROOM_TOKENS
        return body

    async def generate(self, request: AiRequest) -> AiResponse:
        payload = await _post(
            self._client,
            self.name,
            f"{self._api_url}/chat/completions",
            {"Authorization": f"Bearer {self._api_key}"},
            self._body(request),
            self._timeout,
        )
        usage = payload.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        choices = payload.get("choices") or []
        if not choices:
            raise ProviderBadOutput(f"{self.name}: no answer", input_tokens, output_tokens)
        choice = choices[0]
        if choice.get("finish_reason") not in (None, "stop"):  # e.g. "length" = cut off
            raise ProviderBadOutput(
                f"{self.name}: finished with {choice.get('finish_reason')}",
                input_tokens,
                output_tokens,
            )
        text = str((choice.get("message") or {}).get("content") or "")
        data = _parse_json_object(self.name, text, input_tokens, output_tokens)
        return AiResponse(data, input_tokens, output_tokens, self.name, self.model)


PROVIDER_NAMES = ("gemini", "groq", "groq_backup")


def build_providers(settings: Settings, client: httpx.AsyncClient) -> list[AiProvider]:
    """The providers to try, in the configured order. Ones without an API key are left out."""
    unknown = [n for n in settings.ai_providers if n not in PROVIDER_NAMES]
    if unknown:
        raise ValueError(f"Unknown AI provider in AI_PROVIDER_ORDER: {', '.join(unknown)}")
    timeout = settings.ai_request_timeout_seconds
    keys = {
        "gemini": settings.gemini_api_key,
        "groq": settings.groq_api_key,
        "groq_backup": settings.groq_backup_api_key,
    }
    providers: list[AiProvider] = []
    for name in dict.fromkeys(settings.ai_providers):  # in order, no duplicates
        key = keys[name]
        if key is None or not key.get_secret_value():
            continue
        if name == "gemini":
            providers.append(
                GeminiProvider(
                    client,
                    key.get_secret_value(),
                    settings.gemini_model,
                    timeout,
                    api_url=settings.gemini_api_url,
                )
            )
        else:
            providers.append(
                GroqProvider(
                    client,
                    key.get_secret_value(),
                    settings.groq_model,
                    timeout,
                    name=name,
                    reasoning_effort=settings.groq_reasoning_effort,
                    api_url=settings.groq_api_url,
                )
            )
    return providers
