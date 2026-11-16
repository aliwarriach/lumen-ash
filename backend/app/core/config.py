import os
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Tests must never read the developer's real backend/.env: it holds live API keys, and a test
# that forgot to fake a provider would spend real quota. Under ENVIRONMENT=test only real
# environment variables count.
_ENV_FILE = None if os.environ.get("ENVIRONMENT") == "test" else ".env"


class Settings(BaseSettings):
    """All configuration comes from environment variables (or backend/.env locally).

    Every variable is documented in backend/.env.example.
    """

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    environment: Literal["local", "test", "production"] = "local"

    # Supabase project URL, e.g. https://abcd1234.supabase.co
    supabase_url: str
    # Postgres URL using the psycopg driver: postgresql+psycopg://...
    # Use Supabase's *session pooler* string: the direct connection is IPv6-only on the free plan.
    database_url: str

    # AI providers. Optional: the app runs without them.
    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    # A second Groq key, tried when the first is rate limited or stops working.
    groq_backup_api_key: SecretStr | None = None
    # Model names live here, never in code: providers rename and retire models often
    # (llama-3.1-8b-instant, the first default, was retired within the year). After changing one,
    # run `python -m app.ai.evaluate` to see how it does on German.
    gemini_model: str = "gemini-2.5-flash-lite"
    groq_model: str = "openai/gpt-oss-120b"
    # Groq's current models think before they answer. "low" keeps that short. Set it to an empty
    # value for a model that has no reasoning setting (it would reject the option).
    groq_reasoning_effort: str = "low"
    # Where each provider's API lives. Only change these to go through a proxy, or to point Groq's
    # (OpenAI-compatible) client at another compatible service.
    gemini_api_url: str = "https://generativelanguage.googleapis.com/v1beta"
    groq_api_url: str = "https://api.groq.com/openai/v1"
    # Which providers to try, in order, comma separated. Switching provider is a config change.
    # Groq first: it is the one verified against the live service.
    ai_provider_order: str = "groq,groq_backup,gemini"
    ai_request_timeout_seconds: float = 20.0

    # Per-user daily budget. Days are UTC dates, so a client can't reset its own limit.
    ai_user_daily_requests: int = 40
    ai_user_daily_tokens: int = 60_000
    # Overrides for the per-feature daily caps in app/ai/prompts.py, e.g. {"sentence_coach": 10}
    ai_feature_daily_caps: dict[str, int] = {}
    # Short-burst throttle: AI requests per user per minute.
    ai_burst_per_minute: int = 6
    # Global daily ceilings per provider, set to about 80% of its published free limit.
    # Leave a token ceiling unset if the provider has no daily token limit.
    gemini_daily_request_ceiling: int = 400
    gemini_daily_token_ceiling: int | None = None
    # Groq allows 1,000 requests a day per key for openai/gpt-oss-120b (read from its response
    # headers, November 2026). The backup key has its own count and uses the same ceilings.
    groq_daily_request_ceiling: int = 800
    groq_daily_token_ceiling: int | None = 160_000
    # Extra names (comma separated) to strip from text before it is sent to a provider.
    ai_redact_names: str = ""

    # LanguageTool finds the errors in the sentence coach. The public API is free but limited
    # (about 20 requests a minute per IP). Set to an empty value to switch it off.
    languagetool_url: str = "https://api.languagetool.org/v2/check"
    languagetool_timeout_seconds: float = 10.0
    languagetool_per_minute: int = 15

    # Community forum (the shared group chat).
    # Messages one person may post per minute: stops a stuck phone or a flood reaching everyone.
    community_messages_per_minute: int = 20
    # Emails (comma separated) of the people who may delete anyone's message.
    community_moderator_emails: str = ""
    # Phones that may be connected to the live chat at once. 30 people need 30.
    community_max_connections: int = 200

    sentry_dsn: str | None = None

    @field_validator("supabase_url")
    @classmethod
    def _supabase_url_is_a_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise ValueError(
                "SUPABASE_URL must be your Supabase project URL, such as "
                "https://abcd1234.supabase.co (Supabase dashboard -> Project Settings -> API)."
            )
        return v

    @field_validator("database_url")
    @classmethod
    def _database_url_uses_psycopg(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("postgresql+psycopg://"):
            raise ValueError(
                "DATABASE_URL must start with postgresql+psycopg:// . Copy Supabase's "
                "'Session pooler' connection string and change its postgresql:// prefix."
            )
        return v

    @field_validator("groq_reasoning_effort")
    @classmethod
    def _known_effort(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in {"", "low", "medium", "high"}:
            raise ValueError("GROQ_REASONING_EFFORT must be low, medium, high or empty.")
        return v

    @property
    def ai_providers(self) -> list[str]:
        return [name.strip().lower() for name in self.ai_provider_order.split(",") if name.strip()]

    @property
    def redact_names(self) -> list[str]:
        return [name.strip() for name in self.ai_redact_names.split(",") if name.strip()]

    @property
    def community_moderators(self) -> frozenset[str]:
        return frozenset(
            e.strip().lower() for e in self.community_moderator_emails.split(",") if e.strip()
        )

    @property
    def supabase_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from the environment
