import json
import re
import subprocess

import requests
from pypdf import PdfReader

from .config import load_settings

CAMPOS = ["objetivos", "metodologia", "resultados", "contribuicoes", "limitacoes"]

PROMPT = """Você é um assistente especializado em leitura crítica de artigos científicos.
Leia o texto do artigo abaixo e extraia APENAS as informações solicitadas, respondendo em português.

Responda com JSON válido contendo exatamente estas chaves:
{{
  "objetivos": "...",
  "metodologia": "...",
  "resultados": "...",
  "contribuicoes": "...",
  "limitacoes": "..."
}}

Regras:
- Descreva APENAS o que está de fato no texto. Se uma seção não aparecer, use "Não identificado no texto".
- objetivos: o problema endereçado e as metas do trabalho.
- metodologia: desenho do estudo, materiais/métodos, dados, técnicas e métricas usadas.
- resultados: principais achados, com números-chave quando presentes.
- contribuicoes: novidades, implicações e o que o trabalho agrega à área.
- limitacoes: restrições declaradas ou evidentes; se não houver, use "Não identificado no texto".
- Cada campo com 2 a 8 frases objetivas. Não invente nem generalize.
- Responda somente o JSON, sem texto extra, sem usar markdown.

TÍTULO: {titulo}

RESUMO (abstract): {abstract}

TEXTO DO ARTIGO:
{texto}"""


def extrair_texto_pdf(caminho):
    leitor = PdfReader(caminho)
    paginas = []
    for p in leitor.pages[:40]:
        try:
            paginas.append(p.extract_text() or "")
        except Exception:
            paginas.append("")
    texto = "\n".join(paginas)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    return montar_trecho_focado(texto)


PADRAO_SECOES = re.compile(
    r"^\s*(?:(\d+(?:\.\d+)?)[.)\s]+)?(abstract|introduction|background|related\s+work|"
    r"method(?:ology|s)?|approach|model|experiments?|results?|discussion|conclusion(?:s)?|"
    r"limitations?|resumo|introdu[çc][aã]o|metodologia|materiais?\s+e\s+m[ée]todos|resultados|"
    r"discuss[ãa]o|conclus[ãa]o|objetivos?|considera[çc][ãa]o(?:es)?\s+final|refer[êe]ncias|bibliografia)"
    r"[.:\s]*$",
    re.IGNORECASE | re.MULTILINE,
)

_SECOES_PRIORITARIAS = ["abstract", "resumo", "objetiv", "introdu", "method", "metod", "materiais",
                        "result", "discuss", "conclu", "limit"]


def montar_trecho_focado(texto, limite=14000):
    texto = texto.strip()
    if not texto:
        return ""
    achados = list(PADRAO_SECOES.finditer(texto))
    secoes = []
    corte_ref = None
    for i, m in enumerate(achados):
        fim = achados[i + 1].start() if i + 1 < len(achados) else len(texto)
        nome = m.group(0).strip()
        if re.search(r"refer[eê]ncias|references|bibliography", nome, re.IGNORECASE):
            corte_ref = m.start()
            continue
        secoes.append((nome, m.start(), min(fim, m.start() + 3000)))
    trechos = []
    vistos = set()
    usado = 0
    inicio = texto[: min(1200, limite, len(texto))]
    trechos.append(inicio)
    usado += len(inicio)
    for alvo in _SECOES_PRIORITARIAS:
        if usado >= limite:
            break
        for nome, ini, _fim in secoes:
            if alvo not in nome.lower() or ini in vistos:
                continue
            vistos.add(ini)
            corpo = texto[ini:_fim]
            trechos.append(corpo[: min(2500, limite - usado)])
            usado = min(limite, usado + min(len(corpo), 2500))
            break
    if not secoes:
        meio = len(texto) // 2
        trechos = [texto[:4000], texto[meio:meio + 4000], texto[-6000:]]
    montado = "\n\n[...]\n\n".join(trechos)
    if corte_ref is not None and len(montado) < limite:
        montado = montado[:corte_ref] + "\n\n[seção de referências omitida]"
    return montado[:limite]


def montar_prompt(artigo, texto):
    return PROMPT.format(
        titulo=(artigo.get("titulo") or "Sem título")[:500],
        abstract=(artigo.get("resumo") or "Não disponível")[:3000],
        texto=texto or "(sem texto extraível)",
    )


