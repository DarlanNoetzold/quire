import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import requests

from .config import load_settings

OPENALEX = "https://api.openalex.org"
ARXIV_API = "http://export.arxiv.org/api/query"
UNPAYWALL = "https://api.unpaywall.org/v2"
CROSSREF = "https://api.crossref.org/works"

TIPO_ORIGEM_MAPA = {
    "article": "artigo_periodico",
    "review": "revisao",
    "preprint": "preprint",
    "book-chapter": "capitulo_livro",
    "proceedings-article": "anais_congresso",
    "book": "livro",
    "dissertation": "tese_dissertacao",
    "report": "relatorio",
}


def _ua():
    return {"User-Agent": load_settings().get("user_agent", "leitor-artigos/1.0")}


def _reconstruir_abstract(inverted):
    if not inverted:
        return ""
    posicoes = {}
    for palavra, indices in inverted.items():
        for i in indices:
            posicoes[i] = palavra
    return " ".join(posicoes[i] for i in sorted(posicoes))


def _normalizar_openalex(w):
    aut = []
    for a in w.get("authorships", []):
        nome = a.get("author", {}).get("display_name", "")
        if nome:
            aut.append(nome)
    primary = w.get("primary_location") or {}
    best_oa = primary.get("pdf_url") or primary.get("landing_page_url")
    locs = []
    for l in w.get("locations", []) or []:
        u = l.get("pdf_url") or l.get("landing_page_url")
        if u and u not in locs:
            locs.append(u)
    concepts = []
    for c in (w.get("concepts") or [])[:4]:
        concepts.append(c.get("display_name", ""))
    conceito_principal = w.get("primary_topic", {}).get("field", {}).get("display_name") or (concepts[0] if concepts else "")
    subconceito = w.get("primary_topic", {}).get("subfield", {}).get("display_name") or (concepts[1] if len(concepts) > 1 else "")
    tipo = w.get("type", "article")
    return {
        "id_fonte": f"openalex:{w.get('id', '').split('/')[-1]}",
        "fonte": "openalex",
        "doi": w.get("doi") or "",
        "titulo": w.get("title") or "Sem título",
        "autores": aut[:15],
        "ano": w.get("publication_year"),
        "tipo": tipo,
        "tipo_origem": TIPO_ORIGEM_MAPA.get(tipo, "artigo_periodico"),
        "resumo": _reconstruir_abstract(w.get("abstract_inverted_index")) or "",
        "classificacao": f"{conceito_principal} / {subconceito}".strip(" /") or (", ".join(concepts)),
        "url_pdf": best_oa or "",
        "urls_alternativas": locs[:5],
        "url_pagina": primary.get("landing_page_url") or (w.get("doi") or ""),
        "acesso_aberto": bool(w.get("open_access", {}).get("is_oa")),
    }


def buscar_openalex(query, tipo=None, ano_min=None, ano_max=None, limite=25):
    ctx = urllib.parse.quote(query)
    filters = []
    if tipo:
        filters.append(f"type:{tipo}")
    if ano_min:
        filters.append(f"from_publication_date:{ano_min}-01-01")
    if ano_max:
        filters.append(f"to_publication_date:{ano_max}-12-31")
    params = {"search": query, "per-page": limite, "mailto": load_settings().get("email_unpaywall", "")}
    if filters:
        params["filter"] = ",".join(filters)
    r = requests.get(f"{OPENALEX}/works", params=params, headers=_ua(), timeout=30)
    r.raise_for_status()
    return [_normalizar_openalex(w) for w in r.json().get("results", [])]


