"""
LLM provider abstraction.

配置方式（.env 文件）：

  LLM_PROVIDER=<provider>   # 必须手动指定（见下方可选值）
  LLM_MODEL=<model>         # 可选，覆盖该 provider 的默认模型

可用 provider 值：
  CLI 模式（走平台会员额度，无需 API key，需提前登录对应 CLI）：
    claude-cli   → claude CLI（claude.ai Pro/Max）
                   默认模型: sonnet（= claude-sonnet-4-6）
                   可用: opus / sonnet / haiku，或完整 model ID
    gemini-cli   → gemini CLI（Google 账号 / Gemini Advanced）
                   默认模型: gemini-2.5-flash
                   可用: gemini-3-1-pro / gemini-3-1-flash / gemini-2.5-pro 等
    codex-cli    → OpenAI Codex CLI（OpenAI 订阅）
                   默认模型: o4-mini
                   可用: o3 / o4-mini，或 API 支持的 model ID

  API key 模式（需在 .env 中填写对应 key）：
    anthropic / claude  → ANTHROPIC_API_KEY
    openai / gpt        → OPENAI_API_KEY
    gemini / google     → GEMINI_API_KEY
    deepseek            → DEEPSEEK_API_KEY
    openrouter          → OPENROUTER_API_KEY
    copilot             → GITHUB_TOKEN / GH_TOKEN / COPILOT_GITHUB_TOKEN（任一即可）
"""

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

import anthropic
from dotenv import load_dotenv
from openai import AuthenticationError as OpenAIAuthenticationError
from openai import OpenAI

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


@dataclass
class LLMResult:
    """LLM 调用结果契约。调用方通过 .text 取文本，.input_tokens/.output_tokens 取用量。"""

    text: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = ""


def _get_max_tokens(default: int = 300) -> int:
    """从 LLM_MAX_TOKENS 环境变量读取最大 token 数，不合法时使用默认值。"""
    try:
        return int(os.environ.get("LLM_MAX_TOKENS", default))
    except (ValueError, TypeError):
        return default


class LLMClient(ABC):
    @abstractmethod
    def chat(self, system_prompt: str, messages: List[Dict[str, str]]) -> LLMResult:
        pass

    def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> Generator[str, None, LLMResult]:
        result = self.chat(system_prompt, messages)
        if result.text:
            yield result.text
        return result


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key_env: str                                      # 主 key env；空字符串 = CLI 模式
    default_model: str
    kind: str                                             # "anthropic" | "openai_compatible" | "claude_cli" | "gemini_cli" | "codex_cli"
    base_url: Optional[str] = None
    default_headers: Mapping[str, str] = field(default_factory=dict)
    api_key_env_fallbacks: Tuple[str, ...] = field(default_factory=tuple)  # 备用 key env


# ── 别名表 ────────────────────────────────────────────────────────────────────

PROVIDER_ALIASES: Dict[str, str] = {
    # CLI 模式
    "claude-cli":    "claude_cli",
    "claude_cli":    "claude_cli",
    "claudecli":     "claude_cli",
    "gemini-cli":    "gemini_cli",
    "gemini_cli":    "gemini_cli",
    "geminicli":     "gemini_cli",
    "codex-cli":     "codex_cli",
    "codex_cli":     "codex_cli",
    "codexcli":      "codex_cli",
    "codex":         "codex_cli",
    # API key 模式
    "anthropic":     "anthropic",
    "claude":        "anthropic",
    "openai":        "openai",
    "gpt":           "openai",
    "gemini":        "gemini",
    "google":        "gemini",
    "deepseek":      "deepseek",
    "openrouter":    "openrouter",
    "copilot":       "copilot",
    "github-copilot":"copilot",
    "githubcopilot": "copilot",
}

# ── Provider 配置表 ───────────────────────────────────────────────────────────

