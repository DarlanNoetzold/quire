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
    if filtros.get("busca"):
        sql += " AND (a.titulo LIKE ? OR a.classificacao LIKE ? OR a.autores LIKE ?)"
        termo = f"%{filtros['busca']}%"
        params += [termo, termo, termo]
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


def contar_por_tipo_origem():
    conn = _conn()
    rows = conn.execute(
        "SELECT tipo_origem, COUNT(*) as total FROM artigos GROUP BY tipo_origem"
    ).fetchall()
    conn.close()
    return {r["tipo_origem"] or "sem_tipo": r["total"] for r in rows}


def json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False)
