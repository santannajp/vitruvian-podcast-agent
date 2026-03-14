"""
tests/test_ollama_provider.py — Unit tests for llm/ollama_provider.py
"""

import unittest
from unittest.mock import patch, MagicMock

import requests


class TestOllamaProvider(unittest.TestCase):

    # Patch config before importing provider so module-level attributes load correctly
    def _make_provider(self):
        """Import and instantiate OllamaProvider with patched config."""
        with patch.dict("sys.modules", {}):
            import importlib
            # Patch config values directly
            with patch("config.OLLAMA_BASE_URL", "http://localhost:11434"), \
                 patch("config.OLLAMA_MODEL", "llama3"):
                from llm.ollama_provider import OllamaProvider
                return OllamaProvider()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def test_provider_initializes_with_config(self):
        with patch("config.OLLAMA_BASE_URL", "http://localhost:11434"), \
             patch("config.OLLAMA_MODEL", "llama3"):
            from llm.ollama_provider import OllamaProvider
            provider = OllamaProvider()
        self.assertEqual(provider.base_url, "http://localhost:11434")
        self.assertEqual(provider.model, "llama3")
        self.assertEqual(provider.model, "llama3")

    # ------------------------------------------------------------------
    # Successful call
    # ------------------------------------------------------------------

    def test_generate_script_returns_response_text(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Host1: Hello!\nHost2: Hi!"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("config.OLLAMA_BASE_URL", "http://localhost:11434"), \
             patch("config.OLLAMA_MODEL", "llama3"), \
             patch("requests.post", return_value=mock_response) as mock_post:
            from llm.ollama_provider import OllamaProvider
            provider = OllamaProvider()
            result = provider.generate_script(markdown="# AI", language="en")

        self.assertEqual(result, "Host1: Hello!\nHost2: Hi!")

    def test_generate_script_calls_correct_url(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Host1: text\nHost2: reply"}
        mock_response.raise_for_status = MagicMock()

        with patch("config.OLLAMA_BASE_URL", "http://myhost:11434"), \
             patch("config.OLLAMA_MODEL", "mistral"), \
             patch("requests.post", return_value=mock_response) as mock_post:
            from llm.ollama_provider import OllamaProvider
            provider = OllamaProvider()
            provider.generate_script(markdown="text", language="en")

        call_url = mock_post.call_args[0][0]
        self.assertIn("/api/generate", call_url)

    def test_generate_script_sends_correct_payload(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Host1: ok\nHost2: great"}
        mock_response.raise_for_status = MagicMock()

        with patch("config.OLLAMA_BASE_URL", "http://localhost:11434"), \
             patch("config.OLLAMA_MODEL", "llama3"), \
             patch("requests.post", return_value=mock_response) as mock_post:
            from llm.ollama_provider import OllamaProvider
            provider = OllamaProvider()
            provider.generate_script(markdown="content", language="pt-BR")

        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["model"], "llama3")
        self.assertIn("content", payload["prompt"])
        self.assertFalse(payload["stream"])

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_connection_error_raises_runtime_error(self):
        with patch("config.OLLAMA_BASE_URL", "http://localhost:11434"), \
             patch("config.OLLAMA_MODEL", "llama3"), \
             patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
            from llm.ollama_provider import OllamaProvider
            provider = OllamaProvider()
            with self.assertRaises(RuntimeError) as ctx:
                provider.generate_script(markdown="text", language="en")
        self.assertIn("Ollama", str(ctx.exception))

    def test_http_error_raises_runtime_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404")

        with patch("config.OLLAMA_BASE_URL", "http://localhost:11434"), \
             patch("config.OLLAMA_MODEL", "llama3"), \
             patch("requests.post", return_value=mock_response):
            from llm.ollama_provider import OllamaProvider
            provider = OllamaProvider()
            with self.assertRaises(RuntimeError) as ctx:
                provider.generate_script(markdown="text", language="en")
        self.assertIn("Ollama API error", str(ctx.exception))

    def test_empty_response_field_returns_empty_string(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        with patch("config.OLLAMA_BASE_URL", "http://localhost:11434"), \
             patch("config.OLLAMA_MODEL", "llama3"), \
             patch("requests.post", return_value=mock_response):
            from llm.ollama_provider import OllamaProvider
            provider = OllamaProvider()
            result = provider.generate_script(markdown="text", language="en")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
