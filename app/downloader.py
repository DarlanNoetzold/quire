import os
import re
import shutil
import unicodedata

import requests

from . import db
from .config import PDF_DIR, load_settings

TAMANHO_MAX = 200 * 1024 * 1024


def _sess():
    s = requests.Session()
    s.headers.update({
        "User-Agent": load_settings().get("user_agent", "Quire/2.0"),
        "Accept": "application/pdf, application/x-pdf, application/octet-stream, */*",
    })
    return s


def _nome_arquivo(titulo, artigo_id):
    normal = unicodedata.normalize("NFKD", titulo)
    normal = "".join(c for c in normal if not unicodedata.combining(c))
    normal = re.sub(r"[^\w\s-]", "", normal).strip().lower()
    normal = re.sub(r"[\s_]+", "-", normal)[:80] or "artigo"
    return f"{artigo_id}_{normal}.pdf"


def candidatos_url(artigo):
    from . import sources

    urls = []
    if artigo.get("url_pdf"):
        urls.append(artigo["url_pdf"])
    for u in artigo.get("urls_alternativas", []) or []:
        urls.append(u)
    if artigo.get("doi"):
        up = sources.obter_unpaywall(artigo["doi"])
        if up.get("url_pdf"):
            urls.insert(0, up["url_pdf"])
        for u in up.get("urls", []):
            urls.append(u)
        cr = sources.obter_crossref(artigo["doi"])
        for u in cr.get("links", []):
            urls.append(u)
        oa = sources.obter_openalex_doi(artigo["doi"])
        if oa.get("url_pdf"):
            urls.insert(0, oa["url_pdf"])
        for u in oa.get("urls", []):
            urls.append(u)
    vistos = []
    for u in urls:
        if u and u not in vistos and u.lower().startswith(("http://", "https://")):
            vistos.append(u)
    return vistos


def baixar_pdf(artigo):
    urls = candidatos_url(artigo)
    if not urls:
        db.update_artigo(artigo["id"], {"pdf_status": "nao_disponivel", "pdf_mensagem": "No open-access version found. Use manual import with the PDF you already have."})
        return {"ok": False, "motivo": "sem_url"}
    erros = []
    for url in urls:
        try:
            destino_temp = _baixar_uma(url)
            if destino_temp:
                final = _nome_arquivo(artigo.get("titulo", "artigo"), artigo["id"])
                caminho = os.path.join(PDF_DIR, final)
                shutil.move(destino_temp, caminho)
                db.update_artigo(artigo["id"], {"pdf_status": "baixado", "pdf_mensagem": url, "caminho_pdf": caminho})
                return {"ok": True, "url": url, "caminho": caminho}
        except Exception as e:
            erros.append(f"{url}: {type(e).__name__}")
    if not erros:
        msg = "Open sources did not deliver the PDF directly (HTML page, captcha or block). Open the publisher/repository page and use manual import."
    else:
        msg = "; ".join(erros[:4])
    db.update_artigo(artigo["id"], {"pdf_status": "falha", "pdf_mensagem": msg[:500]})
    return {"ok": False, "motivo": "erro", "detalhes": msg}


def _baixar_uma(url):
    with _sess().get(url, timeout=60, stream=True, allow_redirects=True) as r:
        if r.status_code >= 400:
            return None
        ct = (r.headers.get("Content-Type") or "").lower()
        if "html" in ct and not r.url.lower().endswith(".pdf"):
            return None
        tamanho = int(r.headers.get("Content-Length") or 0)
        if tamanho > TAMANHO_MAX:
            return None
        import tempfile

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=PDF_DIR)
        baixados = 0
        with tmp:
            for bloco in r.iter_content(65536):
                tmp.write(bloco)
                baixados += len(bloco)
                if baixados > TAMANHO_MAX:
                    tmp.close()
                    import os

                    os.unlink(tmp.name)
                    return None
        with open(tmp.name, "rb") as f:
            cabecalho = f.read(5)
        if cabecalho != b"%PDF-":
            import os

            os.unlink(tmp.name)
            return None
        return tmp.name
