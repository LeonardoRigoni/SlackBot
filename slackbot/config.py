from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    slack_bot_token: str
    slack_app_token: str
    llm_provider: str
    llm_model: str
    ollama_base_url: str
    openai_api_key: str
    anthropic_api_key: str
    gemini_api_key: str
    rules_path: str
    state_db_path: str
    bot_timezone: str
    allow_llm_generated_questions: bool
    confidence_threshold: float
    auto_route_confidence_threshold: float
    channel_menu: str


def load_settings() -> Settings:
    load_dotenv()

    return Settings(
        slack_bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
        slack_app_token=os.getenv("SLACK_APP_TOKEN", ""),
        llm_provider=os.getenv("LLM_PROVIDER", "ollama").strip().lower(),
        llm_model=os.getenv("LLM_MODEL", os.getenv("OLLAMA_MODEL", "qwen3.6-64k:27b")),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        rules_path=os.getenv("RULES_PATH", "rules/channels.md"),
        state_db_path=os.getenv("STATE_DB_PATH", "slackbot_state.db"),
        bot_timezone=os.getenv("BOT_TIMEZONE", "America/Sao_Paulo"),
        allow_llm_generated_questions=_bool_env("ALLOW_LLM_GENERATED_QUESTIONS", False),
        confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.65")),
        auto_route_confidence_threshold=float(os.getenv("AUTO_ROUTE_CONFIDENCE_THRESHOLD", "0.85")),
        channel_menu=os.getenv("SLACK_CHANNEL_MENU", ""),
    )


def validate_settings(settings: Settings) -> None:
    missing = []
    if not settings.slack_bot_token:
        missing.append("SLACK_BOT_TOKEN")
    if not settings.slack_app_token:
        missing.append("SLACK_APP_TOKEN")
    if not settings.channel_menu:
        missing.append("SLACK_CHANNEL_MENU")
    if settings.llm_provider not in {"ollama", "openai", "anthropic", "gemini"}:
        raise RuntimeError("LLM_PROVIDER must be one of: ollama, openai, anthropic, gemini")
    if settings.llm_provider == "openai" and not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        missing.append("ANTHROPIC_API_KEY")
    if settings.llm_provider == "gemini" and not settings.gemini_api_key:
        missing.append("GEMINI_API_KEY")
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))


def channel_env_name(channel_name: str) -> str:
    suffix = channel_name.removeprefix("chamados-").upper().replace("-", "_")
    return f"SLACK_CHANNEL_{suffix}"


def destination_channel_refs(channel_names: list[str]) -> dict[str, str]:
    missing = []
    channel_refs = {}
    for channel_name in channel_names:
        env_name = channel_env_name(channel_name)
        channel_ref = os.getenv(env_name, "")
        if not channel_ref:
            missing.append(env_name)
        channel_refs[channel_name] = channel_ref

    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))

    return channel_refs
