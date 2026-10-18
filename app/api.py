import json
import os
import shutil
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db, downloader, jobs, sources, summarizer
from .config import BASE_DIR, PDF_DIR, ensure_dirs

app = FastAPI(title="Leitor de Artigos", version="1.0.0")
WEB_DIR = os.path.join(BASE_DIR, "web")


@app.on_event("startup")
def _startup():
    ensure_dirs()
    db.init_db()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.on_event("startup")
def _startup():
    ensure_dirs()
    db.init_db()


@app.get("/api/busca")
def busca(q: str, tipo_origem: str = "", ano_min: str = "", ano_max: str = ""):
    if not q.strip():
        raise HTTPException(400, "Enter at least one keyword")
    return sources.buscar_tudo(
        q.strip(),
        tipo_origem=tipo_origem or None,
        ano_min=ano_min or None,
        ano_max=ano_max or None,
    )


@app.post("/api/artigos")
def criar_artigo(dados: dict):
    campos_papeis = {
        "id_fonte", "doi", "titulo", "autores", "ano", "tipo", "tipo_origem",
        "classificacao", "resumo", "url_pdf", "url_pagina", "urls_alternativas",
        "read_status", "idioma", "citacoes",
    }
    artigo = {k: v for k, v in dados.items() if k in campos_papeis}
    if not artigo.get("titulo"):
        raise HTTPException(400, "Title is required")
    if isinstance(artigo.get("autores"), list):
        artigo["autores"] = json.dumps(artigo["autores"], ensure_ascii=False)
    artigo["fonte"] = dados.get("fonte", "manual")
    artigo["acesso_aberto"] = 1 if dados.get("acesso_aberto") else 0
    artigo["favorito"] = 1 if dados.get("favorito") else 0
    if artigo.get("urls_alternativas"):
        artigo["urls_alternativas"] = json.dumps(artigo["urls_alternativas"], ensure_ascii=False)
    else:
        artigo["urls_alternativas"] = "[]"
    cat = dados.get("categoria_nome")
    if cat:
        cat_id = db.add_categoria(cat)
        artigo["categoria_id"] = cat_id
    if dados.get("pdf_status"):
        artigo["pdf_status"] = dados["pdf_status"]
    if dados.get("resumo_llm"):
        artigo["resumo_llm"] = dados["resumo_llm"]
        artigo["resumo_status"] = "pronto"
    return db.add_artigo(artigo)


@app.get("/api/artigos")
def listar_artigos(categoria_id: str = "", tipo_origem: str = "", pdf_status: str = "", tem_resumo: str = "", busca: str = "", fonte: str = "", acesso_aberto: str = "", ano_min: str = "", ano_max: str = "", ordenacao: str = "", autor: str = "", read_status: str = "", favorito: str = "", idioma: str = "", citacoes_min: str = "", adicionado: str = ""):
    return db.list_artigos({
        "categoria_id": categoria_id or None,
        "tipo_origem": tipo_origem or None,
        "pdf_status": pdf_status or None,
        "tem_resumo": tem_resumo or None,
        "busca": busca or None,
        "fonte": fonte or None,
        "acesso_aberto": acesso_aberto or None,
        "ano_min": ano_min or None,
        "ano_max": ano_max or None,
        "ordenacao": ordenacao or None,
        "autor": autor or None,
        "read_status": read_status or None,
        "favorito": favorito or None,
        "idioma": idioma or None,
        "citacoes_min": citacoes_min or None,
        "adicionado": adicionado or None,
    })


@app.get("/api/artigos/{artigo_id}")
def detalhe_artigo(artigo_id: int):
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        raise HTTPException(404, "Article not found")
    return artigo


@app.patch("/api/artigos/{artigo_id}")
def atualizar_artigo(artigo_id: int, dados: dict):
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        raise HTTPException(404, "Article not found")
    campos = {}
    for chave in ("categoria_id", "classificacao", "tipo_origem", "notas", "titulo", "tipo", "read_status", "idioma"):
        if chave in dados and dados[chave] is not None:
            campos[chave] = dados[chave]
    if dados.get("favorito") is not None:
        campos["favorito"] = 1 if dados["favorito"] else 0
    if dados.get("nova_categoria") and dados["nova_categoria"].strip():
        campos["categoria_id"] = db.add_categoria(dados["nova_categoria"].strip())
    return db.update_artigo(artigo_id, campos)


@app.delete("/api/artigos/{artigo_id}")
def excluir_artigo(artigo_id: int):
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        raise HTTPException(404, "Article not found")
    if artigo.get("caminho_pdf") and os.path.exists(artigo["caminho_pdf"]):
        try:
            os.remove(artigo["caminho_pdf"])
        except OSError:
            pass
    db.delete_artigo(artigo_id)
    return {"ok": True}


