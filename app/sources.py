import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        "idioma": w.get("language") or "",
        "citacoes": int(w.get("cited_by_count") or 0),
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
    r = requests.get(f"{OPENALEX}/works", params=params, headers=_ua(), timeout=15)
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
        "idioma": "en",
        "citacoes": 0,
    }


def buscar_arxiv(query, limite=15):
    params = {
        "search_query": f"all:{query}",
        "max_results": limite,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    req = urllib.request.Request(f"{ARXIV_API}?{urllib.parse.urlencode(params)}", headers=_ua())
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_data = resp.read()
    root = ET.fromstring(xml_data)
    return [_normalizar_arxiv(e) for e in root.findall("{http://www.w3.org/2005/Atom}entry")]


def obter_unpaywall(doi):
    doi = doi.replace("https://doi.org/", "").replace("http://dx.doi.org/", "").strip("/")
    if not doi:
        return {}
    url = f"{UNPAYWALL}/{urllib.parse.quote(doi)}"
    try:
        r = requests.get(url, params={"email": load_settings().get("email_unpaywall", "")}, headers=_ua(), timeout=15)
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
        r = requests.get(f"{CROSSREF}/{urllib.parse.quote(doi)}", headers=_ua(), timeout=15)
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
        "idioma": "",
        "citacoes": int(p.get("citationCount") or 0),
    }


def buscar_semanticscholar(query, limite=15):
    params = {
        "query": query,
        "limit": limite,
        "fields": "title,abstract,authors,year,venue,externalIds,openAccessPdf,publicationTypes",
    }
    r = requests.get(SEMANTICSCHOLAR, params=params, headers=_ua(), timeout=15)
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
        "idioma": (pa.findtext(".//Language") or "").lower()[:3],
        "citacoes": 0,
    }


def buscar_pubmed(query, limite=12):
    esearch = requests.get(PUBMED_ESEARCH, params={
        "db": "pubmed", "term": query, "retmax": limite, "retmode": "json", "sort": "relevance"
    }, headers=_ua(), timeout=15)
    esearch.raise_for_status()
    ids = esearch.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    efetch = requests.get(PUBMED_EFETCH, params={
        "db": "pubmed", "id": ",".join(ids), "rettype": "abstract", "retmode": "xml"
    }, headers=_ua(), timeout=15)
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
        "idioma": (b.get("language") or [""])[0] if isinstance(b.get("language"), list) and b.get("language") else (b.get("language") or ""),
        "citacoes": 0,
    }


def buscar_doaj(query, limite=12):
    r = requests.get(f"{DOAJ_API}/{urllib.parse.quote(query)}", params={"pageSize": limite, "page": 1}, headers=_ua(), timeout=15)
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
        "idioma": r.get("language") or "",
        "citacoes": int(r.get("citedByCount") or 0),
    }


def buscar_europepmc(query, limite=15):
    r = requests.get(EUROPEPMC, params={
        "query": query, "format": "json", "resultType": "core", "pageSize": limite
    }, headers=_ua(), timeout=15)
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
        "idioma": m.get("language") or "",
        "citacoes": int(m.get("is-referenced-by-count") or 0),
    }


def buscar_crossref(query, limite=12):
    r = requests.get(CROSSREF, params={
        "query": query, "rows": limite, "select": "DOI,title,author,issued,abstract,container-title,type,link"
    }, headers=_ua(), timeout=15)
    r.raise_for_status()
    return [_normalizar_crossref(m) for m in r.json().get("message", {}).get("items", [])]


