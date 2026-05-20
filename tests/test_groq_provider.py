"""
tests/test_groq_provider.py — Unit tests for llm/groq_provider.py
"""

import unittest
from unittest.mock import patch, MagicMock


class TestGroqProvider(unittest.TestCase):

    def _make_provider(self, api_key="gsk_test", model="llama3-8b-8192"):
        """Instantiate GroqProvider with mocked groq SDK and config."""
        mock_groq_cls = MagicMock()
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client

        with patch.dict("sys.modules", {"groq": MagicMock(Groq=mock_groq_cls)}), \
             patch("config.GROQ_API_KEY", api_key), \
             patch("config.GROQ_MODEL", model):
            from llm.groq_provider import GroqProvider
            import importlib
            import llm.groq_provider as mod
            importlib.reload(mod)
            provider = mod.GroqProvider()
        # Attach the mock client for assertions
        provider._client = mock_client
        return provider, mock_client

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def test_provider_raises_import_error_when_groq_missing(self):
        with patch.dict("sys.modules", {"groq": None}), \
             patch("config.GROQ_API_KEY", "key"), \
             patch("config.GROQ_MODEL", "model"):
            import importlib
            import llm.groq_provider as mod
            importlib.reload(mod)
            with self.assertRaises(ImportError):
                mod.GroqProvider()

    def test_provider_raises_value_error_when_api_key_missing(self):
        mock_groq_module = MagicMock()
        with patch.dict("sys.modules", {"groq": mock_groq_module}), \
             patch("config.GROQ_API_KEY", ""), \
             patch("config.GROQ_MODEL", "llama3-8b-8192"):
            import importlib
            import llm.groq_provider as mod
            importlib.reload(mod)
            with self.assertRaises(ValueError) as ctx:
                mod.GroqProvider()
        self.assertIn("GROQ_API_KEY", str(ctx.exception))

    # ------------------------------------------------------------------
    # Successful call
    # ------------------------------------------------------------------

    def test_generate_script_returns_content_text(self):
        mock_groq_cls = MagicMock()
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "Host1: Hello!\nHost2: Hi!"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        with patch.dict("sys.modules", {"groq": MagicMock(Groq=mock_groq_cls)}), \
             patch("config.GROQ_API_KEY", "gsk_test"), \
             patch("config.GROQ_MODEL", "llama3-8b-8192"):
            import importlib
            import llm.groq_provider as mod
            importlib.reload(mod)
            provider = mod.GroqProvider()
            provider._client = mock_client
            result = provider.generate_script(markdown="# AI", language="en")

        self.assertEqual(result, "Host1: Hello!\nHost2: Hi!")

    def test_generate_script_sends_user_message(self):
        mock_groq_cls = MagicMock()
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "Host1: ok\nHost2: great"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        with patch.dict("sys.modules", {"groq": MagicMock(Groq=mock_groq_cls)}), \
             patch("config.GROQ_API_KEY", "gsk_test"), \
             patch("config.GROQ_MODEL", "llama3-8b-8192"):
            import importlib
            import llm.groq_provider as mod
            importlib.reload(mod)
            provider = mod.GroqProvider()
            provider._client = mock_client
            provider.generate_script(markdown="content", language="pt-BR")

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs[1]["messages"]
        self.assertEqual(messages[0]["role"], "user")
        self.assertIn("content", messages[0]["content"])

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_api_error_raises_runtime_error(self):
        mock_groq_cls = MagicMock()
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API failure")

        with patch.dict("sys.modules", {"groq": MagicMock(Groq=mock_groq_cls)}), \
             patch("config.GROQ_API_KEY", "gsk_test"), \
             patch("config.GROQ_MODEL", "llama3-8b-8192"):
            import importlib
            import llm.groq_provider as mod
            importlib.reload(mod)
            provider = mod.GroqProvider()
            provider._client = mock_client
            with self.assertRaises(RuntimeError) as ctx:
                provider.generate_script(markdown="text", language="en")

        self.assertIn("Groq API error", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