PROVIDER_CONFIGS: Dict[str, ProviderConfig] = {
    # ── CLI 模式 ─────────────────────────────────────────────────────────────
    "claude_cli": ProviderConfig(
        name="claude_cli",
        api_key_env="",
        default_model="sonnet",          # 别名，等于 claude-sonnet-4-6
        kind="claude_cli",
    ),
    "gemini_cli": ProviderConfig(
        name="gemini_cli",
        api_key_env="",
        default_model="gemini-2.5-flash",
        kind="gemini_cli",
    ),
    "codex_cli": ProviderConfig(
        name="codex_cli",
        api_key_env="",
        default_model="o4-mini",
        kind="codex_cli",
    ),
    # ── API key 模式 ──────────────────────────────────────────────────────────
    "anthropic": ProviderConfig(
        name="anthropic",
        api_key_env="ANTHROPIC_API_KEY",
        default_model="claude-haiku-4-5-20251001",
        kind="anthropic",
    ),
    "openai": ProviderConfig(
        name="openai",
        api_key_env="OPENAI_API_KEY",
        default_model="gpt-4o-mini",
        kind="openai_compatible",
    ),
    "gemini": ProviderConfig(
        name="gemini",
        api_key_env="GEMINI_API_KEY",
        default_model="gemini-2.5-flash",
        kind="openai_compatible",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    ),
    "deepseek": ProviderConfig(
        name="deepseek",
        api_key_env="DEEPSEEK_API_KEY",
        default_model="deepseek-chat",
        kind="openai_compatible",
        base_url="https://api.deepseek.com",
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        api_key_env="OPENROUTER_API_KEY",
        default_model="openai/gpt-4o-mini",
        kind="openai_compatible",
        base_url="https://openrouter.ai/api/v1",
    ),
    "copilot": ProviderConfig(
        name="copilot",
        api_key_env="GITHUB_TOKEN",                      # 主
        api_key_env_fallbacks=("GH_TOKEN", "COPILOT_GITHUB_TOKEN"),  # 备用
        default_model="gpt-4.1",
        kind="openai_compatible",
        base_url="https://api.githubcopilot.com",
        default_headers={
            "editor-version": "vscode/1.99.0",
            "editor-plugin-version": "copilot/1.0.0",
            "openai-intent": "conversation-panel",
        },
    ),
}

_CLI_KINDS = {"claude_cli", "gemini_cli", "codex_cli"}

# ── 内部工具函数 ───────────────────────────────────────────────────────────────

def _resolve_api_key(config: ProviderConfig) -> Optional[str]:
    if config.kind in _CLI_KINDS:
        return None

    # 主 key
    key = os.environ.get(config.api_key_env)
    if key:
        return key

    # 备用 key（copilot 等多名称 token）
    for fallback in config.api_key_env_fallbacks:
        key = os.environ.get(fallback)
        if key:
            return key

    # 通用 key
    key = os.environ.get("LLM_API_KEY") or os.environ.get("API_KEY")
    if key:
        return key

    # 只有一个 provider 配置了 key 时自动使用
    all_keys = [
        os.environ.get(c.api_key_env)
        for c in PROVIDER_CONFIGS.values()
        if c.api_key_env and os.environ.get(c.api_key_env)
    ]
    if len(all_keys) == 1:
        return all_keys[0]

    return None


def _normalize_provider(name: str) -> str:
    normalized = PROVIDER_ALIASES.get(name.lower())
    if not normalized:
        supported = ", ".join(sorted(PROVIDER_ALIASES))
        raise EnvironmentError(f"不支持的 LLM_PROVIDER: {name!r}。\n可选值: {supported}")
    return normalized


def _resolve_provider_name(explicit: Optional[str] = None) -> str:
    raw = explicit or os.environ.get("LLM_PROVIDER")
    if raw:
        return _normalize_provider(raw)

    configured = [
        name
        for name, config in PROVIDER_CONFIGS.items()
        if config.api_key_env and os.environ.get(config.api_key_env)
    ]
    if len(configured) == 1:
        return configured[0]
    if len(configured) > 1:
        raise EnvironmentError(
            f"检测到多个可用 API key，请在 .env 中设置 LLM_PROVIDER 明确指定。\n"
            f"当前可用: {', '.join(configured)}"
        )
    raise EnvironmentError(
        "未检测到可用的 LLM 配置。\n"
        "请在 .env 中设置 LLM_PROVIDER，可选值见 llm.py 顶部注释。"
    )


# ── CLI 基类 ──────────────────────────────────────────────────────────────────

