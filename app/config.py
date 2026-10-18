import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PDF_DIR = os.path.join(DATA_DIR, "pdfs")
DB_PATH = os.path.join(DATA_DIR, "biblioteca.db")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "summary_provider": "ollama",
    "ollama_base_url": "http://127.0.0.1:11434",
    "ollama_model": "qwen2.5:3b",
    "abacus_base_url": "https://routellm.abacus.ai/v1",
    "abacus_model": "route-llm",
    "abacus_api_key": "",
    "max_chars": 45000,
    "email_unpaywall": "leitor-artigos@exemplo.com",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
}


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(PDF_DIR, exist_ok=True)


def load_settings():
    ensure_dirs()
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                settings.update(json.load(f))
        except Exception:
            pass
    return settings


def save_settings(settings):
    ensure_dirs()
    merged = dict(DEFAULT_SETTINGS)
    merged.update(settings)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return merged
