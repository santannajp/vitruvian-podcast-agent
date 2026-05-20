"""
tests/test_chunker.py — Unit tests for chunking/chunker.py
"""

import unittest

from chunking.chunker import chunk_markdown, _estimate_tokens, Chunk


class TestEstimateTokens(unittest.TestCase):

    def test_empty_string(self):
        self.assertEqual(_estimate_tokens(""), 0)

    def test_single_word(self):
        self.assertEqual(_estimate_tokens("hello"), 1)

    def test_five_words(self):
        self.assertEqual(_estimate_tokens("one two three four five"), 5)


class TestChunkMarkdownEmptyInput(unittest.TestCase):

    def test_empty_string_returns_empty_list(self):
        result = chunk_markdown("")
        self.assertEqual(result, [])

    def test_whitespace_only_returns_empty_list(self):
        result = chunk_markdown("   \n   ")
        self.assertEqual(result, [])


class TestChunkMarkdownShortContent(unittest.TestCase):

    def test_short_text_produces_single_chunk(self):
        text = "This is a short paragraph with a few words."
        result = chunk_markdown(text, max_tokens=1500)
        self.assertEqual(len(result), 1)

    def test_single_chunk_has_correct_type(self):
        text = "Short content here."
        result = chunk_markdown(text, max_tokens=1500)
        self.assertIsInstance(result[0], Chunk)

    def test_single_chunk_index_is_zero(self):
        text = "Short content here."
        result = chunk_markdown(text, max_tokens=1500)
        self.assertEqual(result[0].index, 0)

    def test_single_chunk_content_matches(self):
        text = "Short content here."
        result = chunk_markdown(text, max_tokens=1500)
        self.assertIn("Short content here", result[0].content)

    def test_token_count_is_computed(self):
        text = "one two three four five"
        result = chunk_markdown(text, max_tokens=1500)
        self.assertEqual(result[0].token_count, 5)


class TestChunkMarkdownHeadings(unittest.TestCase):

    MULTI_HEADING_TEXT = """\
# Introduction

This is the introduction with a few words.

## Chapter One

Content of chapter one goes here.

## Chapter Two

Content of chapter two goes here.

### Section 2.1

A subsection with some additional text.
"""

    def test_multiple_headings_produce_multiple_chunks(self):
        result = chunk_markdown(self.MULTI_HEADING_TEXT, max_tokens=1500)
        self.assertGreater(len(result), 1)

    def test_chunks_have_sequential_indexes(self):
        result = chunk_markdown(self.MULTI_HEADING_TEXT, max_tokens=1500)
        for i, chunk in enumerate(result):
            self.assertEqual(chunk.index, i)

    def test_headings_are_captured_in_chunks(self):
        result = chunk_markdown(self.MULTI_HEADING_TEXT, max_tokens=1500)
        headings = [c.heading for c in result]
        self.assertIn("Introduction", headings)
        self.assertIn("Chapter One", headings)
        self.assertIn("Chapter Two", headings)

    def test_all_chunks_are_chunk_instances(self):
        result = chunk_markdown(self.MULTI_HEADING_TEXT, max_tokens=1500)
        for chunk in result:
            self.assertIsInstance(chunk, Chunk)


class TestChunkMarkdownLargeSection(unittest.TestCase):

    def _make_large_section(self, total_words: int, words_per_para: int = 200) -> str:
        """Build a section with multiple paragraphs (separated by blank lines).

        Each paragraph has *words_per_para* words, ensuring the chunker
        has paragraph boundaries to split on.
        """
        para = "word " * words_per_para
        n_paras = max(1, total_words // words_per_para)
        return "# Big Section\n\n" + "\n\n".join(para.strip() for _ in range(n_paras))

    def test_large_section_is_split_into_multiple_chunks(self):
        text = self._make_large_section(4000)
        result = chunk_markdown(text, max_tokens=1500)
        self.assertGreater(len(result), 1)

    def test_each_chunk_respects_max_tokens(self):
        # Allow a small buffer because paragraph splitting is not exact
        max_tokens = 500
        text = self._make_large_section(3000)
        result = chunk_markdown(text, max_tokens=max_tokens)
        for chunk in result:
            # Each chunk should be at most 2× max_tokens (worst-case single paragraph)
            self.assertLessEqual(chunk.token_count, max_tokens * 2)

    def test_chunks_cover_all_content(self):
        text = self._make_large_section(3000)
        result = chunk_markdown(text, max_tokens=500)
        combined = " ".join(c.content for c in result)
        # The heading ("# Big Section") is stored in chunk.heading, not content.
        # So we only compare the body text (everything after the first heading line).
        body_text = "\n".join(
            line for line in text.splitlines()
            if not line.startswith("#")
        )
        original_words = set(body_text.split())
        combined_words = set(combined.split())
        self.assertTrue(original_words.issubset(combined_words))


if __name__ == "__main__":
    unittest.main()
