import json
import unittest

from app import importer


class BibtexRisImporterTests(unittest.TestCase):
    def test_parse_bibtex_mendeley_entry(self):
        bib_content = """
        @article{Vaswani2017,
            title = {Attention Is All You Need},
            author = {Vaswani, Ashish and Shazeer, Noam and Parmar, Niki and Uszkoreit, Jakob},
            year = {2017},
            journal = {Advances in Neural Information Processing Systems},
            doi = {10.5555/3295222.3295349},
            url = {https://arxiv.org/abs/1706.03762},
            abstract = {The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.},
            keywords = {Attention, Transformer, Deep Learning},
            file = {:C\\:/Users/User/Mendeley/Vaswani2017.pdf:pdf}
        }
        """
        registros = importer.parse_bibtex(bib_content)
        self.assertEqual(len(registros), 1)
        r = registros[0]
        self.assertEqual(r["titulo"], "Attention Is All You Need")
        autores = json.loads(r["autores"])
        self.assertEqual(autores[0], "Ashish Vaswani")
        self.assertEqual(autores[1], "Noam Shazeer")
        self.assertEqual(r["ano"], 2017)
        self.assertEqual(r["doi"], "10.5555/3295222.3295349")
        self.assertEqual(r["classificacao"], "Advances in Neural Information Processing Systems")
        self.assertIn("Transformer", json.loads(r["tags"]))
        self.assertEqual(r["fonte"], "mendeley")

    def test_parse_ris_mendeley_entry(self):
        ris_content = """
TY  - JOUR
TI  - Deep Residual Learning for Image Recognition
AU  - He, Kaiming
AU  - Zhang, Xiangyu
AU  - Ren, Shaoqing
AU  - Sun, Jian
PY  - 2016
DO  - 10.1109/CVPR.2016.90
JO  - IEEE Conference on Computer Vision and Pattern Recognition
AB  - Deeper neural networks are more difficult to train.
KW  - ResNet
KW  - Computer Vision
UR  - https://doi.org/10.1109/CVPR.2016.90
ER  -
        """
        registros = importer.parse_ris(ris_content)
        self.assertEqual(len(registros), 1)
        r = registros[0]
        self.assertEqual(r["titulo"], "Deep Residual Learning for Image Recognition")
        autores = json.loads(r["autores"])
        self.assertEqual(autores[0], "Kaiming He")
        self.assertEqual(r["ano"], 2016)
        self.assertEqual(r["doi"], "10.1109/CVPR.2016.90")
        self.assertEqual(r["classificacao"], "IEEE Conference on Computer Vision and Pattern Recognition")
        self.assertIn("ResNet", json.loads(r["tags"]))


if __name__ == "__main__":
    unittest.main()