def _normalizar_arxiv(e):
    ns = {"a": "http://www.w3.org/2005/Atom"}
    id_url = e.findtext("a:id", default="", namespaces=ns)
    num = id_url.split("/abs/")[-1]
    publico = e.findtext("a:published", default="", namespaces=ns)
    auts = [x.text for x in e.findall("a:author/a:name", namespaces=ns)]
    cats = [c.get("term", "") for c in e.findall("a:category", namespaces=ns)][:3]
    campos = {
        "cs": "Computer Science", "math": "Mathematics", "physics": "Physics",
        "stat": "Statistics", "eess": "Electrical Engineering", "q-bio": "Biology",
        "q-fin": "Finance", "econ": "Economics",
    }
    area = next((campos.get(c.split(".")[0], c) for c in cats), "")
    return {
        "id_fonte": f"arxiv:{num}",
        "fonte": "arxiv",
        "doi": "",
        "titulo": re.sub(r"\s+", " ", e.findtext("a:title", default="", namespaces=ns)).strip(),
        "autores": auts[:15],
        "ano": publico[:4] if publico else None,
        "tipo": "preprint",
        "tipo_origem": "preprint",
        "resumo": re.sub(r"\s+", " ", e.findtext("a:summary", default="", namespaces=ns)).strip(),
        "classificacao": area,
        "url_pdf": f"https://arxiv.org/pdf/{num}",
        "urls_alternativas": [id_url.replace("/abs/", "/pdf/") + ".pdf"],
        "url_pagina": id_url,
        "acesso_aberto": True,
    }


def buscar_arxiv(query, limite=15):
    params = {
        "search_query": f"all:{query}",
        "max_results": limite,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    req = urllib.request.Request(f"{ARXIV_API}?{urllib.parse.urlencode(params)}", headers=_ua())
    with urllib.request.urlopen(req, timeout=30) as resp:
        xml_data = resp.read()
    root = ET.fromstring(xml_data)
    return [_normalizar_arxiv(e) for e in root.findall("{http://www.w3.org/2005/Atom}entry")]


def obter_unpaywall(doi):
    doi = doi.replace("https://doi.org/", "").replace("http://dx.doi.org/", "").strip("/")
    if not doi:
        return {}
    url = f"{UNPAYWALL}/{urllib.parse.quote(doi)}"
    try:
        r = requests.get(url, params={"email": load_settings().get("email_unpaywall", "")}, headers=_ua(), timeout=25)
        if r.status_code != 200:
            return {}
        data = r.json()
        urls = []
        for loc in data.get("oa_locations", []) or []:
            u = loc.get("url_for_pdf") or loc.get("url")
            if u and u not in urls:
                urls.append(u)
        best = data.get("best_oa_location") or {}
        bpdf = best.get("url_for_pdf") or best.get("url")
        return {"url_pdf": bpdf or "", "urls": urls[:5], "eh_oa": bool(best)}
    except Exception:
        return {}


def obter_crossref(doi):
    doi = doi.replace("https://doi.org/", "").strip("/")
    if not doi:
        return {}
    try:
        r = requests.get(f"{CROSSREF}/{urllib.parse.quote(doi)}", headers=_ua(), timeout=25)
        if r.status_code != 200:
            return {}
        data = r.json().get("message", {})
        links = []
        for l in data.get("link", []) or []:
            if l.get("content-type") in ("application/pdf", "text/plain") or "pdf" in (l.get("URL") or "").lower():
                links.append(l.get("URL"))
        return {"links": links[:5]}
    except Exception:
        return {}


def buscar_tudo(query, tipo_origem=None, ano_min=None, ano_max=None):
    tipo_map_reverso = {v: k for k, v in TIPO_ORIGEM_MAPA.items()}
    tipo_o = tipo_map_reverso.get(tipo_origem) if tipo_origem else None
    resultados = []
    try:
        resultados += buscar_openalex(query, tipo=tipo_o, ano_min=ano_min, ano_max=ano_max)
    except Exception:
        pass
    if not tipo_origem or tipo_origem == "preprint":
        try:
            resultados += buscar_arxiv(query, limite=10)
        except Exception:
            pass
    vistos = {}
    for r in resultados:
        chave = (r.get("doi") or r.get("titulo", "").lower()[:80])
        if chave in vistos:
            antigo = vistos[chave]
            extras = [u for u in r.get("urls_alternativas", []) if u not in antigo.get("urls_alternativas", [])]
            antigo["urls_alternativas"] += extras
            if not antigo.get("url_pdf") and r.get("url_pdf"):
                antigo["url_pdf"] = r["url_pdf"]
            continue
        vistos[chave] = r
    return list(vistos.values())
