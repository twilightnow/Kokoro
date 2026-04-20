import os
import unittest
from unittest.mock import patch

from src.capability.llm import (
    AnthropicClient,
    OpenAICompatibleClient,
    _resolve_api_key,
    _resolve_provider_name,
    create_llm_client,
    PROVIDER_CONFIGS,
)


class LLMSelectionTests(unittest.TestCase):
    def test_resolve_provider_from_explicit_alias(self) -> None:
        self.assertEqual(_resolve_provider_name("claude"), "anthropic")
        self.assertEqual(_resolve_provider_name("google"), "gemini")

    def test_resolve_provider_from_single_configured_key(self) -> None:
        env = {"DEEPSEEK_API_KEY": "sk-deepseek"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(_resolve_provider_name(), "deepseek")

    def test_resolve_provider_requires_explicit_choice_when_multiple_keys_exist(self) -> None:
        env = {
            "DEEPSEEK_API_KEY": "sk-deepseek",
            "OPENAI_API_KEY": "sk-openai",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(EnvironmentError) as ctx:
                _resolve_provider_name()
        self.assertIn("LLM_PROVIDER", str(ctx.exception))

    def test_resolve_api_key_prefers_provider_specific_key(self) -> None:
        config = PROVIDER_CONFIGS["deepseek"]
        env = {
            "DEEPSEEK_API_KEY": "provider-specific",
            "LLM_API_KEY": "generic",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(_resolve_api_key(config), "provider-specific")

    def test_resolve_api_key_falls_back_to_generic_key(self) -> None:
        config = PROVIDER_CONFIGS["openai"]
        env = {"LLM_API_KEY": "generic"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(_resolve_api_key(config), "generic")

    @patch("src.capability.llm.anthropic.Anthropic")
    def test_create_llm_client_returns_anthropic_client(self, anthropic_ctor) -> None:
        env = {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-ant"}
        with patch.dict(os.environ, env, clear=True):
            client = create_llm_client()
        self.assertIsInstance(client, AnthropicClient)
        anthropic_ctor.assert_called_once_with(api_key="sk-ant")

    @patch("src.capability.llm.OpenAI")
    def test_create_llm_client_returns_openai_compatible_client(self, openai_ctor) -> None:
        env = {"LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "sk-deepseek"}
        with patch.dict(os.environ, env, clear=True):
            client = create_llm_client()
        self.assertIsInstance(client, OpenAICompatibleClient)
        openai_ctor.assert_called_once()
        self.assertEqual(client.provider, "deepseek")
        self.assertEqual(client.model, "deepseek-chat")

    @patch("src.capability.llm.OpenAI")
    def test_openrouter_adds_optional_headers(self, openai_ctor) -> None:
        env = {
            "LLM_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "sk-openrouter",
            "OPENROUTER_HTTP_REFERER": "https://example.com",
            "OPENROUTER_APP_TITLE": "Kokoro Test",
        }
        with patch.dict(os.environ, env, clear=True):
            create_llm_client()
        _, kwargs = openai_ctor.call_args
        self.assertEqual(kwargs["default_headers"]["HTTP-Referer"], "https://example.com")
        self.assertEqual(kwargs["default_headers"]["X-Title"], "Kokoro Test")


if __name__ == "__main__":
    unittest.main()
