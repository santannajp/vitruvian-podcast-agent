"""
llm/openai_provider.py — LLM provider via OpenAI API.

Uses the official openai Python SDK to call the OpenAI chat completions endpoint.
Model and API key are configured via config.py / .env.
"""

import config
from llm.provider import LLMProvider
from script.prompts import get_podcast_prompt


class OpenAIProvider(LLMProvider):
    """LLM provider that calls the OpenAI API cloud service."""

    def __init__(self) -> None:
        # Lazy import so the library is only required when this provider is used.
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "openai package is required for OpenAIProvider. "
                "Install it with: pip install openai"
            ) from exc

        api_key: str = config.OPENAI_API_KEY
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Add it to your .env file or environment variables."
            )

        self.model: str = config.OPENAI_MODEL
        self._client = OpenAI(api_key=api_key)

    def generate_script(self, markdown: str, language: str) -> str:
        """
        Generate a podcast dialogue script using the OpenAI API.

        Args:
            markdown: Markdown-formatted source content.
            language: Canonical language code (e.g. "pt-BR", "en").

        Returns:
            Dialogue string with alternating Host1 / Host2 lines.

        Raises:
            RuntimeError: If the OpenAI API call fails.
        """
        prompt = get_podcast_prompt(language=language, content=markdown)
        return self._call_openai(prompt)

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    def _call_openai(self, prompt: str) -> str:
        """
        Send a chat completion request to the OpenAI API.

        Args:
            prompt: Full prompt string to send to the model.

        Returns:
            The model's response text.

        Raises:
            RuntimeError: On API error or connection failure.
        """
        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception as exc:
            raise RuntimeError(f"OpenAI API error: {exc}") from exc

        return completion.choices[0].message.content.strip()
