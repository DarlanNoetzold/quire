import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import requests

from .config import load_settings

OPENALEX = "https://api.openalex.org"
ARXIV_API = "http://export.arxiv.org/api/query"
UNPAYWALL = "https://api.unpaywall.org/v2"
CROSSREF = "https://api.crossref.org/works"
SEMANTICSCHOLAR = "https://api.semanticscholar.org/graph/v1/paper/search"
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
DOAJ_API = "https://doaj.org/api/search/articles"
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

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
        "titulo": w.get("title") or "Untitled",
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


def _normalizar_semanticscholar(p):
    ext = p.get("externalIds") or {}
    oa = p.get("openAccessPdf") or {}
    venue = (p.get("venue") or "").strip()
    tipos = p.get("publicationTypes") or []
    eh_preprint = "preprint" in str(tipos).lower() or "arxiv" in venue.lower() or ext.get("ArXiv") is not None
    return {
        "id_fonte": f"semanticscholar:{p.get('paperId')}",
        "fonte": "semanticscholar",
        "doi": ext.get("DOI") or "",
        "titulo": p.get("title") or "Untitled",
        "autores": [a.get("name", "") for a in (p.get("authors") or []) if a.get("name")][:15],
        "ano": p.get("year"),
        "tipo": "preprint" if eh_preprint else "article",
        "tipo_origem": "preprint" if eh_preprint else "artigo_periodico",
        "resumo": p.get("abstract") or "",
        "classificacao": venue,
        "url_pdf": oa.get("url") or "",
        "urls_alternativas": [oa["url"]] if oa.get("url") else [],
        "url_pagina": f"https://www.semanticscholar.org/paper/{p.get('paperId')}" if p.get("paperId") else "",
        "acesso_aberto": bool(oa.get("url")),
    }


def buscar_semanticscholar(query, limite=15):
    params = {
        "query": query,
        "limit": limite,
        "fields": "title,abstract,authors,year,venue,externalIds,openAccessPdf,publicationTypes",
    }
    r = requests.get(SEMANTICSCHOLAR, params=params, headers=_ua(), timeout=30)
    if r.status_code == 429:
        return []
    r.raise_for_status()
    return [_normalizar_semanticscholar(p) for p in r.json().get("data", [])]


def _normalizar_pubmed(pa):
    art = pa.find(".//Article")
    pmid = pa.findtext(".//PMID") or ""
    titulo = art.findtext(".//ArticleTitle") if art is not None else "Untitled"
    autores = []
    for a in pa.findall(".//AuthorList/Author"):
        nome = a.findtext("CollectiveName") or f"{a.findtext('ForeName', default='')} {a.findtext('LastName', default='')}"
        nome = " ".join(nome.split())
        if nome:
            autores.append(nome)
    autores = autores[:15]
    ano = pa.findtext(".//PubDate/Year")
    if not ano:
        medline = pa.findtext(".//PubDate/MedlineDate")
        ano = medline[:4] if medline else ""
    doi = ""
    pmc = ""
    for el in list(pa.findall(".//ELocationID")) + list(pa.findall(".//ArticleId")):
        if el.get("EIdType") == "doi" or el.get("IdType") == "doi":
            doi = el.text or ""
        if el.get("EIdType") == "pmc" or el.get("IdType") == "pmc":
            pmc = el.text or ""
    journal = art.findtext(".//Journal/Title") if art is not None else ""
    mesh = [c.text for c in pa.findall(".//MeshHeading/DescriptorName")][:3]
    abstract = " ".join(t.text or "" for t in (art.findall(".//Abstract/AbstractText") if art is not None else []))
    url_pdf = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc}/pdf/" if pmc else ""
    return {
        "id_fonte": f"pubmed:{pmid}",
        "fonte": "pubmed",
        "doi": doi,
        "titulo": titulo or "Untitled",
        "autores": autores,
        "ano": int(ano) if str(ano).isdigit() else None,
        "tipo": "article",
        "tipo_origem": "artigo_periodico",
        "resumo": abstract,
        "classificacao": f"{journal} / {', '.join(mesh)}".strip(" /"),
        "url_pdf": url_pdf,
        "urls_alternativas": [url_pdf] if url_pdf else [],
        "url_pagina": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        "acesso_aberto": bool(url_pdf),
    }


