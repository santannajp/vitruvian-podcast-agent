"""
llm/ollama_provider.py — Local LLM provider via Ollama.

Calls the Ollama REST API running locally to generate podcast dialogue.
Model and base URL are configured via config.py / .env.
"""

import requests

import config
from llm.provider import LLMProvider
from script.prompts import get_podcast_prompt


class OllamaProvider(LLMProvider):
    """LLM provider that uses a locally running Ollama instance."""

    def __init__(self) -> None:
        self.base_url: str = config.OLLAMA_BASE_URL
        self.model: str = config.OLLAMA_MODEL
        self._generate_url: str = f"{self.base_url}/api/generate"

    def generate_script(self, markdown: str, language: str) -> str:
        """
        Generate a podcast dialogue script using Ollama.

        Args:
            markdown: Markdown-formatted source content.
            language: Canonical language code (e.g. "pt-BR", "en").

        Returns:
            Dialogue string with alternating Host1 / Host2 lines.

        Raises:
            RuntimeError: If the Ollama API call fails.
        """
        prompt = get_podcast_prompt(language=language, content=markdown)
        return self._call_ollama(prompt)

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _call_ollama(self, prompt: str) -> str:
        """
        Send a generate request to the Ollama REST API.

        Args:
            prompt: Full prompt string to send to the model.

        Returns:
            The model's response text.

        Raises:
            RuntimeError: On HTTP error or connection failure.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            response = requests.post(
                self._generate_url,
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Could not connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running (`ollama serve`)."
            ) from exc
        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(f"Ollama API error: {exc}") from exc

        data = response.json()
        return data.get("response", "").strip()
