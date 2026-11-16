import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.ai.errors import (
    ProviderBadOutput,
    ProviderMisconfigured,
    ProviderRateLimited,
    ProviderUnavailable,
)
from app.ai.providers import (
    REASONING_HEADROOM_TOKENS,
    AiRequest,
    GeminiProvider,
    GroqProvider,
    build_providers,
)
from app.core.config import Settings

REQUEST = AiRequest(system="Be brief.", user="Sentence: Ich habe ein Tisch.", max_output_tokens=300)
ANSWER = {"explanation": "Use einen.", "practice": ["Ich sehe einen Hund."]}

Handler = Callable[[httpx.Request], httpx.Response]


def client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def gemini_body(text: str | None = None, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": text if text is not None else json.dumps(ANSWER)}]},
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 40,
            "candidatesTokenCount": 25,
            "thoughtsTokenCount": 5,
        },
    }
    return {**body, **overrides}


def groq_body(content: str | None = None, finish: str = "stop") -> dict[str, Any]:
    return {
        "choices": [
            {
                "finish_reason": finish,
                "message": {"content": content if content is not None else json.dumps(ANSWER)},
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 30},
    }


async def test_gemini_sends_the_key_in_a_header_and_reads_provider_token_counts() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=gemini_body())

    provider = GeminiProvider(client(handler), "secret-key", "gemini-test")
    result = await provider.generate(REQUEST)

    assert result.data == ANSWER
    assert (result.input_tokens, result.output_tokens) == (40, 30)  # thinking tokens included
    assert (result.provider, result.model) == ("gemini", "gemini-test")
    request = seen[0]
    assert "secret-key" not in str(request.url)
    assert request.headers["x-goog-api-key"] == "secret-key"
    assert request.url.path.endswith("/models/gemini-test:generateContent")
    body = json.loads(request.content)
    assert body["generationConfig"]["maxOutputTokens"] == 300
    assert body["generationConfig"]["responseMimeType"] == "application/json"


async def test_groq_sends_a_capped_json_request_and_reads_provider_token_counts() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=groq_body())

    result = await GroqProvider(client(handler), "groq-key", "llama-test").generate(REQUEST)

    assert result.data == ANSWER
    assert (result.input_tokens, result.output_tokens) == (50, 30)
    assert seen[0].headers["authorization"] == "Bearer groq-key"
    body = json.loads(seen[0].content)
    assert body["model"] == "llama-test"
    assert body["max_completion_tokens"] == 300
    assert body["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


@pytest.mark.parametrize("make", [GeminiProvider, GroqProvider])
async def test_a_429_is_a_rate_limit_and_keeps_retry_after(make: type[GeminiProvider]) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "42"}, json={"error": "quota"})

    with pytest.raises(ProviderRateLimited) as info:
        await make(client(handler), "k", "m").generate(REQUEST)
    assert info.value.retry_after_seconds == 42


@pytest.mark.parametrize("make", [GeminiProvider, GroqProvider])
@pytest.mark.parametrize("status", [500, 503, 401, 403, 404])
async def test_server_errors_and_bad_keys_are_unavailable(
    make: type[GeminiProvider], status: int
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "nope"})

    with pytest.raises(ProviderUnavailable):
        await make(client(handler), "k", "m").generate(REQUEST)


