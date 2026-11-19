import io
import json
import os
import re
import shutil
import tempfile
import time
import urllib.parse
import uuid
import zipfile

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        resposta = await super().get_response(path, scope)
        resposta.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resposta

from . import db, downloader, jobs, review, sources, summarizer
from .config import BASE_DIR, DATA_DIR, PDF_DIR, ensure_dirs

app = FastAPI(title="Quire", version="1.24.0")
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
def busca(q: str, tipo_origem: str = "", ano_min: str = "", ano_max: str = "", fontes: str = "", idioma: str = "", acesso_aberto: str = "", ordenacao: str = "", autor: str = "", assunto: str = "", citacoes_min: str = "", deduplicar: str = "1"):
    if not q.strip():
        raise HTTPException(400, "Enter at least one keyword")
    return sources.buscar_tudo(
        q.strip(),
        tipo_origem=tipo_origem or None,
        ano_min=ano_min or None,
        ano_max=ano_max or None,
        fontes=fontes.split(",") if fontes else None,
        idioma=idioma or None,
        acesso_aberto=bool(acesso_aberto),
        ordenacao=ordenacao or None,
        autor=autor or None,
        assunto=assunto or None,
        citacoes_min=citacoes_min or None,
        deduplicar=deduplicar not in ("0", "false", "False", "no"),
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
    dup = db.encontrar_duplicado(doi=dados.get("doi"), titulo=artigo["titulo"])
    if dup:
        raise HTTPException(409, {"mensagem": "Article already in your library", "id_duplicado": dup})
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
    novo = db.add_artigo(artigo)
    if novo.get("resumo_status") != "pronto":
        if novo.get("caminho_pdf") or novo.get("pdf_status") == "baixado":
            jobs.iniciar_resumo(novo["id"])
        elif novo.get("pdf_status") == "nao_baixado":
            jobs.iniciar_download(novo["id"])
    return novo


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
    if "tags" in dados:
        if isinstance(dados["tags"], str):
            dados["tags"] = [dados["tags"]]
        if isinstance(dados["tags"], list):
            campos["tags"] = json.dumps([str(t).strip()[:60] for t in dados["tags"] if str(t).strip()], ensure_ascii=False)
    if dados.get("progresso_leitura") is not None:
        try:
            campos["progresso_leitura"] = max(0, int(dados["progresso_leitura"]))
        except (TypeError, ValueError):
            pass
    if "paginas_total" in dados and dados["paginas_total"]:
        try:
            campos["paginas_total"] = max(0, int(dados["paginas_total"]))
        except (TypeError, ValueError):
            pass
    if dados.get("marcar_leitura") and dados["marcar_leitura"] in ("sim", True):
        import datetime

        campos["ultima_leitura"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        if dados.get("read_status") == "lidosim" or dados.get("marcar_lido"):
            campos["read_status"] = "lido"
    if dados.get("favorito") is not None:
        campos["favorito"] = 1 if dados["favorito"] else 0
    if dados.get("zera_resumo"):
        campos["resumo_status"] = "nao_iniciado"
        campos["resumo_mensagem"] = ""
        campos["resumo_llm"] = None
        campos["resumo_provider"] = None
    if dados.get("nova_categoria") and dados["nova_categoria"].strip():
        campos["categoria_id"] = db.add_categoria(dados["nova_categoria"].strip())
    return db.update_artigo(artigo_id, campos)


@app.delete("/api/artigos")
def excluir_artigos_em_lote(dados: dict):
    ids = dados.get("ids") if isinstance(dados, dict) else None
    if not isinstance(ids, list) or not ids or len(ids) > 5000 or any(
        isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in ids
    ):
        raise HTTPException(400, "ids must be a non-empty list of positive integers (maximum 5000)")
    artigos = db.excluir_artigos(ids)
    for artigo in artigos:
        caminho = artigo.get("caminho_pdf")
        if caminho and os.path.isfile(caminho):
            try:
                os.remove(caminho)
            except OSError:
                pass
    return {"ok": True, "deleted": len(artigos)}


@app.delete("/api/artigos/{artigo_id}")
def excluir_artigo(artigo_id: int):
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        raise HTTPException(404, "Article not found")
    if artigo.get("caminho_pdf") and os.path.isfile(artigo["caminho_pdf"]):
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
    return FileResponse(
        artigo["caminho_pdf"], media_type="application/pdf",
        filename=os.path.basename(artigo["caminho_pdf"]),
        content_disposition_type="inline",
    )


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
            titulo = (leitor.metadata or {}).get("title") or ""
        except Exception:
            titulo = ""
    metadados = _auto_metadados(leitor, destino)
    if not titulo.strip():
        titulo = metadados.get("titulo") or nome.rstrip(".pdf").replace("_", " ")
    if not autores.strip():
        autores_json = json.dumps(metadados.get("autores", []), ensure_ascii=False)
    if not ano and metadados.get("ano"):
        ano = str(metadados["ano"])
    if not classificacao:
        classificacao = metadados.get("classificacao", "")
    dup = db.encontrar_duplicado(doi=metadados.get("doi"), titulo=titulo.strip())
    if dup:
        os.remove(destino)
        raise HTTPException(409, {"mensagem": "This PDF is already in your library", "id_duplicado": dup})
    campos = {
        "fonte": "manual",
        "titulo": titulo.strip(),
        "autores": autores_json,
        "ano": int(ano) if ano.isdigit() else None,
        "tipo": "article",
        "tipo_origem": "artigo_periodico",
        "classificacao": classificacao or None,
        "doi": metadados.get("doi", ""),
        "resumo": metadados.get("resumo", ""),
        "caminho_pdf": destino,
        "pdf_status": "baixado",
        "pdf_mensagem": "imported manually",
    }
    if categoria.strip():
        campos["categoria_id"] = db.add_categoria(categoria.strip())
    novo = db.add_artigo(campos)
    jobs.iniciar_resumo(novo["id"])
    novo["metadados_auto"] = bool(metadados.get("doi"))
    return novo


@app.post("/api/importar/bibliografia")
async def importar_bibliografia(
    arquivo: UploadFile = File(...),
    formato: str = Form("auto"),
    categoria: str = Form(""),
    baixar_pdfs: bool = Form(True),
):
    """
    Importa multiplos artigos a partir de arquivo BibTeX (.bib) ou RIS (.ris)
    exportados de gerenciadores de referencia como Mendeley, Zotero e EndNote.
    Opera em modo append: adiciona novos artigos e preserva os existentes sem duplicar.
    """
    from . import importer

    nome_arquivo = (arquivo.filename or "").lower()
    conteudo_bytes = await arquivo.read()
    try:
        conteudo = conteudo_bytes.decode("utf-8")
    except UnicodeDecodeError:
        conteudo = conteudo_bytes.decode("latin-1", errors="ignore")

    # Detecta formato
    fmt = formato.lower().strip()
    if fmt == "auto":
        if nome_arquivo.endswith(".bib") or "@" in conteudo:
            fmt = "bibtex"
        elif nome_arquivo.endswith(".ris") or re.search(r"^[A-Z0-9]{2}\s*-", conteudo, re.MULTILINE):
            fmt = "ris"
        else:
            fmt = "bibtex"

    if fmt in ("bib", "bibtex"):
        registros = importer.parse_bibtex(conteudo)
    elif fmt in ("ris",):
        registros = importer.parse_ris(conteudo)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")

    if not registros:
        return {
            "total_processados": 0,
            "adicionados": 0,
            "duplicados": 0,
            "erros": 0,
            "artigos": [],
            "mensagem": "No valid bibliographic entries found in the uploaded file.",
        }

    cat_id = None
    if categoria.strip():
        cat_id = db.add_categoria(categoria.strip())

    importados = []
    total_duplicados = 0
    total_erros = 0

    for reg in registros:
        titulo = (reg.get("titulo") or "").strip()
        doi = (reg.get("doi") or "").strip()

        if not titulo:
            continue

        # Verifica duplicado (modo append seguro)
        dup = db.encontrar_duplicado(doi=doi if doi else None, titulo=titulo)
        if dup:
            total_duplicados += 1
            continue

        dados = {
            "titulo": titulo,
            "autores": reg.get("autores", "[]"),
            "ano": reg.get("ano"),
            "doi": doi,
            "resumo": reg.get("resumo", ""),
            "tipo": reg.get("tipo", "article"),
            "tipo_origem": reg.get("tipo_origem", "artigo_periodico"),
            "classificacao": reg.get("classificacao") or None,
            "url_pagina": reg.get("url_pagina", ""),
            "tags": reg.get("tags", "[]"),
            "fonte": reg.get("fonte", "mendeley"),
            "pdf_status": "pendente" if (doi and baixar_pdfs) else "nenhum",
            "pdf_mensagem": "Imported from Mendeley/Bib" if not doi else "Queued for automatic search",
        }
        if cat_id is not None:
            dados["categoria_id"] = cat_id

        # Se houver arquivo local de PDF especificado e ele existir, vincula ou copia
        caminho_local = reg.get("arquivo_local", "").strip()
        if caminho_local and os.path.isfile(caminho_local):
            try:
                base_nome = os.path.basename(caminho_local).replace(" ", "_")
                dest = os.path.join(PDF_DIR, f"bib_{int(time.time())}_{base_nome}")
                if not os.path.exists(dest):
                    shutil.copy2(caminho_local, dest)
                dados["caminho_pdf"] = dest
                dados["pdf_status"] = "baixado"
                dados["pdf_mensagem"] = "imported from local path"
            except Exception:
                pass

        try:
            novo = db.add_artigo(dados)
            if novo:
                importados.append(novo)

                # Se já tem PDF baixado, agenda resumo por IA
                if dados.get("pdf_status") == "baixado":
                    jobs.iniciar_resumo(novo["id"])
                elif doi and baixar_pdfs:
                    # Dispara download assincrono de versao aberta via OpenAlex/Unpaywall
                    jobs.iniciar_download(novo["id"])
        except Exception:
            total_erros += 1

    return {
        "total_processados": len(registros),
        "adicionados": len(importados),
        "duplicados": total_duplicados,
        "erros": total_erros,
        "artigos": importados,
        "mensagem": f"Import completed: {len(importados)} added, {total_duplicados} skipped (already in library).",
    }


def _auto_metadados(leitor, caminho):
    doi = _extrair_doi_pdf(leitor)
    if not doi:
        return {}
    from . import sources

    try:
        r = requests.get(f"{sources.CROSSREF}/{urllib.parse.quote(doi)}", headers=sources._ua(), timeout=12)
        if r.status_code != 200:
            return {"doi": doi}
        m = r.json().get("message", {})
        saida = {"doi": doi}
        titulo = (m.get("title") or [""])[0] or ""
        if titulo:
            saida["titulo"] = re.sub(r"\s+", " ", titulo).strip()
        autores = []
        for a in m.get("author", []) or []:
            nome = f"{a.get('given', '')} {a.get('family', '')}".strip()
            if nome:
                autores.append(nome)
        if autores:
            saida["autores"] = autores[:15]
        anos = m.get("issued", {}).get("date-parts", [])
        if anos and anos[0] and anos[0][0]:
            saida["ano"] = anos[0][0]
        container = (m.get("container-title") or [""])[0] or ""
        sujeitos = ", ".join(m.get("subject") or [])[:200]
        classificacao = " / ".join(x for x in (container, sujeitos) if x)
        if classificacao:
            saida["classificacao"] = classificacao
        resumo = re.sub(r"<[^>]+>", "", m.get("abstract") or "")[:3000]
        if resumo:
            saida["resumo"] = resumo
        return saida
    except Exception:
        return {"doi": doi}


def _extrair_doi_pdf(leitor):
    try:
        paginas = []
        for p in leitor.pages[:4]:
            try:
                paginas.append(p.extract_text() or "")
            except Exception:
                pass
    except Exception:
        return ""
    texto = "\n".join(paginas)
    padrao = re.compile(r"\b(?:doi[\s:]*|https?://(?:dx\.)?doi\.org/)(10\.\d{4,9}/[^\s<>\"'()\[\]{}]+)", re.IGNORECASE)
    m = re.search(padrao, texto)
    if not m:
        m2 = re.search(r"\b(10\.\d{4,9}/[^\s<>\"'()\[\]{}]+)", texto)
        if m2:
            return m2.group(1)
        return ""
    return m.group(1).rstrip(".,;")


@app.post("/api/artigos/{artigo_id}/pdf")
def anexar_pdf(artigo_id: int, arquivo: UploadFile = File(...)):
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        raise HTTPException(404, "Article not found")
    nome = arquivo.filename or "artigo.pdf"
    if not nome.lower().endswith(".pdf"):
        raise HTTPException(400, "The file must be a PDF")
    destino = os.path.join(PDF_DIR, f"{artigo_id}_{os.path.basename(nome).replace(' ', '_')}")
    with open(destino, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)
    with open(destino, "rb") as f:
        if f.read(5) != b"%PDF-":
            os.remove(destino)
            raise HTTPException(400, "Invalid file: does not look like a PDF")
    db.update_artigo(artigo_id, {
        "caminho_pdf": destino,
        "pdf_status": "baixado",
        "pdf_mensagem": "imported manually",
        "resumo_status": "nao_iniciado",
        "resumo_mensagem": "",
    })
    jobs.iniciar_resumo(artigo_id)
    return db.get_artigo(artigo_id)


@app.delete("/api/artigos/{artigo_id}/pdf")
def remover_pdf(artigo_id: int):
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        raise HTTPException(404, "Article not found")
    caminho = artigo.get("caminho_pdf")
    if caminho and os.path.exists(caminho):
        try:
            os.remove(caminho)
        except OSError:
            pass
    db.update_artigo(artigo_id, {
        "caminho_pdf": None,
        "pdf_status": "nao_baixado",
        "pdf_mensagem": "",
    })
    return db.get_artigo(artigo_id)


@app.get("/api/stats")
def stats():
    return db.estatisticas()


@app.get("/api/destaques")
def destaques(dias: int = 7):
    return sources.destaques(dias=max(1, min(dias, 365)))


@app.get("/api/artigos/{artigo_id}/metricas")
def metricas_artigo(artigo_id: int):
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        raise HTTPException(404, "Article not found")
    return sources.metricas(doi=artigo.get("doi") or "", titulo=artigo.get("titulo") or "")


@app.get("/api/artigos/{artigo_id}/reader")
def info_leitura(artigo_id: int):
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        raise HTTPException(404, "Article not found")
    if not artigo.get("caminho_pdf") or not os.path.exists(artigo["caminho_pdf"]):
        raise HTTPException(404, "PDF not available")
    total = db.contar_paginas(artigo["caminho_pdf"])
    if total and not artigo.get("paginas_total"):
        db.update_artigo(artigo_id, {"paginas_total": total})
        artigo["paginas_total"] = total
    return {
        "id": artigo_id,
        "paginas_total": total or artigo.get("paginas_total") or 0,
        "progresso_leitura": artigo.get("progresso_leitura") or 0,
        "read_status": artigo.get("read_status") or "nao_lido",
        "url_pdf": f"/api/artigos/{artigo_id}/pdf",
    }


@app.get("/api/dashboard")
def dashboard():
    return db.dashboard()


@app.get("/api/revisoes")
def listar_revisoes():
    return db.listar_revisoes()


@app.post("/api/revisoes")
def criar_revisao(dados: dict):
    titulo = str(dados.get("titulo", "")).strip()
    if not titulo:
        raise HTTPException(400, "Review title is required")
    try:
        revisao_id = db.criar_revisao(titulo[:250], str(dados.get("descricao", ""))[:2000])
        return db.get_revisao(revisao_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/revisao/artigos")
def artigos_disponiveis_revisao(revisao_id: int | None = None):
    if revisao_id is not None and not db.get_revisao(revisao_id):
        raise HTTPException(404, "Review not found")
    artigos = db.listar_artigos_revisao()
    if revisao_id is not None:
        selecionados = {a["artigo_id"] for a in db.listar_selecoes_revisao(revisao_id)}
        artigos = [a for a in artigos if a["id"] not in selecionados]
    for artigo in artigos:
        try:
            artigo["resumo_llm"] = json.loads(artigo.get("resumo_llm") or "{}")
        except (TypeError, ValueError):
            artigo["resumo_llm"] = {}
    return artigos


@app.get("/api/revisoes/{revisao_id}")
def detalhe_revisao(revisao_id: int):
    revisao = db.get_revisao(revisao_id)
    if not revisao:
        raise HTTPException(404, "Review not found")
    artigos = db.listar_selecoes_revisao(revisao_id)
    for artigo in artigos:
        artigo_completo = db.get_artigo(artigo["artigo_id"]) or {}
        try:
            artigo["resumo_llm"] = json.loads(artigo_completo.get("resumo_llm") or "{}")
        except (TypeError, ValueError, AttributeError):
            artigo["resumo_llm"] = {}
    return {
        "revisao": revisao,
        "artigos": artigos,
        "extracoes": db.listar_extracoes_revisao(revisao_id),
        "estatisticas": db.estatisticas_revisao(revisao_id),
        "graficos": review.extraction_chart_data(revisao_id),
    }


@app.delete("/api/revisoes/{revisao_id}")
def excluir_revisao(revisao_id: int):
    if not db.excluir_revisao(revisao_id):
        raise HTTPException(404, "Review not found")
    return {"ok": True}


@app.put("/api/revisoes/{revisao_id}/artigos/{artigo_id}")
def selecionar_artigo_revisao(revisao_id: int, artigo_id: int, dados: dict):
    try:
        return db.atualizar_selecao_revisao(
            revisao_id, artigo_id, dados.get("decisao", "pending"), dados.get("motivo", "")
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/revisoes/{revisao_id}/artigos/{artigo_id}")
def remover_artigo_revisao(revisao_id: int, artigo_id: int):
    if not db.remover_artigo_revisao(revisao_id, artigo_id):
        raise HTTPException(404, "Article is not in this review")
    return {"ok": True}


@app.post("/api/revisoes/{revisao_id}/extracoes/detectar")
def detectar_extracoes_revisao(revisao_id: int):
    if not db.get_revisao(revisao_id):
        raise HTTPException(404, "Review not found")
    extracoes = []
    for artigo in db.listar_artigos_revisao(revisao_id, decisao="included"):
        try:
            resumo = json.loads(artigo.get("resumo_llm") or "{}")
        except (TypeError, ValueError):
            resumo = {}
        for item in review.extract_numeric_evidence(resumo):
            item["artigo_id"] = artigo["id"]
            extracoes.append(item)
    salvas = db.salvar_extracoes_revisao(revisao_id, extracoes)
    return {"detectadas": len(extracoes), "salvas": salvas}


@app.put("/api/revisoes/{revisao_id}/extracoes")
def salvar_extracoes_revisao(revisao_id: int, dados: dict):
    if not db.get_revisao(revisao_id):
        raise HTTPException(404, "Review not found")
    extracoes = dados.get("extracoes", [])
    if not isinstance(extracoes, list) or len(extracoes) > 5000:
        raise HTTPException(400, "Invalid extraction list")
    try:
        salvas = db.salvar_extracoes_revisao(revisao_id, extracoes)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"salvas": salvas}


@app.get("/api/revisoes/{revisao_id}/grafico")
def grafico_revisao(revisao_id: int):
    if not db.get_revisao(revisao_id):
        raise HTTPException(404, "Review not found")
    return review.extraction_chart_data(revisao_id)


@app.get("/api/revisoes/{revisao_id}/csv")
def csv_revisao(revisao_id: int):
    if not db.get_revisao(revisao_id):
        raise HTTPException(404, "Review not found")
    output = io.StringIO()
    review.write_csv(output, db.listar_extracoes_revisao(revisao_id))
    return Response(
        content="\\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{review.csv_filename(revisao_id)}"'},
    )


@app.get("/api/tags")
def tags():
    return db.listar_tags()


@app.post("/api/resumir-todos")
def resumir_todos():
    artigos = [
        a["id"]
        for a in db.list_artigos({"tem_resumo": "nao"})
        if a.get("pdf_status") == "baixado" or a.get("caminho_pdf")
    ]
    agendados = 0
    for artigo_id in artigos:
        if jobs.iniciar_resumo(artigo_id):
            agendados += 1
    return {"agendados": agendados, "total": len(artigos)}


@app.get("/api/artigos/{artigo_id}/markdown")
def markdown_artigo(artigo_id: int):
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        raise HTTPException(404, "Article not found")
    return Response(
        content=_artigo_markdown(artigo),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="quire-{artigo_id}.md"'},
    )


def _artigo_markdown(a):
    try:
        autores = "".join(f"- {x}\n" for x in json.loads(a.get("autores") or "[]"))
    except Exception:
        autores = ""
    linhas = []
    linhas.append(f"# {a.get('titulo') or 'Untitled'}")
    linhas.append("")
    meta = []
    if a.get("autores"):
        meta.append(" ".join(f"{x}" for x in (json.loads(a.get("autores") or "[]") or [])[:8]))
    if a.get("ano"):
        meta.append(str(a["ano"]))
    if a.get("fonte"):
        meta.append(f"Source: {a['fonte']}")
    if meta:
        linhas.append("*" + " · ".join(meta) + "*")
        linhas.append("")
    if a.get("doi"):
        linhas.append(f"DOI: `{a.get('doi')}`")
        linhas.append("")
    if a.get("url_pagina"):
        linhas.append(f"Page: {a.get('url_pagina')}")
        linhas.append("")
    if autores:
        linhas.append("## Authors")
        linhas.append("")
        linhas.append(autores)
    if a.get("resumo"):
        linhas.append("## Abstract")
        linhas.append("")
        linhas.append(a["resumo"])
        linhas.append("")
    if a.get("resumo_llm"):
        linhas.append("## Structured summary")
        linhas.append("")
        try:
            campos = json.loads(a["resumo_llm"])
        except Exception:
            campos = {}
        for chave, valor in campos.items():
            linhas.append(f"### {chave.replace('_', ' ').title()}")
            linhas.append("")
            linhas.append(str(valor))
            linhas.append("")
    if a.get("notas"):
        linhas.append("## Notes")
        linhas.append("")
        linhas.append(a["notas"])
        linhas.append("")
    try:
        tags = json.loads(a.get("tags") or "[]")
    except Exception:
        tags = []
    if tags:
        linhas.append("## Tags")
        linhas.append("")
        linhas.append(" ".join(f"`{t}`" for t in tags))
    linhas.append("")
    linhas.append("---")
    linhas.append("")
    linhas.append("_Generated by Quire_")
    return "\n".join(linhas)


@app.patch("/api/categorias/{cat_id}")
def renomear_categoria(cat_id: int, dados: dict):
    from . import db as _db

    nome = dados.get("nome")
    cor = dados.get("cor")
    atualizado = {}
    if nome and str(nome).strip():
        atualizado["nome"] = str(nome).strip()[:80]
    if cor:
        atualizado["cor"] = str(cor)[:9]
    if not atualizado:
        raise HTTPException(400, "Nothing to update")
    conn = _db._conn()
    sets = ", ".join(f"{k} = ?" for k in atualizado)
    conn.execute(f"UPDATE categorias SET {sets} WHERE id = ?", list(atualizado.values()) + [cat_id])
    conn.commit()
    conn.close()
    return _db.get_categoria(cat_id)


@app.get("/api/export")
def exportar(formato: str = "bibtex"):
    import urllib.parse

    artigos = db.list_artigos({})
    if formato == "bibtex":
        conteudo = gerar_bibtex(artigos)
        media = "application/x-bibtex"
        nome = "quire.bib"
    elif formato == "json":
        conteudo = json.dumps(artigos, ensure_ascii=False, indent=2)
        media = "application/json"
        nome = "quire.json"
    elif formato == "markdown":
        conteudo = "\n\n".join(_artigo_markdown(a) for a in artigos)
        if not conteudo:
            conteudo = "_Empty library._"
        media = "text/markdown; charset=utf-8"
        nome = "quire-biblioteca.md"
    else:
        raise HTTPException(400, "Unknown format. Use 'bibtex', 'json' or 'markdown'.")
    return Response(
        content=conteudo,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


TIPO_BIBTEX = {
    "livro": "book",
    "anais_congresso": "inproceedings",
    "capitulo_livro": "incollection",
    "revisao": "article",
    "artigo_periodico": "article",
    "tese_dissertacao": "phdthesis",
    "preprint": "article",
    "relatorio": "techreport",
}


def _bib_escape(s):
    return (str(s)
            .replace("\\", r"\textbackslash{}")
            .replace("&", r"\&")
            .replace("%", r"\%")
            .replace("_", r"\_")
            .replace("#", r"\#"))


def _bib_autores(autores):
    if isinstance(autores, str):
        try:
            autores = json.loads(autores)
        except Exception:
            autores = []
    nomes = []
    for i, nome in enumerate(autores):
        partes = nome.strip().split()
        if len(partes) > 1:
            nomes.append(f"{partes[-1]}, {' '.join(partes[:-1])}")
        else:
            nomes.append(nome)
    return " and ".join(nomes)


def gerar_bibtex(artigos):
    entradas = []
    for a in artigos:
        autores = a.get("autores") or "[]"
        ano = a.get("ano") or ""
        titulo = re.sub(r"\s+", " ", a.get("titulo") or "").strip()
        chave_autor = ""
        try:
            lista = json.loads(autores) if isinstance(autores, str) else autores
            if lista and isinstance(lista[0], str):
                chave_autor = lista[0].split()[-1]
        except Exception:
            chave_autor = ""
        chave = f"{chave_autor or 'anon'}{ano}" + (("-" + re.sub(r'[\W]+', '', titulo)[:6]) if titulo else "")
        campo_tipo = TIPO_BIBTEX.get(a.get("tipo_origem") or "", "misc")
        campos = [
            ("title", _bib_escape(titulo)),
            ("author", _bib_autores(autores)),
        ]
        if ano:
            campos.insert(0, ("year", str(ano)))
        journal = a.get("classificacao") or ""
        if campo_tipo in ("article", "review"):
            if journal:
                campos.append(("journal", _bib_escape(journal)))
        elif campo_tipo == "inproceedings":
            if journal:
                campos.append(("booktitle", _bib_escape(journal)))
        elif campo_tipo in ("book", "incollection"):
            if journal:
                campos.append(("publisher", _bib_escape(journal)))
        elif campo_tipo == "phdthesis":
            if journal:
                campos.append(("school", _bib_escape(journal)))
        elif campo_tipo == "techreport":
            if journal:
                campos.append(("institution", _bib_escape(journal)))
        doi = a.get("doi") or ""
        if doi:
            campos.append(("doi", doi.replace("https://doi.org/", "")))
        if a.get("url_pagina"):
            campos.append(("url", a["url_pagina"]))
        if a.get("acesso_aberto"):
            campos.append(("note", "Open access"))
        linhas = ",\n".join(f"  {k} = {{{v}}}" for k, v in campos)
        entradas.append(f"@{campo_tipo}{{{chave},\n{linhas}\n}}")
    return "\n\n".join(entradas) + "\n"


@app.get("/api/backup")
def backup():
    dados = []
    for raiz, _dirs, arquivos in os.walk(DATA_DIR):
        for nome in arquivos:
            dados.append(os.path.join(raiz, nome))
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=DATA_DIR)
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as z:
        for caminho in dados:
            if os.path.abspath(caminho) == os.path.abspath(tmp.name):
                continue
            z.write(caminho, os.path.relpath(caminho, DATA_DIR))
    return FileResponse(
        tmp.name,
        media_type="application/zip",
        filename="quire-backup.zip",
        background=BackgroundTask(lambda: _apagar_zip(tmp.name)),
    )


def _apagar_zip(caminho):
    try:
        os.remove(caminho)
    except OSError:
        pass


@app.get("/api/categorias")
def categorias():
    return db.list_categorias()


@app.delete("/api/categorias/{cat_id}")
def remover_categoria(cat_id: int):
    db.delete_categoria(cat_id)
    return {"ok": True}


@app.get("/api/configuracoes")
def get_config():
    from .config import CATALOGO_CAMPOS, load_settings

    config = dict(load_settings())
    config["api_key_definida"] = bool(config.get("abacus_api_key"))
    config["abacus_api_key"] = config["abacus_api_key"][:4] + "••••" if config.get("abacus_api_key") else ""
    pessoais = config.get("resumo_campos_personalizados") or []
    config["resumo_campos_personalizados"] = pessoais
    config["resumo_campos_disponiveis"] = (
        [{"id": c["id"], "rotulo": c["rotulo"]} for c in CATALOGO_CAMPOS]
        + [{"id": p["id"], "rotulo": p["rotulo"], "personalizado": True} for p in pessoais]
    )
    config["resumo_campos"] = config.get("resumo_campos") or ["objectives", "methodology", "results", "contributions", "limitations"]
    return config


@app.post("/api/configuracoes")
def set_config(dados: dict):
    from .config import CATALOGO_CAMPOS, load_settings, save_settings

    atual = load_settings()
    if dados.get("abacus_api_key") and not dados["abacus_api_key"].endswith("••••"):
        atual["abacus_api_key"] = dados["abacus_api_key"].strip()
    if "abacus_api_key" in dados and not dados.get("abacus_api_key"):
        atual["abacus_api_key"] = ""
    for chave in ("summary_provider", "ollama_base_url", "ollama_model", "abacus_base_url", "abacus_model", "max_chars", "email_unpaywall", "area_pesquisa"):
        if chave in dados and dados[chave] is not None and str(dados[chave]).strip() != "":
            atual[chave] = str(dados[chave]).strip()
    if dados.get("sumario_idioma") in ("English", "Portuguese"):
        atual["sumario_idioma"] = dados["sumario_idioma"]
    if isinstance(dados.get("resumo_campos_personalizados"), list):
        ids_base = {c["id"] for c in CATALOGO_CAMPOS}
        guardados = []
        vistos = set(ids_base)
        for p in dados["resumo_campos_personalizados"]:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id") or "").strip()
            rotulo = str(p.get("rotulo") or "").strip()
            if not pid or not rotulo or pid in vistos:
                continue
            vistos.add(pid)
            guardados.append({
                "id": pid,
                "rotulo": rotulo[:80],
                "instrucao": str(p.get("instrucao") or "").strip()[:500],
            })
        atual["resumo_campos_personalizados"] = guardados
    if isinstance(dados.get("resumo_campos"), list):
        ids_validos = {c["id"] for c in CATALOGO_CAMPOS} | {p["id"] for p in atual.get("resumo_campos_personalizados") or []}
        campos = [str(x).strip() for x in dados["resumo_campos"] if str(x).strip() in ids_validos]
        atual["resumo_campos"] = campos
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


app.mount("/", NoCacheStaticFiles(directory=WEB_DIR, html=True), name="web")
