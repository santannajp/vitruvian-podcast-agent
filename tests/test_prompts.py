"""
tests/test_prompts.py — Unit tests for script/prompts.py
"""

import unittest

from script.prompts import get_podcast_prompt, PODCAST_PROMPT_TEMPLATE


class TestGetPodcastPrompt(unittest.TestCase):

    def test_returns_string(self):
        result = get_podcast_prompt(language="en", content="Some content.")
        self.assertIsInstance(result, str)

    def test_language_injected_in_prompt(self):
        result = get_podcast_prompt(language="pt-BR", content="Conteúdo.")
        self.assertIn("pt-BR", result)

    def test_content_injected_in_prompt(self):
        result = get_podcast_prompt(language="en", content="Important topic here.")
        self.assertIn("Important topic here.", result)

    def test_prompt_contains_host_format(self):
        result = get_podcast_prompt(language="en", content="text")
        self.assertIn("Host1:", result)
        self.assertIn("Host2:", result)

    def test_prompt_contains_rules_section(self):
        result = get_podcast_prompt(language="en", content="text")
        self.assertIn("Rules:", result)

    def test_template_has_placeholders(self):
        self.assertIn("{language}", PODCAST_PROMPT_TEMPLATE)
        self.assertIn("{content}", PODCAST_PROMPT_TEMPLATE)

    def test_different_languages_produce_different_prompts(self):
        result_en = get_podcast_prompt(language="en", content="same content")
        result_pt = get_podcast_prompt(language="pt-BR", content="same content")
        self.assertNotEqual(result_en, result_pt)


if __name__ == "__main__":
    unittest.main()