def chamar_ollama(mensagens, settings):
    url = settings.get("ollama_base_url", "http://127.0.0.1:11434").rstrip("/") + "/v1/chat/completions"
    body = {
        "model": settings.get("ollama_model", "qwen2.5:3b"),
        "messages": mensagens,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, json=body, timeout=600)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def chamar_abacus(mensagens, settings):
    url = settings.get("abacus_base_url", "https://routellm.abacus.ai/v1").rstrip("/") + "/chat/completions"
    chave = settings.get("abacus_api_key", "")
    if not chave:
        raise ValueError("Chave da API da Abacus não configurada. Adicione em Configurações.")
    body = {
        "model": settings.get("abacus_model", "route-llm"),
        "messages": mensagens,
        "temperature": 0.2,
    }
    r = requests.post(url, json=body, headers={"Authorization": f"Bearer {chave}"}, timeout=600)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def parse_resposta(texto):
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        raise ValueError("Resposta do modelo sem JSON")
    dados = json.loads(m.group(0))
    dados_norm = {}
    for chave, valor in dados.items():
        dados_norm[re.sub(r"[\s_-]+", "", str(chave)).lower()] = valor
    limpos = {}
    for campo in CAMPOS:
        valor = str(dados_norm.get(campo, "") or "").strip()
        if valor.lower().startswith("não identif") or valor.lower().startswith("nao identif"):
            valor = "Não identificado no texto"
        limpos[campo] = valor or "Não identificado no texto"
    return limpos


def modelo_ollama_existe(modelo):
    try:
        r = requests.get(f"{load_settings().get('ollama_base_url', 'http://127.0.0.1:11434')}/api/tags", timeout=10)
        modelos = [m["name"] for m in r.json().get("models", [])]
        return any(m == modelo or m.startswith(modelo.split(":")[0]) for m in modelos)
    except Exception:
        return False


def existe_modelo_exato(modelo):
    try:
        r = requests.get(f"{load_settings().get('ollama_base_url', 'http://127.0.0.1:11434')}/api/tags", timeout=10)
        return any(m["name"] == modelo for m in r.json().get("models", []))
    except Exception:
        return False


def baixar_modelo(modelo, progresso=None):
    proc = subprocess.Popen(
        ["ollama", "pull", modelo],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    ultima = ""
    for linha in proc.stdout:
        linha = linha.strip()
        if linha:
            ultima = linha
            if progresso:
                progresso(linha)
    proc.wait()
    return proc.returncode == 0, ultima


def resumir_artigo(artigo, progresso=None):
    from . import db

    settings = load_settings()
    provider = settings.get("summary_provider", "ollama")
    caminho = artigo.get("caminho_pdf")
    if not caminho:
        db.update_artigo(artigo["id"], {"resumo_status": "falha", "resumo_mensagem": "Sem PDF baixado. Baixe ou importe o PDF antes de resumir."})
        return
    if provider == "ollama":
        if not existe_modelo_exato(settings.get("ollama_model", "qwen2.5:3b")):
            db.update_artigo(artigo["id"], {"resumo_status": "processando", "resumo_mensagem": f"Baixando modelo {settings['ollama_model']} (só na primeira vez)..."})
            if progresso:
                progresso(f"baixando_modelo:{settings['ollama_model']}")
            ok, msg = baixar_modelo(settings["ollama_model"])
            if not ok:
                db.update_artigo(artigo["id"], {"resumo_status": "falha", "resumo_mensagem": f"Falha ao baixar modelo: {msg}"})
                return
    texto = extrair_texto_pdf(caminho)
    if len(texto.strip()) < 250:
        db.update_artigo(artigo["id"], {"resumo_status": "falha", "resumo_mensagem": "O PDF parece escaneado ou sem camada de texto. Use um PDF com texto selecionável."})
        return
    try:
        prompt = montar_prompt(artigo, texto)
        mensagens = [{"role": "user", "content": prompt}]
        if provider == "ollama":
            resposta = chamar_ollama(mensagens, settings)
        elif provider == "abacus":
            resposta = chamar_abacus(mensagens, settings)
        else:
            raise ValueError(f"Provedor desconhecido: {provider}")
        campos = parse_resposta(resposta)
        db.update_artigo(artigo["id"], {
            "resumo_llm": json.dumps(campos, ensure_ascii=False),
            "resumo_status": "pronto",
            "resumo_mensagem": "",
            "resumo_provider": provider,
        })
    except Exception as e:
        db.update_artigo(artigo["id"], {"resumo_status": "falha", "resumo_mensagem": f"{type(e).__name__}: {str(e)[:200]}"})
