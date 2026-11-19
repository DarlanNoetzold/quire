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
    "resumo_campos": ["objectives", "methodology", "results", "contributions", "limitations"],
    "resumo_campos_personalizados": [],
    "sumario_idioma": "English",
    "area_pesquisa": "post-quantum cryptography, quantum computing, cybersecurity, machine learning, deep learning, reinforcement learning, internet of things, smart environments, self-adaptive systems, high performance computing, anomaly detection",
    "email_unpaywall": "quire@example.com",
    "user_agent": "Quire/1.24 (https://github.com/DarlanNoetzold/quire; local research library)",
}

CATALOGO_CAMPOS = [
    {"id": "objectives", "rotulo": "Objectives", "instrucao": "the problem addressed and the goals of the work."},
    {"id": "motivation", "rotulo": "Motivation", "instrucao": "why the work matters and what real-world or scientific problem it addresses."},
    {"id": "methodology", "rotulo": "Methodology", "instrucao": "study design, materials/methods, data, techniques and metrics used."},
    {"id": "results", "rotulo": "Results", "instrucao": "main findings, with key numbers when present."},
    {"id": "contributions", "rotulo": "Contributions", "instrucao": "novelty, implications and what the work adds to the field."},
    {"id": "limitations", "rotulo": "Limitations", "instrucao": "stated or evident restrictions; if none, use \"Not identified in the text\"."},
    {"id": "novelty", "rotulo": "Novelty", "instrucao": "what is genuinely new compared with prior work."},
    {"id": "related_work", "rotulo": "Related work", "instrucao": "prior work the article builds on or positions itself against."},
    {"id": "future_work", "rotulo": "Future work", "instrucao": "next steps or open questions mentioned by the authors."},
    {"id": "experimental_setup", "rotulo": "Experimental setup", "instrucao": "datasets, environments, parameters and evaluation protocol used."},
]

DEFAULT_CAMPOS = ["objectives", "methodology", "results", "contributions", "limitations"]


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
