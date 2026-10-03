from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderConfig:
    """Student TODO: define the provider configuration shared by the agents.

    Required providers for this lab:
    - openai
    - custom (OpenAI-compatible base URL)
    - gemini
    - anthropic
    - ollama
    - openrouter
    """

    provider: str
    model_name: str
    temperature: float
    api_key: str | None = None
    base_url: str | None = None


def normalize_provider(value: str) -> str:
    """Student TODO: map aliases like `anthorpic` -> `anthropic`."""
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "open-ai": "openai",
        "openai": "openai",
        "custom": "custom",
        "openai-compatible": "custom",
        "gemini": "gemini",
        "google": "gemini",
        "anthropic": "anthropic",
        "anthorpic": "anthropic",  # common transposition in setup files
        "claude": "anthropic",
        "ollama": "ollama",
        "openrouter": "openrouter",
        "open-router": "openrouter",
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted(set(aliases.values())))
        raise ValueError(f"Unsupported provider {value!r}. Expected one of: {supported}.") from exc


def build_chat_model(config: ProviderConfig):
    """Student TODO: instantiate the real chat model for the selected provider.

    Pseudocode:
    - `openai` -> `ChatOpenAI`
    - `custom` -> `ChatOpenAI` with `base_url`
    - `gemini` -> `ChatGoogleGenerativeAI`
    - `anthropic` -> `ChatAnthropic`
    - `ollama` -> `ChatOllama`
    - `openrouter` -> `ChatOpenRouter`
    """

    provider = normalize_provider(config.provider)
    common = {"model": config.model_name, "temperature": config.temperature}

    if provider in {"openai", "custom"}:
        from langchain_openai import ChatOpenAI

        kwargs = dict(common)
        if config.api_key:
            kwargs["api_key"] = config.api_key
        if provider == "custom":
            if not config.base_url:
                raise ValueError("CUSTOM_BASE_URL is required when LLM_PROVIDER=custom.")
            kwargs["base_url"] = config.base_url
        return ChatOpenAI(**kwargs)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        kwargs = dict(common)
        if config.api_key:
            kwargs["google_api_key"] = config.api_key
        return ChatGoogleGenerativeAI(**kwargs)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        kwargs = dict(common)
        if config.api_key:
            kwargs["api_key"] = config.api_key
        return ChatAnthropic(**kwargs)
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        kwargs = dict(common)
        if config.base_url:
            kwargs["base_url"] = config.base_url
        return ChatOllama(**kwargs)
    if provider == "openrouter":
        from langchain_openrouter import ChatOpenRouter

        kwargs = dict(common)
        if config.api_key:
            kwargs["api_key"] = config.api_key
        if config.base_url:
            kwargs["base_url"] = config.base_url
        return ChatOpenRouter(**kwargs)
    # normalize_provider currently makes this unreachable; retain a clear
    # failure if a future provider is added incompletely.
    raise ValueError(f"No model builder for provider {provider!r}.")
