"""
tests/test_language_detector.py — Unit tests for language/detector.py
"""

import unittest
from unittest.mock import patch

from language.detector import detect_language, _normalize_language_code


class TestNormalizeLanguageCode(unittest.TestCase):

    def test_pt_maps_to_pt_br(self):
        self.assertEqual(_normalize_language_code("pt"), "pt-BR")

    def test_zh_cn_maps_to_zh(self):
        self.assertEqual(_normalize_language_code("zh-cn"), "zh")

    def test_zh_tw_maps_to_zh(self):
        self.assertEqual(_normalize_language_code("zh-tw"), "zh")

    def test_zh_maps_to_zh(self):
        self.assertEqual(_normalize_language_code("zh"), "zh")

    def test_en_passthrough(self):
        self.assertEqual(_normalize_language_code("en"), "en")

    def test_es_passthrough(self):
        self.assertEqual(_normalize_language_code("es"), "es")

    def test_ru_passthrough(self):
        self.assertEqual(_normalize_language_code("ru"), "ru")

    def test_unsupported_language_defaults_to_en(self):
        self.assertEqual(_normalize_language_code("ja"), "en")

    def test_case_insensitive(self):
        self.assertEqual(_normalize_language_code("PT"), "pt-BR")


class TestDetectLanguage(unittest.TestCase):

    def test_empty_text_returns_en(self):
        self.assertEqual(detect_language(""), "en")

    def test_blank_text_returns_en(self):
        self.assertEqual(detect_language("   "), "en")

    def test_english_text_detected(self):
        with patch("language.detector.detect", return_value="en"):
            result = detect_language("This is an English sentence.")
        self.assertEqual(result, "en")

    def test_portuguese_text_detected_and_mapped(self):
        with patch("language.detector.detect", return_value="pt"):
            result = detect_language("Este é um texto em português.")
        self.assertEqual(result, "pt-BR")

    def test_spanish_text_detected(self):
        with patch("language.detector.detect", return_value="es"):
            result = detect_language("Este es un texto en español.")
        self.assertEqual(result, "es")

    def test_chinese_text_detected_and_mapped(self):
        with patch("language.detector.detect", return_value="zh-cn"):
            result = detect_language("这是中文内容。")
        self.assertEqual(result, "zh")

    def test_russian_text_detected(self):
        with patch("language.detector.detect", return_value="ru"):
            result = detect_language("Это текст на русском языке.")
        self.assertEqual(result, "ru")

    def test_lang_detect_exception_falls_back_to_en(self):
        from langdetect import LangDetectException
        with patch("language.detector.detect", side_effect=LangDetectException(0, "error")):
            result = detect_language("gibberish??$$##")
        self.assertEqual(result, "en")

    def test_unsupported_language_falls_back_to_en(self):
        with patch("language.detector.detect", return_value="ja"):
            result = detect_language("日本語のテキスト")
        self.assertEqual(result, "en")


if __name__ == "__main__":
    unittest.main()