def _normalizar_dblp(info):
    autores = info.get("authors", {}).get("author", [])
    if isinstance(autores, str):
        autores = [autores]
    autores = [a.get("text", a) if isinstance(a, dict) else a for a in autores][:15]
    tipo = (info.get("type") or "").lower()
    if "conference" in tipo:
        tipo_origem = "anais_congresso"
    elif "journal" in tipo or "article" in tipo:
        tipo_origem = "artigo_periodico"
    elif "book" in tipo or "thesis" in tipo:
        tipo_origem = "livro" if "book" in tipo else "tese_dissertacao"
    else:
        tipo_origem = "artigo_periodico"
    ee = info.get("ee") or ""
    return {
        "id_fonte": f"dblp:{info.get('key')}",
        "fonte": "dblp",
        "doi": ("https://doi.org/" + info["doi"]) if info.get("doi") else "",
        "titulo": info.get("title") or "Untitled",
        "autores": autores,
        "ano": int(info["year"]) if str(info.get("year") or "").isdigit() else None,
        "tipo": "article" if tipo_origem == "artigo_periodico" else tipo_origem,
        "tipo_origem": tipo_origem,
        "resumo": "",
        "classificacao": info.get("venue") or "",
        "url_pdf": ee if ee.lower().endswith(".pdf") else "",
        "urls_alternativas": [ee] if ee else [],
        "url_pagina": info.get("url") or "",
        "acesso_aberto": True if ee else False,
        "idioma": "",
        "citacoes": 0,
    }


def buscar_dblp(query, limite=8):
    r = requests.get("https://dblp.org/search/publ/api", params={
        "q": query, "format": "json", "h": limite,
    }, headers=_ua(), timeout=15)
    r.raise_for_status()
    hits = r.json().get("result", {}).get("hits", {}).get("hit", []) or []
    return [_normalizar_dblp(h.get("info", {})) for h in hits]


def _normalizar_hal(doc):
    url_pdf = ""
    for f in (doc.get("fileMain_s") or [])[:2]:
        if isinstance(f, str) and f.startswith("http"):
            url_pdf = f
            break
    autores = []
    for a in doc.get("authFullName_s", []) or []:
        partes = [p.strip() for p in a.split(",")]
        if len(partes) == 2:
            autores.append(f"{partes[1]} {partes[0]}")
        else:
            autores.append(a)
    doc_tipo = (doc.get("docType_s") or "ART")
    ano = (doc.get("producedDateY_i") or [None])
    ano = ano[0] if isinstance(ano, list) and ano else (doc.get("producedDateY_i") if isinstance(doc.get("producedDateY_i"), int) else None)
    return {
        "id_fonte": f"hal:{doc.get('halId_s') or doc.get('docid')}",
        "fonte": "hal",
        "doi": ("https://doi.org/" + doc["doiId_s"]) if doc.get("doiId_s") else "",
        "titulo": (doc.get("title_s") or ["Untitled"])[0],
        "autores": autores[:15],
        "ano": ano,
        "tipo": "preprint" if doc_tipo == "PREPRINT" else "article",
        "tipo_origem": "preprint" if doc_tipo == "PREPRINT" else "artigo_periodico",
        "resumo": (doc.get("abstract_s") or [""])[0],
        "classificacao": (doc.get("journalTitle_s") or "") or (doc.get("none") or ""),
        "url_pdf": url_pdf,
        "urls_alternativas": [url_pdf] if url_pdf else [],
        "url_pagina": doc.get("uri_s") or "",
        "acesso_aberto": bool(url_pdf),
        "idioma": (doc.get("language_s") or [""])[0] or "",
        "citacoes": 0,
    }


def buscar_hal(query, limite=8):
    r = requests.get("https://api.archives-ouvertes.fr/search/", params={
        "q": query, "fl": "title_s,abstract_s,doiId_s,authFullName_s,producedDateY_i,fileMain_s,uri_s,docType_s,halId_s,language_s,journalTitle_s",
        "wt": "json", "rows": limite,
    }, headers=_ua(), timeout=15)
    r.raise_for_status()
    return [_normalizar_hal(d) for d in r.json().get("response", {}).get("docs", [])]