def buscar_pubmed(query, limite=12):
    esearch = requests.get(PUBMED_ESEARCH, params={
        "db": "pubmed", "term": query, "retmax": limite, "retmode": "json", "sort": "relevance"
    }, headers=_ua(), timeout=30)
    esearch.raise_for_status()
    ids = esearch.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    efetch = requests.get(PUBMED_EFETCH, params={
        "db": "pubmed", "id": ",".join(ids), "rettype": "abstract", "retmode": "xml"
    }, headers=_ua(), timeout=30)
    efetch.raise_for_status()
    root = ET.fromstring(efetch.text)
    return [_normalizar_pubmed(pa) for pa in root.findall(".//PubmedArticle")]


def _normalizar_doaj(a):
    b = a.get("bibjson", {})
    autores = [x.get("name", "") for x in b.get("author", []) if x.get("name")][:15]
    links = b.get("link", [])
    url_pdf = next((l.get("url", "") for l in links if (l.get("content_type") or "").startswith("pdf") or "pdf" in l.get("url", "").lower()), "")
    url_pagina = next((l.get("url", "") for l in links if l.get("type") == "fulltext"), "")
    doi = ""
    for ident in b.get("identifier", []):
        if ident.get("type") in ("doi", "DOI"):
            doi = ident.get("id", "")
    sujeitos = [s.get("term", "") for s in b.get("subject", []) if s.get("term")]
    return {
        "id_fonte": f"doaj:{a.get('id')}",
        "fonte": "doaj",
        "doi": doi,
        "titulo": b.get("title") or "Untitled",
        "autores": autores,
        "ano": int(b.get("year")) if str(b.get("year") or "").isdigit() else None,
        "tipo": "article",
        "tipo_origem": "artigo_periodico",
        "resumo": b.get("abstract") or "",
        "classificacao": ", ".join(sujeitos),
        "url_pdf": url_pdf,
        "urls_alternativas": [url_pdf] if url_pdf else [],
        "url_pagina": url_pagina,
        "acesso_aberto": True,
    }


def buscar_doaj(query, limite=12):
    r = requests.get(f"{DOAJ_API}/{urllib.parse.quote(query)}", params={"pageSize": limite, "page": 1}, headers=_ua(), timeout=30)
    r.raise_for_status()
    return [_normalizar_doaj(a) for a in r.json().get("results", [])]


def _normalizar_europepmc(r):
    ano = (r.get("firstPublicationDate") or "")[:4]
    url_pdf = ""
    for ft in r.get("fullTextUrlList", {}).get("fullTextUrl", []) or []:
        if str(ft.get("documentStyle", "")).lower() == "pdf":
            url_pdf = ft.get("url", "")
            break
    eh_preprint = r.get("source") == "PPR"
    return {
        "id_fonte": f"europepmc:{r.get('id')}",
        "fonte": "europepmc",
        "doi": r.get("doi") or "",
        "titulo": r.get("title") or "Untitled",
        "autores": [a.strip() for a in (r.get("authorString") or "").split(", ") if a.strip()][:15],
        "ano": int(ano) if ano.isdigit() else None,
        "tipo": "preprint" if eh_preprint else "article",
        "tipo_origem": "preprint" if eh_preprint else "artigo_periodico",
        "resumo": r.get("abstractText") or "",
        "classificacao": r.get("journalTitle") or "",
        "url_pdf": url_pdf,
        "urls_alternativas": [url_pdf] if url_pdf else [],
        "url_pagina": f"https://europepmc.org/article/{r.get('source')}/{r.get('id')}" if r.get("id") else ("https://europepmc.org/article/MED/{}".format(r.get("pmid")) if r.get("pmid") else ""),
        "acesso_aberto": bool(url_pdf),
    }


def buscar_europepmc(query, limite=15):
    r = requests.get(EUROPEPMC, params={
        "query": query, "format": "json", "resultType": "core", "pageSize": limite
    }, headers=_ua(), timeout=30)
    r.raise_for_status()
    return [_normalizar_europepmc(x) for x in r.json().get("resultList", {}).get("result", [])]


def _limpar_jats(texto):
    return re.sub(r"<[^>]+>", "", texto or "")


