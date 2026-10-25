import unittest
from unittest.mock import patch

from app import sources


class SearchFilterTests(unittest.TestCase):
    def run_search(self, records, **filters):
        with patch.object(sources, "buscar_openalex", return_value=records):
            with patch.object(sources, "buscar_pubmed", return_value=[]), \
                 patch.object(sources, "buscar_doaj", return_value=[]), \
                 patch.object(sources, "buscar_europepmc", return_value=[]), \
                 patch.object(sources, "buscar_crossref", return_value=[]), \
                 patch.object(sources, "buscar_semanticscholar", return_value=[]), \
                 patch.object(sources, "buscar_dblp", return_value=[]), \
                 patch.object(sources, "buscar_hal", return_value=[]), \
                 patch.object(sources, "buscar_zenodo", return_value=[]), \
                 patch.object(sources, "buscar_openaire", return_value=[]), \
                 patch.object(sources, "buscar_plos", return_value=[]), \
                 patch.object(sources, "buscar_figshare", return_value=[]), \
                 patch.object(sources, "buscar_datacite", return_value=[]), \
                 patch.object(sources, "buscar_arxiv", return_value=[]), \
                 patch.object(sources, "buscar_openreview", return_value=[]), \
                 patch.object(sources, "buscar_osf", return_value=[]):
                return sources.buscar_tudo("climate", **filters)

    def test_author_filter_matches_case_insensitively(self):
        records = [
            {"titulo": "Paper A", "autores": ["Jane Doe"], "ano": 2022},
            {"titulo": "Paper B", "autores": ["John Smith"], "ano": 2022},
        ]
        result = self.run_search(records, autor="jane doe")
        self.assertEqual([r["titulo"] for r in result], ["Paper A"])

    def test_advanced_filters_match_type_subject_and_min_citations(self):
        records = [
            {"titulo": "A", "autores": [], "ano": 2022, "tipo_origem": "artigo_periodico", "classificacao": "Computer Science", "citacoes": 12, "idioma": "en", "acesso_aberto": True},
            {"titulo": "B", "autores": [], "ano": 2022, "tipo_origem": "preprint", "classificacao": "Computer Science", "citacoes": 20, "idioma": "en", "acesso_aberto": True},
        ]
        result = self.run_search(records, tipo_origem="artigo_periodico", assunto="computer science", citacoes_min=10)
        self.assertEqual([r["titulo"] for r in result], ["A"])

    def test_deduplicacao_can_be_disabled(self):
        records = [
            {"titulo": "Same Paper", "doi": "10.1234/test", "autores": []},
            {"titulo": "Same Paper", "doi": "10.1234/test", "autores": []},
        ]
        result = self.run_search(records, deduplicar=False)
        self.assertEqual(len(result), 2)

    def test_deduplicacao_is_enabled_by_default_and_keeps_pdf(self):
        records = [
            {"titulo": "Same Paper", "doi": "https://doi.org/10.1234/TEST", "autores": [], "url_pdf": "", "urls_alternativas": []},
            {"titulo": "Same Paper", "doi": "10.1234/test", "autores": [], "url_pdf": "https://example.test/paper.pdf", "urls_alternativas": []},
        ]
        result = self.run_search(records)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["url_pdf"], "https://example.test/paper.pdf")

    def test_type_filter_is_applied_after_aggregating_sources(self):
        records = [
            {"titulo": "Journal", "autores": [], "tipo_origem": "artigo_periodico"},
            {"titulo": "Preprint", "autores": [], "tipo_origem": "preprint"},
        ]
        result = self.run_search(records, tipo_origem="artigo_periodico")
        self.assertEqual([r["titulo"] for r in result], ["Journal"])


if __name__ == "__main__":
    unittest.main()