def _normalizar_zenodo(rec):
    md = rec.get("metadata", {})
    criadores = []
    for c in md.get("creators", []) or []:
        nome = c.get("name", "")
        if "," in nome:
            partes = [p.strip() for p in nome.split(",")]
            nome = f"{partes[1]} {partes[0]}"
        criadores.append(nome)
    url_pdf = ""
    for f in rec.get("files", []) or []:
        if (f.get("key") or "").lower().endswith(".pdf"):
            url_pdf = f.get("links", {}).get("self", "")
            break
    data = md.get("publication_date", "")
    return {
        "id_fonte": f"zenodo:{rec.get('id')}",
        "fonte": "zenodo",
        "doi": md.get("doi") or "",
        "titulo": md.get("title") or "Untitled",
        "autores": criadores[:15],
        "ano": int(data[:4]) if str(data)[:4].isdigit() else None,
        "tipo": "article",
        "tipo_origem": "artigo_periodico" if md.get("resource_type", {}).get("type") == "publication" else "capitulo_livro",
        "resumo": re.sub(r"<[^>]+>", "", md.get("description") or "")[:2000],
        "classificacao": ", ".join(md.get("subjects", [])[:3]),
        "url_pdf": url_pdf,
        "urls_alternativas": [url_pdf] if url_pdf else [],
        "url_pagina": rec.get("links", {}).get("html") or "",
        "acesso_aberto": True,
        "idioma": md.get("language") or "",
        "citacoes": 0,
    }


def buscar_zenodo(query, limite=8):
    r = requests.get("https://zenodo.org/api/records", params={
        "q": query, "size": limite, "sort": "mostrelevance",
        "type": "publication",
    }, headers=_ua(), timeout=15)
    r.raise_for_status()
    return [_normalizar_zenodo(rec) for rec in r.json().get("hits", {}).get("hits", [])]


def _extrair_openaire(res):
    ent = res.get("metadata", {}).get("oaf:entity", {})
    r = ent.get("oaf:result", {})
    if not r:
        return None
    md = r.get("metadata", {})
    titulo = ""
    for t in r.get("title") or []:
        if isinstance(t, dict) and t.get("$"):
            titulo = t["$"]
            break
    criadores = []
    for c in r.get("creator") or []:
        if isinstance(c, dict) and c.get("$"):
            criadores.append(str(c["$"]))
    doi = ""
    for p in r.get("pid") or []:
        if isinstance(p, dict) and str(p.get("@classid", "")) == "doi":
            doi = str(p.get("$", "")).replace("doi:", "")
            break
    data = r.get("dateofacceptance") or {}
    if isinstance(data, dict):
        ano = str(data.get("$", ""))[:4]
    else:
        ano = ""
    respublicacao = r.get("resulttype") or {}
    eh_preprint = "preprint" in str(respublicacao.get("@classid", "")).lower() or "0017" in str(respublicacao.get("@classid", ""))
    tipo_origem = "preprint" if eh_preprint else "artigo_periodico"
    idioma = (r.get("language") or {}).get("@classid", "")
    acesso = str((r.get("bestaccessright") or {}).get("@classid", "")).upper()
    url_pagina = f"https://doi.org/{doi}" if doi else ""
    return {
        "id_fonte": "openaire:" + str((r.get("originalId") or "")),
        "fonte": "openaire",
        "doi": ("https://doi.org/" + doi) if doi else "",
        "titulo": titulo.strip() or "Untitled",
        "autores": criadores[:15],
        "ano": int(ano) if str(ano).isdigit() else None,
        "tipo": "preprint" if eh_preprint else "article",
        "tipo_origem": tipo_origem,
        "resumo": "",
        "classificacao": "",
        "url_pdf": "",
        "urls_alternativas": [],
        "url_pagina": url_pagina,
        "acesso_aberto": acesso in ("OPEN", "GREEN", "GOLD"),
        "idioma": idioma,
        "citacoes": 0,
    }


def buscar_openaire(query, limite=8):
    r = requests.get("https://api.openaire.eu/search/publications", params={
        "keywords": query, "format": "json", "size": limite,
    }, headers=_ua(), timeout=8)
    r.raise_for_status()
    resultados = []
    for res in (r.json().get("response", {}).get("results", {}).get("result", []) or []):
        normal = _extrair_openaire(res)
        if normal:
            resultados.append(normal)
    return resultados


