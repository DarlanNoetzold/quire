import unittest
from unittest.mock import patch

import requests

from app import summarizer


class SummarizerTests(unittest.TestCase):
    def test_baixar_modelo_reports_helpful_error_when_ollama_cli_missing(self):
        with patch("subprocess.Popen", side_effect=FileNotFoundError(2, "No such file or directory", "ollama")):
            ok, msg = summarizer.baixar_modelo("qwen2.5:3b")

        self.assertFalse(ok)
        self.assertIn("Ollama executable was not found", msg)

    def test_chamar_ollama_reports_connection_error_cleanly(self):
        settings = {
            "ollama_base_url": "http://127.0.0.1:11434",
            "ollama_model": "qwen2.5:3b",
        }
        with patch.object(summarizer, "_postar_json", side_effect=requests.ConnectionError("offline")):
            with self.assertRaises(RuntimeError) as ctx:
                summarizer.chamar_ollama([{"role": "user", "content": "hi"}], settings)

        self.assertIn("Ollama server not reachable", str(ctx.exception))