@app.post("/api/artigos/{artigo_id}/download")
def baixar_pdf(artigo_id: int):
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        raise HTTPException(404, "Article not found")
    iniciado = jobs.iniciar_download(artigo_id)
    if not iniciado:
        raise HTTPException(409, "A task is already running for this article")
    return {"ok": True}


@app.post("/api/artigos/{artigo_id}/resumir")
def resumir(artigo_id: int):
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        raise HTTPException(404, "Article not found")
    iniciado = jobs.iniciar_resumo(artigo_id)
    if not iniciado:
        raise HTTPException(409, "A task is already running for this article")
    return {"ok": True}


@app.get("/api/artigos/{artigo_id}/pdf")
def abrir_pdf(artigo_id: int):
    artigo = db.get_artigo(artigo_id)
    if not artigo or not artigo.get("caminho_pdf") or not os.path.exists(artigo["caminho_pdf"]):
        raise HTTPException(404, "PDF not available")
    return FileResponse(artigo["caminho_pdf"], media_type="application/pdf", filename=os.path.basename(artigo["caminho_pdf"]))


@app.post("/api/importar")
def importar(arquivo: UploadFile = File(...), titulo: str = Form(""), autores: str = Form(""), ano: str = Form(""), classificacao: str = Form(""), categoria: str = Form("")):
    nome = arquivo.filename or "importado.pdf"
    if not nome.lower().endswith(".pdf"):
        raise HTTPException(400, "The file must be a PDF")
    artigo_id = uuid.uuid4().int % 10**9
    destino = os.path.join(PDF_DIR, f"{artigo_id}_{os.path.basename(nome).replace(' ', '_')}")
    with open(destino, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)
    with open(destino, "rb") as f:
        if f.read(5) != b"%PDF-":
            os.remove(destino)
            raise HTTPException(400, "Invalid file: does not look like a PDF")
    from pypdf import PdfReader

    leitor = PdfReader(destino)
    autores_json = json.dumps([a.strip() for a in autores.split(";") if a.strip()], ensure_ascii=False)
    if not titulo:
        try:
            titulo = (leitor.metadata or {}).get("title") or nome.rstrip(".pdf").replace("_", " ")
        except Exception:
            titulo = nome.rstrip(".pdf").replace("_", " ")
    campos = {
        "fonte": "manual",
        "titulo": titulo,
        "autores": autores_json,
        "ano": int(ano) if ano.isdigit() else None,
        "tipo": "article",
        "tipo_origem": "artigo_periodico",
        "classificacao": classificacao or None,
        "caminho_pdf": destino,
        "pdf_status": "baixado",
        "pdf_mensagem": "imported manually",
    }
    if categoria.strip():
        campos["categoria_id"] = db.add_categoria(categoria.strip())
    return db.add_artigo(campos)


@app.get("/api/categorias")
def categorias():
    return db.list_categorias()


@app.delete("/api/categorias/{cat_id}")
def remover_categoria(cat_id: int):
    db.delete_categoria(cat_id)
    return {"ok": True}


@app.get("/api/configuracoes")
def get_config():
    from .config import load_settings

    config = dict(load_settings())
    config["api_key_definida"] = bool(config.get("abacus_api_key"))
    config["abacus_api_key"] = config["abacus_api_key"][:4] + "••••" if config.get("abacus_api_key") else ""
    return config


@app.post("/api/configuracoes")
def set_config(dados: dict):
    from .config import load_settings, save_settings

    atual = load_settings()
    if dados.get("abacus_api_key") and not dados["abacus_api_key"].endswith("••••"):
        atual["abacus_api_key"] = dados["abacus_api_key"].strip()
    if "abacus_api_key" in dados and not dados.get("abacus_api_key"):
        atual["abacus_api_key"] = ""
    for chave in ("summary_provider", "ollama_base_url", "ollama_model", "abacus_base_url", "abacus_model", "max_chars", "email_unpaywall"):
        if chave in dados and dados[chave] is not None and dados[chave] != "":
            atual[chave] = dados[chave]
    return save_settings(atual)


@app.get("/api/status-ferramentas")
def status_ferramentas():
    from .config import load_settings

    settings = load_settings()
    ollama_ok = summary_ok = False
    modelos = []
    try:
        import requests

        r = requests.get(f"{settings['ollama_base_url']}/api/tags", timeout=5)
        ollama_ok = r.status_code == 200
        if ollama_ok:
            modelos = [m["name"] for m in r.json().get("models", [])]
            summary_ok = any(m == settings["ollama_model"] for m in modelos)
    except Exception:
        pass
    return {
        "ollama_ok": ollama_ok,
        "modelos_ollama": modelos,
        "modelo_padrao_baixado": summary_ok,
        "provider": settings["summary_provider"],
    }


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
