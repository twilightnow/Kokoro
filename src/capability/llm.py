import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import anthropic


class LLMClient(ABC):
    @abstractmethod
    def chat(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        pass


class ClaudeClient(LLMClient):
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"
    MAX_TOKENS = 1024

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY 未设置。"
                "请检查 .env 文件或环境变量。"
            )
        self._client = anthropic.Anthropic(api_key=resolved_key)
        self.model = model

    def chat(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
