"""
tests/test_openai_provider.py — Unit tests for llm/openai_provider.py
"""

import unittest
from unittest.mock import patch, MagicMock


class TestOpenAIProvider(unittest.TestCase):

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def test_provider_raises_import_error_when_openai_missing(self):
        with patch.dict("sys.modules", {"openai": None}), \
             patch("config.OPENAI_API_KEY", "key"), \
             patch("config.OPENAI_MODEL", "gpt-4o-mini"):
            import importlib
            import llm.openai_provider as mod
            importlib.reload(mod)
            with self.assertRaises(ImportError):
                mod.OpenAIProvider()

    def test_provider_raises_value_error_when_api_key_missing(self):
        mock_openai_module = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai_module}), \
             patch("config.OPENAI_API_KEY", ""), \
             patch("config.OPENAI_MODEL", "gpt-4o-mini"):
            import importlib
            import llm.openai_provider as mod
            importlib.reload(mod)
            with self.assertRaises(ValueError) as ctx:
                mod.OpenAIProvider()
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))

    # ------------------------------------------------------------------
    # Successful call
    # ------------------------------------------------------------------

    def test_generate_script_returns_content_text(self):
        mock_openai_cls = MagicMock()
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "Host1: Hello!\nHost2: Hi!"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai_cls)}), \
             patch("config.OPENAI_API_KEY", "sk-test"), \
             patch("config.OPENAI_MODEL", "gpt-4o-mini"):
            import importlib
            import llm.openai_provider as mod
            importlib.reload(mod)
            provider = mod.OpenAIProvider()
            provider._client = mock_client
            result = provider.generate_script(markdown="# AI", language="en")

        self.assertEqual(result, "Host1: Hello!\nHost2: Hi!")

    def test_generate_script_sends_user_message(self):
        mock_openai_cls = MagicMock()
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "Host1: ok\nHost2: great"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai_cls)}), \
             patch("config.OPENAI_API_KEY", "sk-test"), \
             patch("config.OPENAI_MODEL", "gpt-4o-mini"):
            import importlib
            import llm.openai_provider as mod
            importlib.reload(mod)
            provider = mod.OpenAIProvider()
            provider._client = mock_client
            provider.generate_script(markdown="content", language="pt-BR")

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs[1]["messages"]
        self.assertEqual(messages[0]["role"], "user")
        self.assertIn("content", messages[0]["content"])

    def test_generate_script_uses_configured_model(self):
        mock_openai_cls = MagicMock()
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "Host1: ok\nHost2: great"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai_cls)}), \
             patch("config.OPENAI_API_KEY", "sk-test"), \
             patch("config.OPENAI_MODEL", "gpt-4o"):
            import importlib
            import llm.openai_provider as mod
            importlib.reload(mod)
            provider = mod.OpenAIProvider()
            provider._client = mock_client
            provider.generate_script(markdown="text", language="en")

        call_kwargs = mock_client.chat.completions.create.call_args
        self.assertEqual(call_kwargs[1]["model"], "gpt-4o")

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_api_error_raises_runtime_error(self):
        mock_openai_cls = MagicMock()
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API failure")

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai_cls)}), \
             patch("config.OPENAI_API_KEY", "sk-test"), \
             patch("config.OPENAI_MODEL", "gpt-4o-mini"):
            import importlib
            import llm.openai_provider as mod
            importlib.reload(mod)
            provider = mod.OpenAIProvider()
            provider._client = mock_client
            with self.assertRaises(RuntimeError) as ctx:
                provider.generate_script(markdown="text", language="en")

        self.assertIn("OpenAI API error", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