def _ordenar_resultados(resultados, ordenacao):
    if ordenacao == "ano_novo":
        return sorted(resultados, key=lambda r: (r.get("ano") is None, -(r.get("ano") or 0)))
    if ordenacao == "ano_velho":
        return sorted(resultados, key=lambda r: (r.get("ano") is None, r.get("ano") or 0))
    if ordenacao == "citacoes":
        return sorted(resultados, key=lambda r: -(r.get("citacoes") or 0))
    if ordenacao == "titulo_az":
        return sorted(resultados, key=lambda r: (r.get("titulo") or "").lower())
    return resultados


def buscar_tudo(query, tipo_origem=None, ano_min=None, ano_max=None, fontes=None, idioma=None, acesso_aberto=None, ordenacao=None):
    tipo_map_reverso = {v: k for k, v in TIPO_ORIGEM_MAPA.items()}
    tipo_o = tipo_map_reverso.get(tipo_origem) if tipo_origem else None
    fontes = set(fontes) if fontes else None

    def rodar_alvo(alvo, **kw):
        try:
            return alvo(query, **kw)
        except Exception:
            return []

    tarefas = []
    if not tipo_origem or tipo_origem in ("artigo_periodico", "revisao", "anais_congresso", "capitulo_livro", "livro", "tese_dissertacao", "relatorio"):
        pares_gerais = [
            (buscar_openalex, {"tipo": tipo_o, "ano_min": ano_min, "ano_max": ano_max, "limite": 16}, "openalex"),
            (buscar_pubmed, {"limite": 6}, "pubmed"),
            (buscar_doaj, {"limite": 6}, "doaj"),
            (buscar_europepmc, {"limite": 8}, "europepmc"),
            (buscar_crossref, {"limite": 6}, "crossref"),
            (buscar_semanticscholar, {"limite": 8}, "semanticscholar"),
            (buscar_dblp, {"limite": 6}, "dblp"),
            (buscar_hal, {"limite": 6}, "hal"),
            (buscar_zenodo, {"limite": 6}, "zenodo"),
            (buscar_openaire, {"limite": 6}, "openaire"),
        ]
        for fn, kw, nome in pares_gerais:
            if not fontes or nome in fontes:
                tarefas.append((nome, lambda fn=fn, kw=kw: rodar_alvo(fn, **kw)))
    if not tipo_origem or tipo_origem == "preprint":
        pares_preprint = [
            (buscar_arxiv, {"limite": 8}, "arxiv"),
            (buscar_semanticscholar, {"limite": 6}, "semanticscholar"),
            (buscar_hal, {"limite": 6}, "hal"),
            (buscar_openaire, {"limite": 6}, "openaire"),
        ]
        for fn, kw, nome in pares_preprint:
            if not fontes or nome in fontes:
                tarefas.append((nome, lambda fn=fn, kw=kw: rodar_alvo(fn, **kw)))
    resultados = []
    vistos_tasks = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(f): nome for nome, f in tarefas}
        vistos_tasks = futures
        for fut in as_completed(futures, timeout=22):
            try:
                lote = fut.result()
                resultados.extend(lote)
            except Exception:
                pass
    if ano_min or ano_max:
        antes = len(resultados)
        resultados = [
            r for r in resultados
            if (not ano_min or (r.get("ano") or 0) >= int(ano_min))
            and (not ano_max or (r.get("ano") or 0) <= int(ano_max))
        ]
    if idioma:
        resultados = [r for r in resultados if not r.get("idioma") or r["idioma"] == idioma]
    if acesso_aberto:
        resultados = [r for r in resultados if r.get("acesso_aberto")]
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
            if not antigo.get("idioma") and r.get("idioma"):
                antigo["idioma"] = r["idioma"]
            if not antigo.get("citacoes") and r.get("citacoes"):
                antigo["citacoes"] = r["citacoes"]
            continue
        vistos[chave] = r
    return _ordenar_resultados(list(vistos.values()), ordenacao)
