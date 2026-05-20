"""
llm/provider.py — Abstract LLM provider interface.

All LLM implementations must subclass LLMProvider and implement
the generate_script method. No provider should be called outside
its own module (Architecture Invariant #6).
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for all LLM provider implementations."""

    @abstractmethod
    def generate_script(self, markdown: str, language: str) -> str:
        """
        Generate a podcast dialogue script from Markdown content.

        Args:
            markdown: Markdown-formatted source content.
            language: Canonical language code (e.g. "pt-BR", "en").

        Returns:
            A dialogue string alternating between Host1 and Host2 lines,
            in the format:
                Host1: ...
                Host2: ...
        """
