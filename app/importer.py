import json
import re
from typing import Any, Dict, List, Optional


def parse_bibtex(conteudo: str) -> List[Dict[str, Any]]:
    """
    Realiza o parse de string BibTeX (.bib) e retorna uma lista de dicionarios
    compatíveis com a tabela de artigos do Quire.
    """
    registros: List[Dict[str, Any]] = []
    # Divide por entradas bibtex iniciando com @tipo{chave, ...
    partes = re.split(r"(?=@\w+\s*\{)", conteudo)

    tipo_map = {
        "article": "artigo_periodico",
        "inproceedings": "artigo_conferencia",
        "conference": "artigo_conferencia",
        "proceedings": "artigo_conferencia",
        "book": "livro",
        "incollection": "capitulo_livro",
        "phdthesis": "tese",
        "mastersthesis": "dissertacao",
        "techreport": "relatorio",
        "unpublished": "preprint",
        "misc": "outro",
    }

    for parte in partes:
        parte = parte.strip()
        if not parte.startswith("@"):
            continue

        m_head = re.match(r"@(\w+)\s*\{\s*([^,]*),", parte, re.IGNORECASE)
        if not m_head:
            continue

        raw_tipo = m_head.group(1).lower()
        if raw_tipo in ("comment", "preamble", "string"):
            continue

        tipo_origem = tipo_map.get(raw_tipo, "outro")
        corpo = parte[m_head.end():]

        # Parse de campos: chave = {valor} ou "valor" ou número
        campos_raw = _extrair_campos_bibtex(corpo)

        titulo = _limpar_bib(campos_raw.get("title", ""))
        if not titulo:
            continue

        # Autores: separados por ' and '
        autores_raw = _limpar_bib(campos_raw.get("author", ""))
        autores_lista = _parse_bib_autores(autores_raw)

        # Ano
        ano_str = re.sub(r"\D", "", _limpar_bib(campos_raw.get("year", "")))[:4]
        ano = int(ano_str) if ano_str else None

        # DOI
        doi = _limpar_doi(_limpar_bib(campos_raw.get("doi", "")))

        # Resumo
        resumo = _limpar_bib(campos_raw.get("abstract", ""))

        # Classificação / Journal / Booktitle
        classificacao = _limpar_bib(
            campos_raw.get("journal", "")
            or campos_raw.get("booktitle", "")
            or campos_raw.get("publisher", "")
            or campos_raw.get("institution", "")
            or campos_raw.get("school", "")
        )

        # URL
        url_pagina = _limpar_bib(campos_raw.get("url", ""))
        if not url_pagina and doi:
            url_pagina = f"https://doi.org/{doi}"

        # Tags / Keywords
        tags_raw = _limpar_bib(campos_raw.get("keywords", "") or campos_raw.get("mendeley-tags", ""))
        tags_lista = [t.strip() for t in re.split(r"[,;]", tags_raw) if t.strip()]

        # File path do Mendeley (ex: :C\:/path/to/file.pdf:pdf ou /path/to/file.pdf)
        arquivo_local = _extrair_caminho_arquivo_bib(campos_raw.get("file", ""))

        registros.append({
            "titulo": titulo,
            "autores": json.dumps(autores_lista, ensure_ascii=False),
            "ano": ano,
            "doi": doi,
            "resumo": resumo,
            "tipo": "article",
            "tipo_origem": tipo_origem,
            "classificacao": classificacao,
            "url_pagina": url_pagina,
            "tags": json.dumps(tags_lista, ensure_ascii=False),
            "arquivo_local": arquivo_local,
            "fonte": "mendeley",
        })

    return registros


def _extrair_campos_bibtex(corpo: str) -> Dict[str, str]:
    campos: Dict[str, str] = {}
    tokens = re.split(r"\n\s*([a-zA-Z0-9_\-]+)\s*=\s*", "\n" + corpo)
    if len(tokens) > 1:
        for i in range(1, len(tokens), 2):
            k = tokens[i].lower().strip()
            v = tokens[i + 1].strip() if (i + 1) < len(tokens) else ""
            v = re.sub(r",\s*$", "", v.strip())
            campos[k] = v
    return campos


def _limpar_bib(val: str) -> str:
    if not val:
        return ""
    val = val.strip()
    if (val.startswith("{") and val.endswith("}")) or (val.startswith('"') and val.endswith('"')):
        val = val[1:-1].strip()
    val = val.replace("{", "").replace("}", "")
    val = re.sub(r"\\([a-zA-Z])", r"\1", val)
    return re.sub(r"\s+", " ", val).strip()


