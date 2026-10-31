import csv
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from app import review


class ReviewExtractionTests(unittest.TestCase):
    def test_extracts_explicit_numeric_values_and_units_from_summary(self):
        summary = {
            "results": "Accuracy improved to 92.5% on Dataset-X (n=120 participants). Runtime was 1,250 ms.",
            "methodology": "We evaluated 10-fold cross-validation.",
        }

        values = review.extract_numeric_evidence(summary)

        self.assertEqual(
            [(v["valor"], v["unidade"]) for v in values],
            [(92.5, "%"), (120, "participants"), (1250, "ms"), (10, "folds")],
        )
        self.assertTrue(all(v["evidencia"] for v in values))

    def test_does_not_duplicate_the_same_number_from_multiple_fields(self):
        values = review.extract_numeric_evidence({"results": "Accuracy was 92.5%.", "contributions": "Accuracy was 92.5%."})
        self.assertEqual(len(values), 1)

    def test_rejects_non_finite_or_unreasonably_large_numbers(self):
        values = review.extract_numeric_evidence({"results": "Score was 1e999 and count was 999999999999999."})
        self.assertEqual(values, [])


class ReviewPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "review.db")
        self.db_patch = patch("app.db.DB_PATH", self.db_path)
        self.db_patch.start()
        from app import db
        db.init_db()
        self.db = db

    def tearDown(self):
        self.db_patch.stop()
        self.tmp.cleanup()

    def article(self, title, summary):
        return self.db.add_artigo({
            "fonte": "manual", "titulo": title, "resumo_status": "pronto",
            "resumo_llm": json.dumps({"results": summary}),
        })

    def test_review_selection_is_persisted_per_review_and_only_summarized_articles_listed(self):
        included = self.article("Included study", "Accuracy was 88%.")
        self.db.add_artigo({"fonte": "manual", "titulo": "Pending study"})
        review_id = self.db.criar_revisao("My review")

        saved = self.db.atualizar_selecao_revisao(review_id, included["id"], "included", "Matches criteria")
        available = self.db.listar_artigos_revisao()
        selections = self.db.listar_selecoes_revisao(review_id)

        self.assertEqual(saved["decisao"], "included")
        self.assertEqual([a["id"] for a in available], [included["id"]])
        self.assertEqual(selections[0]["motivo"], "Matches criteria")

    def test_numeric_extraction_can_be_edited_and_exported_as_csv(self):
        article = self.article("A study, with comma", "Accuracy was 88%.")
        review_id = self.db.criar_revisao("CSV review")
        self.db.atualizar_selecao_revisao(review_id, article["id"], "included", "")
        extraction = {
            "artigo_id": article["id"], "campo": "accuracy", "valor": 91.2,
            "unidade": "%", "evidencia": "Revised from full text, p. 5", "pagina": 5,
        }

        saved = self.db.salvar_extracoes_revisao(review_id, [extraction])
        rows = self.db.listar_extracoes_revisao(review_id)
        output = io.StringIO()
        review.write_csv(output, rows)
        parsed = list(csv.DictReader(io.StringIO(output.getvalue())))

        self.assertEqual(saved, 1)
        self.assertEqual(rows[0]["valor"], 91.2)
        self.assertEqual(rows[0]["pagina"], 5)
        self.assertEqual(parsed[0]["artigo"], "A study, with comma")
        self.assertEqual(parsed[0]["unidade"], "%")
