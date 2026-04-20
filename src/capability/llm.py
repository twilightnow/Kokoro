import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional

import anthropic
from dotenv import load_dotenv
from openai import AuthenticationError as OpenAIAuthenticationError
from openai import OpenAI

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


class LLMClient(ABC):
    @abstractmethod
    def chat(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        pass


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key_env: str
    default_model: str
    kind: str
    base_url: Optional[str] = None
    default_headers: Mapping[str, str] = field(default_factory=dict)


PROVIDER_ALIASES = {
    "anthropic": "anthropic",
    "claude": "anthropic",
    "openai": "openai",
    "gpt": "openai",
    "deepseek": "deepseek",
    "gemini": "gemini",
    "google": "gemini",
    "openrouter": "openrouter",
}

PROVIDER_CONFIGS = {
    "anthropic": ProviderConfig(
        name="anthropic",
        api_key_env="ANTHROPIC_API_KEY",
        default_model="claude-haiku-4-5-20251001",
        kind="anthropic",
    ),
    "openai": ProviderConfig(
        name="openai",
        api_key_env="OPENAI_API_KEY",
        default_model="gpt-5-mini",
        kind="openai_compatible",
    ),
    "deepseek": ProviderConfig(
        name="deepseek",
        api_key_env="DEEPSEEK_API_KEY",
        default_model="deepseek-chat",
        kind="openai_compatible",
        base_url="https://api.deepseek.com",
    ),
    "gemini": ProviderConfig(
        name="gemini",
        api_key_env="GEMINI_API_KEY",
        default_model="gemini-2.5-flash",
        kind="openai_compatible",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        api_key_env="OPENROUTER_API_KEY",
        default_model="openai/gpt-5-mini",
        kind="openai_compatible",
        base_url="https://openrouter.ai/api/v1",
    ),
}


def _resolve_api_key(config: ProviderConfig) -> Optional[str]:
    direct_key = os.environ.get(config.api_key_env)
    if direct_key:
        return direct_key

    generic_key = os.environ.get("LLM_API_KEY") or os.environ.get("API_KEY")
    if generic_key:
        return generic_key

    configured_provider_keys = [
        os.environ.get(provider_config.api_key_env)
        for provider_config in PROVIDER_CONFIGS.values()
        if os.environ.get(provider_config.api_key_env)
    ]
    if len(configured_provider_keys) == 1:
        return configured_provider_keys[0]

    return None


def _normalize_provider_name(provider: str) -> str:
    normalized = PROVIDER_ALIASES.get(provider.lower())
    if not normalized:
        supported = ", ".join(sorted(PROVIDER_CONFIGS))
        raise EnvironmentError(
            f"不支持的 LLM_PROVIDER: {provider}。可选值: {supported}"
        )
    return normalized


def _resolve_provider_name(explicit_provider: Optional[str] = None) -> str:
    provider = explicit_provider or os.environ.get("LLM_PROVIDER")
    if provider:
        return _normalize_provider_name(provider)

    configured = [
        name
        for name, config in PROVIDER_CONFIGS.items()
        if os.environ.get(config.api_key_env)
    ]
    if len(configured) == 1:
        return configured[0]
    if len(configured) > 1:
        options = ", ".join(configured)
        raise EnvironmentError(
            "检测到多个可用的 API key。请在 .env 中设置 LLM_PROVIDER 明确选择供应商。"
            f"当前可用: {options}"
        )

    expected_keys = ", ".join(
        config.api_key_env for config in PROVIDER_CONFIGS.values()
    )
    raise EnvironmentError(
        "未检测到可用的 LLM API key。"
        f"请在 .env 中配置以下任一变量: {expected_keys}"
    )


class AnthropicClient(LLMClient):
    MAX_TOKENS = 1024

    def __init__(self, config: ProviderConfig, model: Optional[str] = None) -> None:
        api_key = _resolve_api_key(config)
        if not api_key:
            raise EnvironmentError(
                f"{config.api_key_env} 未设置。"
                "请检查 .env 文件，或设置 LLM_API_KEY / API_KEY。"
            )
        self.provider = config.name
        self.model = model or os.environ.get("LLM_MODEL") or config.default_model
        self._client = anthropic.Anthropic(api_key=api_key)

    def chat(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.MAX_TOKENS,
                system=system_prompt,
                messages=messages,
            )
        except anthropic.AuthenticationError as exc:
            raise RuntimeError(
                "Anthropic 鉴权失败：当前 ANTHROPIC_API_KEY 无效。"
                "请在 .env 中填入有效的 Anthropic Console API key。"
            ) from exc

        text_parts = [block.text for block in response.content if block.type == "text"]
        return "".join(text_parts).strip()


class OpenAICompatibleClient(LLMClient):
    MAX_TOKENS = 1024

    def __init__(self, config: ProviderConfig, model: Optional[str] = None) -> None:
        api_key = _resolve_api_key(config)
        if not api_key:
            raise EnvironmentError(
                f"{config.api_key_env} 未设置。"
                "请检查 .env 文件，或设置 LLM_API_KEY / API_KEY。"
            )

        headers = dict(config.default_headers)
        referer = os.environ.get("OPENROUTER_HTTP_REFERER")
        title = os.environ.get("OPENROUTER_APP_TITLE")
        if config.name == "openrouter":
            if referer:
                headers["HTTP-Referer"] = referer
            if title:
                headers["X-Title"] = title

        self.provider = config.name
        self.model = model or os.environ.get("LLM_MODEL") or config.default_model
        client_kwargs = {"api_key": api_key}
        if config.base_url:
            client_kwargs["base_url"] = config.base_url
        if headers:
            client_kwargs["default_headers"] = headers
        self._client = OpenAI(**client_kwargs)

    def chat(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        request_messages = [{"role": "system", "content": system_prompt}, *messages]
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=request_messages,
                max_completion_tokens=self.MAX_TOKENS,
            )
        except OpenAIAuthenticationError as exc:
            env_name = PROVIDER_CONFIGS[self.provider].api_key_env
            raise RuntimeError(
                f"{self.provider} 鉴权失败：当前 {env_name} 无效。"
                "请在 .env 中填入对应供应商的有效 API key。"
            ) from exc

        content = response.choices[0].message.content
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts = []
            for item in content:
                text_value = getattr(item, "text", None)
                if text_value:
                    text_parts.append(text_value)
            return "".join(text_parts).strip()
        return ""


def create_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMClient:
    resolved_provider = _resolve_provider_name(provider)
    config = PROVIDER_CONFIGS[resolved_provider]
    if config.kind == "anthropic":
        return AnthropicClient(config=config, model=model)
    return OpenAICompatibleClient(config=config, model=model)