def _normalizar_crossref(m):
    tipo = m.get("type", "journal-article")
    cr_tipo = {
        "journal-article": "article", "review-article": "review", "posted-content": "preprint",
        "book-chapter": "book-chapter", "proceedings-article": "proceedings-article",
        "book": "book", "dissertation": "dissertation", "report": "report",
    }
    ano = None
    if isinstance(m.get("issued", {}).get("date-parts", []), list) and m["issued"]["date-parts"]:
        ano = m["issued"]["date-parts"][0][0]
    titulo = (m.get("title") or [""])[0]
    container = (m.get("container-title") or [""])[0] or ""
    links = []
    for l in m.get("link", []) or []:
        if l.get("content-type") in ("application/pdf", "text/plain") or "pdf" in (l.get("URL") or "").lower():
            links.append(l.get("URL"))
    return {
        "id_fonte": f"crossref:{m.get('DOI')}",
        "fonte": "crossref",
        "doi": f"https://doi.org/{m.get('DOI')}" if m.get("DOI") else "",
        "titulo": titulo or "Untitled",
        "autores": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in m.get("author", [])][:15],
        "ano": ano,
        "tipo": cr_tipo.get(tipo, "article"),
        "tipo_origem": TIPO_ORIGEM_MAPA.get(cr_tipo.get(tipo, "article"), "artigo_periodico"),
        "resumo": _limpar_jats(m.get("abstract", "")) or "",
        "classificacao": container,
        "url_pdf": links[0] if links else "",
        "urls_alternativas": links[:5],
        "url_pagina": f"https://doi.org/{m.get('DOI')}" if m.get("DOI") else "",
        "acesso_aberto": bool(links),
    }


def buscar_crossref(query, limite=12):
    r = requests.get(CROSSREF, params={
        "query": query, "rows": limite, "select": "DOI,title,author,issued,abstract,container-title,type,link"
    }, headers=_ua(), timeout=30)
    r.raise_for_status()
    return [_normalizar_crossref(m) for m in r.json().get("message", {}).get("items", [])]


def buscar_tudo(query, tipo_origem=None, ano_min=None, ano_max=None):
    tipo_map_reverso = {v: k for k, v in TIPO_ORIGEM_MAPA.items()}
    tipo_o = tipo_map_reverso.get(tipo_origem) if tipo_origem else None

    def rodar_alvo(alvo, **kw):
        try:
            return alvo(query, **kw)
        except Exception:
            return []

    tarefas = []
    if not tipo_origem or tipo_origem in ("artigo_periodico", "revisao", "anais_congresso", "capitulo_livro", "livro", "tese_dissertacao", "relatorio"):
        tarefas.append(lambda: rodar_alvo(buscar_openalex, tipo=tipo_o, ano_min=ano_min, ano_max=ano_max, limite=18))
        tarefas.append(lambda: rodar_alvo(buscar_pubmed, limite=8))
        tarefas.append(lambda: rodar_alvo(buscar_doaj, limite=8))
        tarefas.append(lambda: rodar_alvo(buscar_europepmc, limite=10))
        tarefas.append(lambda: rodar_alvo(buscar_crossref, limite=8))
        tarefas.append(lambda: rodar_alvo(buscar_semanticscholar, limite=10))
    if not tipo_origem or tipo_origem == "preprint":
        tarefas.append(lambda: rodar_alvo(buscar_arxiv, limite=8))
        tarefas.append(lambda: rodar_alvo(buscar_semanticscholar, limite=6))
    resultados = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for lote in pool.map(lambda f: f(), tarefas):
            resultados.extend(lote)
    vistos = {}
    for r in resultados:
        chave = (r.get("doi") or r.get("titulo", "").lower()[:80]) or r.get("id_fonte", "")
        if chave in vistos:
            antigo = vistos[chave]
            extras = [u for u in r.get("urls_alternativas", []) if u not in antigo.get("urls_alternativas", [])]
            antigo["urls_alternativas"] += extras
            if not antigo.get("url_pdf") and r.get("url_pdf"):
                antigo["url_pdf"] = r["url_pdf"]
            if not antigo.get("acesso_aberto") and r.get("acesso_aberto"):
                antigo["acesso_aberto"] = True
            continue
        vistos[chave] = r
    return list(vistos.values())