class _BaseCLIClient(LLMClient):
    CLI_CMD: str = ""
    TIMEOUT: int = 120

    def __init__(self, config: ProviderConfig, model: Optional[str] = None) -> None:
        if not shutil.which(self.CLI_CMD):
            raise EnvironmentError(
                f"未找到 {self.CLI_CMD!r} 命令。{self._install_hint()}"
            )
        self.provider = config.name
        self.model = model or os.environ.get("LLM_MODEL") or config.default_model

    def _install_hint(self) -> str:
        return ""

    def _run(
        self,
        cmd: List[str],
        stdin_text: Optional[str] = None,
    ) -> str:
        try:
            result = subprocess.run(
                cmd,
                input=stdin_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"{self.CLI_CMD} 响应超时（{self.TIMEOUT}s）") from exc
        except FileNotFoundError as exc:
            raise RuntimeError(f"{self.CLI_CMD!r} 不可用，请检查 PATH") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if any(kw in stderr.lower() for kw in ("not logged in", "auth", "login", "sign in", "unauthenticated")):
                raise RuntimeError(f"{self.CLI_CMD} 未登录。{self._login_hint()}")
            raise RuntimeError(f"{self.CLI_CMD} 返回错误 (exit {result.returncode}): {stderr}")

        return result.stdout.strip()

    def _login_hint(self) -> str:
        return ""

    def chat(self, system_prompt: str, messages: List[Dict[str, str]]) -> LLMResult:
        text = self._get_reply_text(system_prompt, messages)
        return LLMResult(text=text, model=self.model, provider=self.provider)

    def _get_reply_text(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        raise NotImplementedError


# ── CLI 实现 ──────────────────────────────────────────────────────────────────

class ClaudeCodeCLIClient(_BaseCLIClient):
    """claude CLI — 消耗 claude.ai Pro/Max 会员额度。

    非交互模式：claude -p "<message>" --model <model> --system-prompt "<system>"
    模型别名：opus / sonnet / haiku（claude-opus-4-7 / claude-sonnet-4-6 / claude-haiku-4-5）
    """

    CLI_CMD = "claude"

    def _install_hint(self) -> str:
        return "请安装 Claude Code：npm install -g @anthropic-ai/claude-code"

    def _login_hint(self) -> str:
        return "请先运行 `claude` 完成登录。"

    def _get_reply_text(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        user_text = "\n\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in messages
        )
        cmd = [
            "claude", "-p", user_text,
            "--model", self.model,
            "--system-prompt", system_prompt,
        ]
        return self._run(cmd)


class GeminiCLIClient(_BaseCLIClient):
    """gemini CLI — 消耗 Google 账号 / Gemini Advanced 会员额度。

    非交互模式：通过 stdin 传入 prompt（gemini CLI 无 --prompt 标志）
    模型示例：gemini-2.5-flash / gemini-2.5-pro / gemini-3-1-flash / gemini-3-1-pro
    """

    CLI_CMD = "gemini"

    def _install_hint(self) -> str:
        return "请安装 Gemini CLI：npm install -g @google/gemini-cli"

    def _login_hint(self) -> str:
        return "请先运行 `gemini` 完成 Google 账号授权。"

    def _get_reply_text(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        user_text = "\n\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in messages
        )
        combined = f"{system_prompt}\n\n{user_text}"
        cmd = ["gemini", "--model", self.model]
        return self._run(cmd, stdin_text=combined)


class CodexCLIClient(_BaseCLIClient):
    """OpenAI Codex CLI — 消耗 OpenAI 订阅额度。

    非交互模式：codex -m <model> exec "<prompt>"
    模型示例：gpt-5.4 / gpt-5.4-mini / gpt-5.3-codex
    注意：Codex CLI 主要面向编程任务（可读写文件、执行命令），
          此处仅以 exec 模式做单次对话，system prompt 拼入任务文本。
    """

    CLI_CMD = "codex"

    def _install_hint(self) -> str:
        return "请安装 OpenAI Codex CLI：npm install -g @openai/codex"

    def _login_hint(self) -> str:
        return "请先运行 `codex login` 或在 .env 中设置 OPENAI_API_KEY。"

    def _get_reply_text(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        user_text = "\n\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in messages
        )
        task = f"[System]\n{system_prompt}\n\n[Conversation]\n{user_text}"
        cmd = ["codex", "-m", self.model, "exec", task]
        return self._run(cmd)


# ── API key 实现 ───────────────────────────────────────────────────────────────

class AnthropicClient(LLMClient):
    MAX_TOKENS = 1024

    def __init__(self, config: ProviderConfig, model: Optional[str] = None) -> None:
        api_key = _resolve_api_key(config)
        if not api_key:
            raise EnvironmentError(f"{config.api_key_env} 未设置。请检查 .env 文件。")
        self.provider = config.name
        self.model = model or os.environ.get("LLM_MODEL") or config.default_model
        self._client = anthropic.Anthropic(api_key=api_key)

    def chat(self, system_prompt: str, messages: List[Dict[str, str]]) -> LLMResult:
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=_get_max_tokens(),
                system=system_prompt,
                messages=messages,
            )
        except anthropic.AuthenticationError as exc:
            raise RuntimeError("Anthropic 鉴权失败：ANTHROPIC_API_KEY 无效。") from exc
        except anthropic.RateLimitError as exc:
            raise RuntimeError("Anthropic API 触发速率限制，请稍后重试。") from exc
        except Exception as exc:
            raise RuntimeError(f"Anthropic API 调用失败: {exc}") from exc

        text = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
        return LLMResult(
            text=text,
            model=self.model,
            provider=self.provider,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=response.stop_reason or "",
        )

    def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> Generator[str, None, LLMResult]:
        chunks: List[str] = []
        try:
            with self._client.messages.stream(
                model=self.model,
                max_tokens=_get_max_tokens(),
                system=system_prompt,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    if not text:
                        continue
                    chunks.append(text)
                    yield text
                final_message = stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise RuntimeError("Anthropic 鉴权失败：ANTHROPIC_API_KEY 无效。") from exc
        except anthropic.RateLimitError as exc:
            raise RuntimeError("Anthropic API 触发速率限制，请稍后重试。") from exc
        except Exception as exc:
            raise RuntimeError(f"Anthropic API 调用失败: {exc}") from exc

        return LLMResult(
            text="".join(chunks).strip(),
            model=self.model,
            provider=self.provider,
            input_tokens=final_message.usage.input_tokens,
            output_tokens=final_message.usage.output_tokens,
            finish_reason=final_message.stop_reason or "",
        )


class OpenAICompatibleClient(LLMClient):
    MAX_TOKENS = 1024

    def __init__(self, config: ProviderConfig, model: Optional[str] = None) -> None:
        api_key = _resolve_api_key(config)
        if not api_key:
            all_envs = [config.api_key_env, *config.api_key_env_fallbacks]
            raise EnvironmentError(
                f"未找到 {config.name} 的 API key。\n"
                f"请在 .env 中设置以下任一变量: {', '.join(all_envs)}"
            )

        headers = dict(config.default_headers)
        if config.name == "openrouter":
            if referer := os.environ.get("OPENROUTER_HTTP_REFERER"):
                headers["HTTP-Referer"] = referer
            if title := os.environ.get("OPENROUTER_APP_TITLE"):
                headers["X-Title"] = title

        self.provider = config.name
        self.model = model or os.environ.get("LLM_MODEL") or config.default_model

        client_kwargs: Dict = {"api_key": api_key}
        if config.base_url:
            client_kwargs["base_url"] = config.base_url
        if headers:
            client_kwargs["default_headers"] = headers
        self._client = OpenAI(**client_kwargs)

    def chat(self, system_prompt: str, messages: List[Dict[str, str]]) -> LLMResult:
        request_messages = [{"role": "system", "content": system_prompt}, *messages]
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=request_messages,
                max_completion_tokens=_get_max_tokens(),
            )
        except OpenAIAuthenticationError as exc:
            config = PROVIDER_CONFIGS[self.provider]
            all_envs = [config.api_key_env, *config.api_key_env_fallbacks]
            raise RuntimeError(
                f"{self.provider} 鉴权失败：{' / '.join(all_envs)} 无效。"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"{self.provider} API 调用失败: {exc}") from exc

        content = response.choices[0].message.content
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            text = "".join(getattr(item, "text", "") for item in content).strip()
        else:
            text = ""
        usage = response.usage
        return LLMResult(
            text=text,
            model=self.model,
            provider=self.provider,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            finish_reason=response.choices[0].finish_reason or "",
        )

    def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> Generator[str, None, LLMResult]:
        request_messages = [{"role": "system", "content": system_prompt}, *messages]
        chunks: List[str] = []
        input_tokens = 0
        output_tokens = 0
        finish_reason = ""
        try:
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=request_messages,
                max_completion_tokens=_get_max_tokens(),
                stream=True,
                stream_options={"include_usage": True},
            )
            for chunk in stream:
                if getattr(chunk, "usage", None):
                    input_tokens = chunk.usage.prompt_tokens or input_tokens
                    output_tokens = chunk.usage.completion_tokens or output_tokens

                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue

                choice = choices[0]
                finish_reason = getattr(choice, "finish_reason", None) or finish_reason
                delta = getattr(choice, "delta", None)
                content = getattr(delta, "content", None) if delta is not None else None
                if isinstance(content, str) and content:
                    chunks.append(content)
                    yield content
                elif isinstance(content, list):
                    text = "".join(getattr(item, "text", "") for item in content)
                    if text:
                        chunks.append(text)
                        yield text
        except OpenAIAuthenticationError as exc:
            config = PROVIDER_CONFIGS[self.provider]
            all_envs = [config.api_key_env, *config.api_key_env_fallbacks]
            raise RuntimeError(
                f"{self.provider} 鉴权失败：{' / '.join(all_envs)} 无效。"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"{self.provider} API 调用失败: {exc}") from exc

        return LLMResult(
            text="".join(chunks).strip(),
            model=self.model,
            provider=self.provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=finish_reason,
        )


# ── 工厂函数 ──────────────────────────────────────────────────────────────────

_CLI_CLIENT_MAP = {
    "claude_cli": ClaudeCodeCLIClient,
    "gemini_cli": GeminiCLIClient,
    "codex_cli":  CodexCLIClient,
}


def create_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMClient:
    resolved = _resolve_provider_name(provider)
    config = PROVIDER_CONFIGS[resolved]

    if config.kind in _CLI_KINDS:
        return _CLI_CLIENT_MAP[resolved](config=config, model=model)
    if config.kind == "anthropic":
        return AnthropicClient(config=config, model=model)
    return OpenAICompatibleClient(config=config, model=model)
