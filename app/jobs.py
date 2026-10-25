import logging
import threading

from . import db
from . import downloader
from . import summarizer

_trabalhos = {}
_lock = threading.Lock()


def _registrar(tipo, artigo_id):
    with _lock:
        _trabalhos[(tipo, artigo_id)] = True


def _finalizar(tipo, artigo_id):
    with _lock:
        _trabalhos.pop((tipo, artigo_id), None)


def ocupado(artigo_id):
    with _lock:
        return any(k[1] == artigo_id for k in _trabalhos)


def trabalhos_ativos():
    with _lock:
        return list(_trabalhos.keys())


def iniciar_download(artigo_id):
    if ocupado(artigo_id):
        return False
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        return False
    db.update_artigo(artigo_id, {"pdf_status": "baixando", "pdf_mensagem": "Looking for an open-access version (OpenAlex/arXiv/Unpaywall/Crossref)..."})

    def rodar():
        _registrar("download", artigo_id)
        sucesso = False
        try:
            resultado = downloader.baixar_pdf(artigo)
            if not resultado["ok"] and resultado.get("motivo") == "sem_url":
                db.update_artigo(artigo_id, {"pdf_status": "nao_disponivel"})
            else:
                sucesso = bool(resultado.get("ok"))
        except Exception as e:
            db.update_artigo(artigo_id, {"pdf_status": "falha", "pdf_mensagem": f"{type(e).__name__}: {str(e)[:200]}"})
        finally:
            _finalizar("download", artigo_id)
        if sucesso:
            iniciar_resumo(artigo_id)

    threading.Thread(target=rodar, daemon=True).start()
    return True


def iniciar_resumo(artigo_id):
    if ocupado(artigo_id):
        return False
    artigo = db.get_artigo(artigo_id)
    if not artigo:
        return False
    db.update_artigo(artigo_id, {"resumo_status": "processando", "resumo_mensagem": "Extracting text and summarizing..."})

    def rodar():
        _registrar("resumo", artigo_id)
        try:
            summarizer.resumir_artigo(artigo, progresso=None)
        except Exception as e:
            logging.error("Resumo falhou no artigo %s: %s", artigo_id, e, exc_info=True)
            db.update_artigo(artigo_id, {"resumo_status": "falha", "resumo_mensagem": f"{type(e).__name__}: {str(e)[:200]}"})
        finally:
            _finalizar("resumo", artigo_id)

    threading.Thread(target=rodar, daemon=True).start()
    return True


def iniciar_pull_modelo(modelo):
    def rodar():
        _registrar("modelo", modelo)
        try:
            summarizer.baixar_modelo(modelo)
        finally:
            _finalizar("modelo", modelo)

    threading.Thread(target=rodar, daemon=True).start()
    return True
