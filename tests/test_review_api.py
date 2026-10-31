import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from app import api, db


class ReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_patch = patch("app.db.DB_PATH", os.path.join(self.tempdir.name, "api.db"))
        self.db_patch.start()
        db.init_db()

    def tearDown(self):
        self.db_patch.stop()
        self.tempdir.cleanup()

    def request(self, method, path, body=None):
        async def run():
            parsed = urlsplit(path)
            raw_body = json.dumps(body).encode() if body is not None else b""
            messages = [{"type": "http.request", "body": raw_body, "more_body": False}]
            sent = []

            async def receive():
                return messages.pop(0) if messages else {"type": "http.disconnect"}

            async def send(message):
                sent.append(message)

            await api.app({
                "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1", "method": method, "scheme": "http",
                "path": parsed.path, "raw_path": parsed.path.encode(),
                "query_string": parsed.query.encode(), "root_path": "",
                "headers": [(b"host", b"test"), (b"content-type", b"application/json")],
                "client": ("127.0.0.1", 12345), "server": ("test", 80),
            }, receive, send)
            start = next(m for m in sent if m["type"] == "http.response.start")
            content = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
            return start["status"], content

        status, content = asyncio.run(run())
        try:
            decoded = json.loads(content)
        except (TypeError, ValueError):
            decoded = content.decode()
        return status, decoded

    def test_review_workflow_includes_and_exports_a_summarized_article(self):
        article = db.add_artigo({
            "fonte": "manual", "titulo": "Study for review", "ano": 2024,
            "autores": "[]", "resumo_status": "pronto",
            "resumo_llm": '{"results":"Accuracy reached 91% (n=50 participants)."}',
        })

        status, created = self.request("POST", "/api/revisoes", {"titulo": "Review question"})
        self.assertEqual(status, 200)
        review_id = created["id"]
        status, listed = self.request("GET", "/api/revisao/artigos")
        self.assertEqual(status, 200)
        self.assertEqual([x["id"] for x in listed], [article["id"]])
        status, _ = self.request(
            "PUT", f"/api/revisoes/{review_id}/artigos/{article['id']}",
            {"decisao": "included", "motivo": "Meets criteria"},
        )
        self.assertEqual(status, 200)

        status, detected = self.request("POST", f"/api/revisoes/{review_id}/extracoes/detectar")
        self.assertEqual(status, 200)
        self.assertGreater(detected["salvas"], 0)
        status, detail = self.request("GET", f"/api/revisoes/{review_id}")
        self.assertEqual(status, 200)
        self.assertEqual(detail["estatisticas"]["included"], 1)
        self.assertTrue(any(e["unidade"] == "%" for e in detail["extracoes"]))
        self.assertTrue(detail["graficos"])
        status, csv_text = self.request("GET", f"/api/revisoes/{review_id}/csv")
        self.assertEqual(status, 200)
        self.assertIn("Study for review", csv_text)

    def test_available_articles_for_review_excludes_selected_and_keeps_other_summaries(self):
        selected = db.add_artigo({
            "fonte": "manual", "titulo": "Selected study", "resumo_status": "pronto",
            "resumo_llm": '{"results":"Selected"}',
        })
        available = db.add_artigo({
            "fonte": "manual", "titulo": "Available study", "resumo_status": "pronto",
            "resumo_llm": '{"results":"Available"}',
        })
        review_id = db.criar_revisao("Review")
        db.atualizar_selecao_revisao(review_id, selected["id"], "pending")

        status, listed = self.request("GET", f"/api/revisao/artigos?revisao_id={review_id}")

        self.assertEqual(status, 200)
        self.assertEqual([article["id"] for article in listed], [available["id"]])

    def test_pdf_reader_response_is_inline_not_download(self):
        pdf_path = os.path.join(self.tempdir.name, "reader.pdf")
        with open(pdf_path, "wb") as pdf:
            pdf.write(b"%PDF-1.4\\n%%EOF")
        article = db.add_artigo({
            "fonte": "manual", "titulo": "Readable PDF", "caminho_pdf": pdf_path,
            "pdf_status": "baixado",
        })

        response = api.abrir_pdf(article["id"])

        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(response.headers["content-disposition"].startswith("inline"))

    def test_review_rejects_article_without_ready_summary(self):
        article = db.add_artigo({"fonte": "manual", "titulo": "No summary"})
        review_id = db.criar_revisao("Review")

        status, response = self.request(
            "PUT", f"/api/revisoes/{review_id}/artigos/{article['id']}",
            {"decisao": "included"},
        )

        self.assertEqual(status, 400)
        self.assertIn("ready summary", response["detail"])
