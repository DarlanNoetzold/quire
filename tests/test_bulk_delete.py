import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from app import api, db


class BulkDeleteTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_patch = patch("app.db.DB_PATH", os.path.join(self.tempdir.name, "bulk-delete.db"))
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
            start = next(message for message in sent if message["type"] == "http.response.start")
            content = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
            return start["status"], json.loads(content)

        return asyncio.run(run())

    def test_bulk_delete_removes_selected_articles_and_their_pdfs(self):
        paths = []
        ids = []
        for title in ("Delete A", "Delete B"):
            pdf_path = os.path.join(self.tempdir.name, title.replace(" ", "_") + ".pdf")
            with open(pdf_path, "wb") as pdf:
                pdf.write(b"%PDF-1.4\\n%%EOF")
            paths.append(pdf_path)
            ids.append(db.add_artigo({"fonte": "manual", "titulo": title, "caminho_pdf": pdf_path})["id"])
        keep = db.add_artigo({"fonte": "manual", "titulo": "Keep this"})

        status, result = self.request("DELETE", "/api/artigos", {"ids": ids})

        self.assertEqual(status, 200)
        self.assertEqual(result, {"ok": True, "deleted": 2})
        self.assertIsNone(db.get_artigo(ids[0]))
        self.assertIsNone(db.get_artigo(ids[1]))
        self.assertIsNotNone(db.get_artigo(keep["id"]))
        self.assertFalse(any(os.path.exists(path) for path in paths))

    def test_bulk_delete_requires_a_nonempty_list_of_integer_ids(self):
        for body in ({}, {"ids": []}, {"ids": ["all"]}):
            with self.subTest(body=body):
                status, response = self.request("DELETE", "/api/artigos", body)
                self.assertEqual(status, 400)
                self.assertIn("ids", response["detail"])
