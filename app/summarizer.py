import json
import re
import subprocess
import time

import requests
from pypdf import PdfReader

from .config import CATALOGO_CAMPOS, DEFAULT_CAMPOS, load_settings


def _prototipo_chaves(campos):
    return ", ".join(f'"{c}": "..."' for c in campos) or '"objectives": "..."'


def _instrucao_campo(campo_id, settings):
    for c in CATALOGO_CAMPOS:
        if c["id"] == campo_id:
            return c["instrucao"]
    for p in settings.get("resumo_campos_personalizados") or []:
        if p.get("id") == campo_id:
            return p.get("instrucao") or "describe this aspect of the article, with details when present in the text."
    return "describe this aspect of the article, with details when present in the text."


def _campos_validos(campos, settings):
    ids = {c["id"] for c in CATALOGO_CAMPOS} | {p.get("id") for p in settings.get("resumo_campos_personalizados") or []}
    filtrados = [c for c in campos if c in ids]
    return filtrados or DEFAULT_CAMPOS


PROMPT = """You are an assistant specialized in critical reading of scientific articles.
Read the article text below and extract ONLY the requested information, answering in {idioma}.

Respond with valid JSON containing exactly these keys:
{{ {chaves} }}

Rules:
- Describe ONLY what is actually in the text. If a section is not present, use "Not identified in the text".
{regras}
- Each field with 2 to 8 objective sentences. Do not invent or generalize.
- Respond with only the JSON, no extra text, no markdown.

TITLE: {titulo}

ABSTRACT: {abstract}

ARTICLE TEXT:
{texto}"""


def montar_prompt(artigo, texto, campos=None):
    settings = load_settings()
    campos = _campos_validos(campos or [], settings)
    regras = "\n".join(f"- {c}: {_instrucao_campo(c, settings)}" for c in campos)
    if not regras:
        regras = "- objectives: the problem addressed and the goals of the work."
    idioma = settings.get("sumario_idioma", "English")
    return PROMPT.format(
        chaves=_prototipo_chaves(campos),
        regras=regras,
        idioma=idioma,
        titulo=(artigo.get("titulo") or "Untitled")[:500],
        abstract=(artigo.get("resumo") or "Not available")[:3000],
        texto=texto or "(no extractable text)",
    )


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
        montado = montado[:corte_ref] + "\n\n[references section omitted]"
    return montado[:limite]


def _postar_json(url, body, headers=None, timeout=600, tentativas=3):
    ultimo_erro = None
    for tentativa in range(tentativas):
        try:
            with requests.Session() as sessao:
                r = sessao.post(url, json=body, headers=headers or {}, timeout=timeout)
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except (requests.ConnectionError, requests.Timeout) as e:
            ultimo_erro = e
            time.sleep(1.5 * (tentativa + 1))
        except requests.HTTPError as e:
            if 429 <= e.response.status_code < 500:
                ultimo_erro = e
                time.sleep(1.5 * (tentativa + 1))
            else:
                raise
    raise ultimo_erro


def chamar_ollama(mensagens, settings):
    url = settings.get("ollama_base_url", "http://127.0.0.1:11434").rstrip("/") + "/v1/chat/completions"
    body = {
        "model": settings.get("ollama_model", "qwen2.5:3b"),
        "messages": mensagens,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    return _postar_json(url, body)


def chamar_abacus(mensagens, settings):
    url = settings.get("abacus_base_url", "https://routellm.abacus.ai/v1").rstrip("/") + "/chat/completions"
    chave = settings.get("abacus_api_key", "")
    if not chave:
        raise ValueError("Abacus API key not configured. Add it in Settings.")
    body = {
        "model": settings.get("abacus_model", "route-llm"),
        "messages": mensagens,
        "temperature": 0.2,
    }
    return _postar_json(url, body, headers={"Authorization": f"Bearer {chave}"})


def parse_resposta(texto, campos=None):
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        raise ValueError("Model response without JSON")
    dados = json.loads(m.group(0))
    dados_norm = {}
    for chave, valor in dados.items():
        dados_norm[re.sub(r"[\s_-]+", "", str(chave)).lower()] = valor
    campos = campos or DEFAULT_CAMPOS
    nao_id = "Não identificado no texto" if load_settings().get("sumario_idioma", "English") == "Portuguese" else "Not identified in the text"
    limpos = {}
    for campo in campos:
        chave_pt = _campo_pt(campo)
        normal_campo = re.sub(r"[\s_-]+", "", campo).lower()
        valor = str(dados_norm.get(normal_campo) or dados_norm.get(campo) or dados_norm.get(chave_pt) or "").strip()
        if re.match(r"^(n[aã]o\s+identif|not\s+identif|not\s+found|n/a|none|não\s+encontrado)$", valor, re.IGNORECASE):
            valor = nao_id
        limpos[campo] = valor or nao_id
    return limpos


def _campo_pt(campo):
    return {
        "objectives": "objetivos",
        "motivation": "motivacao",
        "methodology": "metodologia",
        "results": "resultados",
        "contributions": "contribuicoes",
        "limitations": "limitacoes",
        "novelty": "novidade",
        "related_work": "trabalhos_relacionados",
        "future_work": "trabalhos_futuros",
        "experimental_setup": "configuracao_experimental",
    }.get(campo, campo)


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
    campos = settings.get("resumo_campos") or DEFAULT_CAMPOS
    caminho = artigo.get("caminho_pdf")
    if not caminho:
        db.update_artigo(artigo["id"], {"resumo_status": "falha", "resumo_mensagem": "No PDF downloaded. Download or import the PDF before summarizing."})
        return
    if provider == "ollama":
        if not existe_modelo_exato(settings.get("ollama_model", "qwen2.5:3b")):
            db.update_artigo(artigo["id"], {"resumo_status": "processando", "resumo_mensagem": f"Downloading model {settings['ollama_model']} (first time only)..."})
            if progresso:
                progresso(f"baixando_modelo:{settings['ollama_model']}")
            ok, msg = baixar_modelo(settings["ollama_model"])
            if not ok:
                db.update_artigo(artigo["id"], {"resumo_status": "falha", "resumo_mensagem": f"Failed to download model: {msg}"})
                return
    try:
        texto = extrair_texto_pdf(caminho)
    except Exception as e:
        db.update_artigo(artigo["id"], {"resumo_status": "falha", "resumo_mensagem": f"PDF read error: {type(e).__name__}: {str(e)[:200]}"})
        return
    if len(texto.strip()) < 250:
        db.update_artigo(artigo["id"], {"resumo_status": "falha", "resumo_mensagem": "The PDF appears to be scanned or has no text layer. Use a PDF with selectable text."})
        return
    try:
        prompt = montar_prompt(artigo, texto, campos)
        mensagens = [{"role": "user", "content": prompt}]
        if provider == "ollama":
            resposta = chamar_ollama(mensagens, settings)
        elif provider == "abacus":
            resposta = chamar_abacus(mensagens, settings)
        else:
            raise ValueError(f"Unknown provider: {provider}")
        campos_finais = parse_resposta(resposta, campos)
        db.update_artigo(artigo["id"], {
            "resumo_llm": json.dumps(campos_finais, ensure_ascii=False),
            "resumo_status": "pronto",
            "resumo_mensagem": "",
            "resumo_provider": provider,
        })
    except Exception as e:
        db.update_artigo(artigo["id"], {"resumo_status": "falha", "resumo_mensagem": f"{type(e).__name__}: {str(e)[:200]}"})