def _parse_bib_autores(autores_str: str) -> List[str]:
    if not autores_str:
        return []
    partes = autores_str.split(" and ")
    saida = []
    for p in partes:
        p = p.strip()
        if not p:
            continue
        if "," in p:
            sub = [s.strip() for s in p.split(",", 1)]
            nome_completo = f"{sub[1]} {sub[0]}".strip()
            saida.append(nome_completo)
        else:
            saida.append(p)
    return saida


def _extrair_caminho_arquivo_bib(file_val: str) -> str:
    if not file_val:
        return ""
    val = _limpar_bib(file_val)
    # Formato Mendeley: ":C\:/path/to/doc.pdf:pdf" ou ":/home/user/doc.pdf:PDF"
    partes = [p.strip() for p in val.split(";") if p.strip()]
    caminho = partes[0] if partes else val
    # Remove dois-pontos delimitadores do formato Mendeley
    if caminho.startswith(":") and caminho.count(":") >= 2:
        caminho = caminho.split(":")[1]
    caminho = caminho.replace(r"\:", ":")
    if caminho.lower().endswith(".pdf"):
        return caminho
    return ""


def parse_ris(conteudo: str) -> List[Dict[str, Any]]:
    """
    Realiza o parse de arquivos no formato RIS (Research Information Systems)
    exportados pelo Mendeley, Zotero ou EndNote.
    """
    registros: List[Dict[str, Any]] = []
    blocos = re.split(r"(?:\r?\n)ER\s*-", conteudo)

    ris_tipo_map = {
        "JOUR": "artigo_periodico",
        "CONF": "artigo_conferencia",
        "BOOK": "livro",
        "CHAP": "capitulo_livro",
        "THES": "tese",
        "RPRT": "relatorio",
        "UNPB": "preprint",
    }

    for bloco in blocos:
        bloco = bloco.strip()
        if not bloco:
            continue

        linhas = bloco.splitlines()
        tipo_origem = "artigo_periodico"
        titulo = ""
        autores: List[str] = []
        ano: Optional[int] = None
        doi = ""
        resumo = ""
        classificacao = ""
        url_pagina = ""
        tags: List[str] = []
        arquivo_local = ""

        ultimo_tag = None

        for linha in linhas:
            m = re.match(r"^([A-Z0-9]{2})\s*-\s*(.*)$", linha)
            if m:
                tag = m.group(1).upper()
                val = m.group(2).strip()
                ultimo_tag = tag

                if tag == "TY":
                    tipo_origem = ris_tipo_map.get(val.upper(), "outro")
                elif tag in ("TI", "T1", "CT", "BT") and not titulo:
                    titulo = val
                elif tag in ("AU", "A1"):
                    # Normalmente 'Sobrenome, Nome'
                    if "," in val:
                        partes = [p.strip() for p in val.split(",", 1)]
                        autores.append(f"{partes[1]} {partes[0]}".strip())
                    else:
                        autores.append(val)
                elif tag in ("PY", "Y1"):
                    m_ano = re.search(r"\b(19\d\d|20\d\d)\b", val)
                    if m_ano and not ano:
                        ano = int(m_ano.group(1))
                elif tag in ("DO", "DI"):
                    doi = _limpar_doi(val)
                elif tag in ("AB", "N2"):
                    resumo = (resumo + " " + val).strip() if resumo else val
                elif tag in ("JF", "JO", "JA", "T2", "PB"):
                    if not classificacao:
                        classificacao = val
                elif tag in ("UR", "LK"):
                    if not url_pagina:
                        url_pagina = val
                elif tag == "KW":
                    if val:
                        tags.append(val)
                elif tag in ("L1", "LK") and val.lower().endswith(".pdf"):
                    arquivo_local = val
            elif ultimo_tag in ("AB", "N2") and linha.strip():
                # Linha de continuacao para abstract
                resumo = (resumo + " " + linha.strip()).strip()

        if not titulo:
            continue

        if not url_pagina and doi:
            url_pagina = f"https://doi.org/{doi}"

        registros.append({
            "titulo": re.sub(r"\s+", " ", titulo).strip(),
            "autores": json.dumps(autores, ensure_ascii=False),
            "ano": ano,
            "doi": doi,
            "resumo": resumo,
            "tipo": "article",
            "tipo_origem": tipo_origem,
            "classificacao": classificacao,
            "url_pagina": url_pagina,
            "tags": json.dumps(tags, ensure_ascii=False),
            "arquivo_local": arquivo_local,
            "fonte": "mendeley",
        })

    return registros


def _limpar_doi(doi_str: str) -> str:
    if not doi_str:
        return ""
    d = doi_str.replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "")
    return d.strip().rstrip(".,;")