@pytest.mark.parametrize("make", [GeminiProvider, GroqProvider])
async def test_timeouts_and_network_errors_are_unavailable(make: type[GeminiProvider]) -> None:
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    def refused(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    for handler in (timeout, refused):
        with pytest.raises(ProviderUnavailable):
            await make(client(handler), "k", "m").generate(REQUEST)


@pytest.mark.parametrize(
    "body",
    [
        gemini_body(text="not json"),
        gemini_body(text="[1, 2]"),
        gemini_body(candidates=[]),
        gemini_body(candidates=[{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]),
        gemini_body(candidates=[{"finishReason": "SAFETY"}]),
    ],
)
async def test_gemini_unusable_output_is_bad_output_with_the_tokens_it_spent(
    body: dict[str, Any],
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with pytest.raises(ProviderBadOutput) as info:
        await GeminiProvider(client(handler), "k", "m").generate(REQUEST)
    assert info.value.input_tokens == 40


@pytest.mark.parametrize(
    "body", [groq_body(content="oops"), groq_body(finish="length"), {"choices": []}]
)
async def test_groq_unusable_output_is_bad_output(body: dict[str, Any]) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with pytest.raises(ProviderBadOutput):
        await GroqProvider(client(handler), "k", "m").generate(REQUEST)


def settings(**values: Any) -> Settings:
    return Settings(
        supabase_url="https://x.supabase.co", database_url="postgresql+psycopg://x", **values
    )


def test_provider_order_and_models_come_from_config() -> None:
    http = httpx.AsyncClient()
    both = {"gemini_api_key": SecretStr("g"), "groq_api_key": SecretStr("q")}

    default = build_providers(settings(**both), http)
    assert [(p.name, p.model) for p in default] == [
        ("groq", "openai/gpt-oss-120b"),
        ("gemini", "gemini-2.5-flash-lite"),
    ]

    swapped = build_providers(
        settings(**both, ai_provider_order="groq, gemini", groq_model="other-model"), http
    )
    assert [(p.name, p.model) for p in swapped] == [
        ("groq", "other-model"),
        ("gemini", "gemini-2.5-flash-lite"),
    ]


def test_providers_without_a_key_are_left_out_and_typos_are_rejected() -> None:
    http = httpx.AsyncClient()
    only_groq = build_providers(settings(groq_api_key=SecretStr("q")), http)
    assert [p.name for p in only_groq] == ["groq"]
    assert build_providers(settings(gemini_api_key=SecretStr("")), http) == []
    with pytest.raises(ValueError, match="gemni"):
        build_providers(settings(ai_provider_order="gemni"), http)


def test_a_backup_groq_key_is_a_provider_of_its_own_after_the_first() -> None:
    http = httpx.AsyncClient()
    providers = build_providers(
        settings(groq_api_key=SecretStr("q"), groq_backup_api_key=SecretStr("b")), http
    )
    # Its own name, so its usage and daily ceiling are counted apart from the first key's.
    assert [(p.name, p.model) for p in providers] == [
        ("groq", "openai/gpt-oss-120b"),
        ("groq_backup", "openai/gpt-oss-120b"),
    ]


def test_the_real_env_file_is_never_read_under_test() -> None:
    # backend/.env holds live keys. If tests read it, a test that forgot to fake a provider would
    # call the real AI. With no key passed in and none in the environment there must be none.
    assert Settings.model_config.get("env_file") is None
    assert build_providers(settings(), httpx.AsyncClient()) == []


@pytest.mark.parametrize(
    ("field", "value", "says"),
    [
        ("supabase_url", "", "SUPABASE_URL"),
        ("supabase_url", "abcd1234.supabase.co", "SUPABASE_URL"),
        ("database_url", "postgresql://u:p@host/db", "postgresql+psycopg://"),
        ("groq_reasoning_effort", "maximum", "GROQ_REASONING_EFFORT"),
    ],
)
def test_a_wrong_setting_is_refused_at_start_up_with_what_to_fix(
    field: str, value: str, says: str
) -> None:
    values: dict[str, Any] = {
        "supabase_url": "https://x.supabase.co",
        "database_url": "postgresql+psycopg://x",
        field: value,
    }
    with pytest.raises(ValueError, match=says.replace("+", r"\+")):
        Settings(**values)


# --- what Groq is asked for ---


async def groq_request(**provider_options: Any) -> dict[str, Any]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=groq_body())

    await GroqProvider(client(handler), "k", "m", **provider_options).generate(REQUEST)
    body: dict[str, Any] = json.loads(seen[0].content)
    return body


async def test_a_reasoning_model_gets_room_to_think_and_its_thinking_is_left_out() -> None:
    body = await groq_request(reasoning_effort="low")
    assert body["reasoning_effort"] == "low"
    assert body["include_reasoning"] is False
    # Thinking is billed against the same limit: without the extra room the answer is cut off.
    assert body["max_completion_tokens"] == REQUEST.max_output_tokens + REASONING_HEADROOM_TOKENS


async def test_a_model_without_reasoning_is_not_sent_reasoning_options() -> None:
    body = await groq_request(reasoning_effort="")
    assert "reasoning_effort" not in body and "include_reasoning" not in body
    assert body["max_completion_tokens"] == REQUEST.max_output_tokens


# --- telling a broken setting, a bad answer and an outage apart ---


@pytest.mark.parametrize("status", [401, 402, 403, 404])
async def test_a_bad_key_no_credit_or_a_retired_model_is_misconfigured(status: int) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": "no", "code": "whatever"}})

    with pytest.raises(ProviderMisconfigured):
        await GroqProvider(client(handler), "k", "m").generate(REQUEST)
    with pytest.raises(ProviderMisconfigured):
        await GeminiProvider(client(handler), "k", "m").generate(REQUEST)


async def test_groq_failing_to_produce_json_is_a_bad_answer_not_an_outage() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"message": "Failed to generate JSON", "code": "json_validate_failed"}},
        )

    with pytest.raises(ProviderBadOutput):
        await GroqProvider(client(handler), "k", "m").generate(REQUEST)


async def test_another_400_or_a_server_error_is_an_ordinary_outage() -> None:
    for status in (400, 500, 503):

        def handler(_: httpx.Request, status: int = status) -> httpx.Response:
            return httpx.Response(status, text="nope")

        with pytest.raises(ProviderUnavailable) as failure:
            await GroqProvider(client(handler), "k", "m").generate(REQUEST)
        assert not isinstance(failure.value, ProviderMisconfigured)
