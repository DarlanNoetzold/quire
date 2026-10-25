import json
import sqlite3
from datetime import datetime, timezone

from .config import DB_PATH

PDF_STATUS = ("nao_disponivel", "nao_baixado", "baixando", "baixado", "falha")
SUMMARY_STATUS = ("nao_iniciado", "processando", "pronto", "falha")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    conn = _conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            cor TEXT DEFAULT '#4f8cff'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS artigos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fonte TEXT NOT NULL,
            id_fonte TEXT,
            doi TEXT,
            titulo TEXT NOT NULL,
            autores TEXT DEFAULT '[]',
            ano INTEGER,
            tipo TEXT,
            tipo_origem TEXT,
            classificacao TEXT,
            categoria_id INTEGER REFERENCES categorias(id),
            resumo TEXT,
            url_pdf TEXT,
            url_pagina TEXT,
            urls_alternativas TEXT DEFAULT '[]',
            acesso_aberto INTEGER DEFAULT 0,
            caminho_pdf TEXT,
            pdf_status TEXT DEFAULT 'nao_baixado',
            pdf_mensagem TEXT,
            resumo_llm TEXT,
            resumo_status TEXT DEFAULT 'nao_iniciado',
            resumo_mensagem TEXT,
            resumo_provider TEXT,
            notas TEXT,
            read_status TEXT DEFAULT 'nao_lido',
            favorito INTEGER DEFAULT 0,
            idioma TEXT,
            citacoes INTEGER DEFAULT 0,
            tags TEXT DEFAULT '[]',
            progresso_leitura INTEGER DEFAULT 0,
            paginas_total INTEGER DEFAULT 0,
            ultima_leitura TEXT,
            criado_em TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_artigos_cat ON artigos(categoria_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_artigos_status ON artigos(pdf_status)")
    _migrar(conn)
    conn.commit()
    conn.close()


def _migrar(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(artigos)").fetchall()}
    if "acesso_aberto" not in cols:
        conn.execute("ALTER TABLE artigos ADD COLUMN acesso_aberto INTEGER DEFAULT 0")
    if "read_status" not in cols:
        conn.execute("ALTER TABLE artigos ADD COLUMN read_status TEXT DEFAULT 'nao_lido'")
    if "favorito" not in cols:
        conn.execute("ALTER TABLE artigos ADD COLUMN favorito INTEGER DEFAULT 0")
    if "idioma" not in cols:
        conn.execute("ALTER TABLE artigos ADD COLUMN idioma TEXT")
    if "citacoes" not in cols:
        conn.execute("ALTER TABLE artigos ADD COLUMN citacoes INTEGER DEFAULT 0")
    if "tags" not in cols:
        conn.execute("ALTER TABLE artigos ADD COLUMN tags TEXT DEFAULT '[]'")
    if "progresso_leitura" not in cols:
        conn.execute("ALTER TABLE artigos ADD COLUMN progresso_leitura INTEGER DEFAULT 0")
    if "paginas_total" not in cols:
        conn.execute("ALTER TABLE artigos ADD COLUMN paginas_total INTEGER DEFAULT 0")
    if "ultima_leitura" not in cols:
        conn.execute("ALTER TABLE artigos ADD COLUMN ultima_leitura TEXT")


def add_categoria(nome, cor="#4f8cff"):
    conn = _conn()
    try:
        cur = conn.execute("INSERT INTO categorias (nome, cor) VALUES (?, ?)", (nome, cor))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        row = conn.execute("SELECT id FROM categorias WHERE nome = ?", (nome,)).fetchone()
        return row["id"]
    finally:
        conn.close()


def list_categorias():
    conn = _conn()
    rows = conn.execute("SELECT * FROM categorias ORDER BY nome").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_categoria(cat_id):
    conn = _conn()
    row = conn.execute("SELECT * FROM categorias WHERE id = ?", (cat_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_categoria(cat_id):
    conn = _conn()
    conn.execute("UPDATE artigos SET categoria_id = NULL WHERE categoria_id = ?", (cat_id,))
    conn.execute("DELETE FROM categorias WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()


def add_artigo(dados):
    conn = _conn()
    dados.setdefault("autores", "[]")
    dados.setdefault("criado_em", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    cols = ", ".join(dados.keys())
    marks = ", ".join("?" for _ in dados)
    cur = conn.execute(
        f"INSERT INTO artigos ({cols}) VALUES ({marks})", list(dados.values())
    )
    conn.commit()
    artigo_id = cur.lastrowid
    conn.close()
    return get_artigo(artigo_id)


def get_artigo(artigo_id):
    conn = _conn()
    row = conn.execute("SELECT * FROM artigos WHERE id = ?", (artigo_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


ORDENACOES = {
    "recente": "a.criado_em DESC",
    "antigo": "a.criado_em ASC",
    "titulo_az": "a.titulo COLLATE NOCASE ASC",
    "titulo_za": "a.titulo COLLATE NOCASE DESC",
    "ano_novo": "a.ano DESC, a.criado_em DESC",
    "ano_velho": "a.ano ASC, a.criado_em DESC",
    "classificacao": "a.classificacao COLLATE NOCASE ASC",
    "fonte": "a.fonte COLLATE NOCASE ASC",
    "citacoes": "a.citacoes DESC, a.ano DESC",
    "favoritos": "a.favorito DESC, a.criado_em DESC",
    "idioma": "a.idioma COLLATE NOCASE ASC",
    "autor": "a.autores COLLATE NOCASE ASC",
    "lendo": "a.read_status = 'lendo' DESC, a.ultima_leitura DESC",
    "ult_leitura": "COALESCE(a.ultima_leitura, '') DESC",
}


def list_artigos(filtros=None):
    filtros = filtros or {}
    sql = "SELECT a.*, c.nome AS categoria_nome, c.cor AS categoria_cor FROM artigos a LEFT JOIN categorias c ON a.categoria_id = c.id WHERE 1=1"
    params = []
    if filtros.get("categoria_id"):
        sql += " AND a.categoria_id = ?"
        params.append(filtros["categoria_id"])
    if filtros.get("tipo_origem"):
        sql += " AND a.tipo_origem = ?"
        params.append(filtros["tipo_origem"])
    if filtros.get("pdf_status"):
        sql += " AND a.pdf_status = ?"
        params.append(filtros["pdf_status"])
    if filtros.get("fonte"):
        sql += " AND a.fonte = ?"
        params.append(filtros["fonte"])
    if filtros.get("acesso_aberto"):
        sql += " AND a.acesso_aberto = 1"
    if filtros.get("ano_min"):
        sql += " AND a.ano >= ?"
        params.append(int(filtros["ano_min"]))
    if filtros.get("ano_max"):
        sql += " AND a.ano <= ?"
        params.append(int(filtros["ano_max"]))
    if filtros.get("tem_resumo") == "sim":
        sql += " AND a.resumo_status = 'pronto'"
    elif filtros.get("tem_resumo") == "nao":
        sql += " AND a.resumo_status != 'pronto'"
    if filtros.get("autor"):
        sql += " AND a.autores LIKE ?"
        params.append(f"%{filtros['autor']}%")
    if filtros.get("read_status"):
        sql += " AND a.read_status = ?"
        params.append(filtros["read_status"])
    if filtros.get("favorito"):
        sql += " AND a.favorito = 1"
    if filtros.get("idioma"):
        sql += " AND a.idioma = ?"
        params.append(filtros["idioma"])
    if filtros.get("citacoes_min"):
        sql += " AND a.citacoes >= ?"
        params.append(int(filtros["citacoes_min"]))
    if filtros.get("adicionado") in ("hoje", "7", "30", "90"):
        from datetime import datetime, timedelta, timezone

        agora = datetime.now(timezone.utc)
        if filtros["adicionado"] == "hoje":
            limite = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            limite = agora - timedelta(days=int(filtros["adicionado"]))
        sql += " AND a.criado_em >= ?"
        params.append(limite.isoformat(timespec="seconds"))
    if filtros.get("busca"):
        sql += " AND (a.titulo LIKE ? OR a.classificacao LIKE ? OR a.autores LIKE ?)"
        termo = f"%{filtros['busca']}%"
        params += [termo, termo, termo]
    if filtros.get("tag"):
        sql += " AND a.tags LIKE ?"
        params.append(f"%{filtros['tag']}%")
    if filtros.get("notas"):
        sql += " AND a.notas LIKE ?"
        params.append(f"%{filtros['notas']}%")
    if filtros.get("lendo"):
        sql += " AND a.read_status = 'lendo'"
    if filtros.get("ultima_leitura_dias"):
        from datetime import datetime, timedelta, timezone

        limite = datetime.now(timezone.utc) - timedelta(days=int(filtros["ultima_leitura_dias"]))
        sql += " AND a.ultima_leitura >= ?"
        params.append(limite.isoformat(timespec="seconds"))
    sql += " ORDER BY " + ORDENACOES.get(filtros.get("ordenacao"), ORDENACOES["recente"])
    conn = _conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_artigo(artigo_id, campos):
    if not campos:
        return get_artigo(artigo_id)
    conn = _conn()
    sets = ", ".join(f"{k} = ?" for k in campos)
    conn.execute(f"UPDATE artigos SET {sets} WHERE id = ?", list(campos.values()) + [artigo_id])
    conn.commit()
    conn.close()
    return get_artigo(artigo_id)


def delete_artigo(artigo_id):
    conn = _conn()
    conn.execute("DELETE FROM artigos WHERE id = ?", (artigo_id,))
    conn.commit()
    conn.close()


def estatisticas():
    conn = _conn()
    row = conn.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN pdf_status = 'baixado' THEN 1 ELSE 0 END) AS com_pdf,
               SUM(CASE WHEN resumo_status = 'pronto' THEN 1 ELSE 0 END) AS com_resumo,
               SUM(CASE WHEN favorito = 1 THEN 1 ELSE 0 END) AS favoritos,
               SUM(CASE WHEN read_status = 'nao_lido' THEN 1 ELSE 0 END) AS nao_lidos,
               SUM(COALESCE(citacoes, 0)) AS citacoes_total
        FROM artigos
        """
    ).fetchone()
    conn.close()
    saida = dict(row) if row else {}
    for chave in ("com_pdf", "com_resumo", "favoritos", "nao_lidos", "citacoes_total"):
        saida[chave] = int(saida.get(chave) or 0)
    saida["total"] = int(saida.get("total") or 0)
    return saida


def encontrar_duplicado(doi=None, titulo=None):
    if not doi and not titulo:
        return None
    conn = _conn()
    if doi:
        doi_limpo = doi.replace("https://doi.org/", "").strip("/")
        row = conn.execute("SELECT id FROM artigos WHERE doi LIKE ?", (f"%{doi_limpo}%",)).fetchone()
        if row:
            conn.close()
            return row["id"]
    if titulo:
        row = conn.execute("SELECT id FROM artigos WHERE LOWER(titulo) = LOWER(?)", (titulo.strip(),)).fetchone()
        if row:
            conn.close()
            return row["id"]
    conn.close()
    return None


def contar_por_tipo_origem():
    conn = _conn()
    rows = conn.execute(
        "SELECT tipo_origem, COUNT(*) as total FROM artigos GROUP BY tipo_origem"
    ).fetchall()
    conn.close()
    return {r["tipo_origem"] or "sem_tipo": r["total"] for r in rows}


def listar_tags():
    conn = _conn()
    rows = conn.execute("SELECT tags FROM artigos WHERE tags IS NOT NULL AND tags != '[]'").fetchall()
    conn.close()
    from collections import Counter

    contagem = Counter()
    for r in rows:
        try:
            for t in json.loads(r["tags"] or "[]"):
                if isinstance(t, str) and t.strip():
                    contagem[t.strip().lower()] += 1
        except Exception:
            continue
    return [{"tag": tag, "quantidade": n} for tag, n in contagem.most_common()]


def dashboard():
    conn = _conn()
    total_por_ano = dict(conn.execute(
        "SELECT ano, COUNT(*) FROM artigos WHERE ano IS NOT NULL GROUP BY ano ORDER BY ano DESC"
    ).fetchall())
    total_por_fonte = dict(conn.execute(
        "SELECT fonte, COUNT(*) FROM artigos GROUP BY fonte ORDER BY 2 DESC"
    ).fetchall())
    total_por_leitura = dict(conn.execute(
        "SELECT read_status, COUNT(*) FROM artigos GROUP BY read_status"
    ).fetchall())
    total_por_pdf = dict(conn.execute(
        "SELECT pdf_status, COUNT(*) FROM artigos GROUP BY pdf_status"
    ).fetchall())
    paginas = conn.execute(
        "SELECT SUM(CASE WHEN progresso_leitura > 0 THEN 1 ELSE 0 END) AS sendo_lidos, SUM(progresso_leitura) AS paginas_lidas FROM artigos WHERE caminho_pdf IS NOT NULL"
    ).fetchone()
    conn.close()
    return {
        "por_ano": total_por_ano,
        "por_fonte": total_por_fonte,
        "por_leitura": total_por_leitura,
        "por_pdf": total_por_pdf,
        "paginas_lidas": int(paginas["paginas_lidas"] or 0),
        "sendo_lidos": int(paginas["sendo_lidos"] or 0),
    }


def json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False)


def contar_paginas(caminho):
    try:
        from pypdf import PdfReader

        leitor = PdfReader(caminho)
        return len(leitor.pages)
    except Exception:
        return None
