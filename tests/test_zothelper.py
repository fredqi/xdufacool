# test_zothelper.py ---
#
# Filename: test_zothelper.py
# Author: Fred Qi
# Created: 2021-08-22 18:32:58(+0800)
#
# Last-Updated: 2021-08-25 21:08:34(+0800) [by Fred Qi]
#     Update #: 227
# 

# Commentary:
#
#
# 

# Change Log:
#
#
#

from pathlib import Path
from unittest import TestCase
from xml.etree import ElementTree as ET
from xdufacool.zothelper import paperIDParser
from xdufacool.zothelper import EntryParser
from xdufacool.zothelper import ZoteroRDFParser


DATA_PATH = Path(__file__).resolve().parent
RDF_FILEPATH = DATA_PATH.joinpath("data", "zotero.rdf")


class TestPaperIdParser(TestCase):

    def setUp(self):
        self.pidp = paperIDParser()

    def test_arxiv(self):
        arxiv_urls = ["http://arxiv.org/abs/2003.12565",
                      "https://arxiv.org/abs/1602.00991v2",
                      "https://arxiv.org/pdf/1907.01869.pdf"]
        arxiv_ids = ["2003.12565", "1602.00991", "1907.01869"]
        arxiv_ids = ["arxiv " + theid for theid in arxiv_ids]

        for url, paper_id in zip(arxiv_urls, arxiv_ids):
            paper_id_ret = self.pidp.get_paper_id(url)
            self.assertEqual(paper_id, paper_id_ret,
                             msg=f"Erorr parsing arXiv URL {url}")


    def test_sciencedirect(self):
        sd_urls = ["https://www.sciencedirect.com/science/article/pii/S1361841518308430",
                   "http://www.sciencedirect.com/science/article/pii/S107731421300091X"]
        sd_ids = ["S1361841518308430", "S107731421300091X"]
        sd_ids = ["sciencedirect " + theid for theid in sd_ids]

        for url, paper_id in zip(sd_urls, sd_ids):
            paper_id_ret = self.pidp.get_paper_id(url)
            self.assertEqual(paper_id, paper_id_ret,
                             msg=f"Erorr parsing ScienceDirect URL {url}")

    def test_springer(self):
        springer_urls = ["http://link.springer.com/chapter/10.1007/978-3-319-10602-1_9",
                         "http://link.springer.com/article/10.1007/s11263-011-0489-0",
                         "http://link.springer.com/article/10.1023/B%3AJMIV.0000011325.36760.1e",
                         "https://link.springer.com/article/10.1007/s11042-015-3114-3"]
        springer_ids = ["10.1007/978-3-319-10602-1_9", "10.1007/s11263-011-0489-0",
                        "10.1023/B%3AJMIV.0000011325.36760.1e",
                        "10.1007/s11042-015-3114-3"]
        springer_ids = ["springer " + doi for doi in springer_ids]

        for url, paper_id in zip(springer_urls, springer_ids):
            paper_id_ret = self.pidp.get_paper_id(url)
            self.assertEqual(paper_id, paper_id_ret,
                             msg=f"Erorr parsing SpringerLink URL {url}")

    def test_dois(self):
        doi_urls = ["https://www.worldscientific.com/doi/abs/10.1142/S0129065718500594",
                    "http://www.worldscientific.com/doi/abs/10.1142/S012906579100011X",
                    "http://onlinelibrary.wiley.com/doi/10.1002/wcs.142/abstract",
                    "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2015JD024722",
                    "https://onlinelibrary.wiley.com/doi/abs/10.1002/widm.1249",
                    "https://physoc.onlinelibrary.wiley.com/doi/abs/10.1113/jphysiol.1962.sp006837",
                    "https://epubs.siam.org/doi/abs/10.1137/070698014",
                    "http://epubs.siam.org/doi/abs/10.1137/S0097539792240406",
                    "http://doi.acm.org/10.1145/1390156.1390177",
                    "http://doi.acm.org/10.1145/3363294",
                    "http://link.aps.org/doi/10.1103/PhysRevE.90.012118",
                    "https://link.aps.org/doi/10.1103/PhysRevD.101.075042",
                    "https://doi.org/10.1023/A:1008078328650",
                    "https://doi.org/10.1186/s41476-017-0070-8",
                    "http://dx.doi.org/10.1371/journal.pone.0116312",
                    "https://doi.org/10.5194/isprs-annals-IV-3-149-2018"]
                    
        dois = ["worldscientific 10.1142/S0129065718500594",
                "worldscientific 10.1142/S012906579100011X",
                "wiley 10.1002/wcs.142", "wiley 10.1002/2015JD024722",
                "wiley 10.1002/widm.1249", "wiley 10.1113/jphysiol.1962.sp006837",
                "siam 10.1137/070698014", "siam 10.1137/S0097539792240406",
                "acm 10.1145/1390156.1390177", "acm 10.1145/3363294",
                "aps 10.1103/PhysRevE.90.012118", "aps 10.1103/PhysRevD.101.075042",
                "doi 10.1023/A:1008078328650", "doi 10.1186/s41476-017-0070-8",
                "doi 10.1371/journal.pone.0116312","doi 10.5194/isprs-annals-IV-3-149-2018"]

        for url, paper_id in zip(doi_urls, dois):
            paper_id_ret = self.pidp.get_paper_id(url)
            self.assertEqual(paper_id, paper_id_ret,
                             msg=f"Erorr parsing DOI-based URL {url}")

    def test_thecvf(self):
        cvf_urls = ["https://openaccess.thecvf.com/content/CVPR2021/html/Wang_Transformer_Meets_Tracker_Exploiting_Temporal_Context_for_Robust_Visual_Tracking_CVPR_2021_paper.html",
         "https://openaccess.thecvf.com/content_iccv_2015/html/Tang_Multi-Kernel_Correlation_Filter_ICCV_2015_paper.html",
         "https://openaccess.thecvf.com/content_iccv_2015_workshops/w14/html/Bibi_Multi-Template_Scale-Adaptive_Kernelized_ICCV_2015_paper.html"]
        cvf_ids = ["thecvf Wang_Transformer_Meets_Tracker_Exploiting_Temporal_Context_for_Robust_Visual_Tracking_CVPR_2021",
                   "thecvf Tang_Multi-Kernel_Correlation_Filter_ICCV_2015",
                   "thecvf Bibi_Multi-Template_Scale-Adaptive_Kernelized_ICCV_2015"]

        for url, paper_id in zip(cvf_urls, cvf_ids):
            paper_id_ret = self.pidp.get_paper_id(url)
            self.assertEqual(paper_id, paper_id_ret,
                             msg=f"Erorr parsing DOI-based URL {url}")


    def test_neurips(self):
        neurips_urls = ["https://proceedings.neurips.cc/paper/2018/file/5e62d03aec0d17facfc5355dd90d441c-Paper.pdf",
                        "https://proceedings.neurips.cc/paper/2019/hash/54229abfcfa5649e7003b83dd4755294-Abstract.html",
                        "https://proceedings.neurips.cc/paper/2020/file/8965f76632d7672e7d3cf29c87ecaa0c-Paper.pdf",
                        "http://papers.nips.cc/paper/5423-generative-adversarial-nets.pdf",
                        "http://papers.nips.cc/paper/7033-dual-path-networks",
                        "https://papers.nips.cc/paper/6111-learning-what-and-where-to-draw"
        ]
        neurips_ids = ["neurips 5e62d03aec0d17facfc5355dd90d441c",
                       "neurips 54229abfcfa5649e7003b83dd4755294",
                       "neurips 8965f76632d7672e7d3cf29c87ecaa0c",
                       "nips 5423-generative-adversarial-nets",
                       "nips 7033-dual-path-networks", "nips 6111-learning-what-and-where-to-draw"]

        for url, paper_id in zip(neurips_urls, neurips_ids):
            paper_id_ret = self.pidp.get_paper_id(url)
            self.assertEqual(paper_id, paper_id_ret,
                             msg=f"Erorr parsing DOI-based URL {url}")



class TestEntryParser(TestCase):

    def setUp(self):
        self.entry_parser = EntryParser(RDF_FILEPATH)
        self.root = ET.parse(RDF_FILEPATH).getroot()
    
    def test_namespace(self):
        ns = {'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
              'z': "http://www.zotero.org/namespaces/export#",
              'dc': "http://purl.org/dc/elements/1.1/",
              'vcard': "http://nwalsh.com/rdf/vCard#",
              'foaf': "http://xmlns.com/foaf/0.1/",
              'bib': "http://purl.org/net/biblio#",
              'link': "http://purl.org/rss/1.0/modules/link/",
              'dcterms': "http://purl.org/dc/terms/",
              'prism': "http://prismstandard.org/namespaces/1.2/basic/"}

        nsmap = EntryParser.get_xml_namespaces(RDF_FILEPATH)

        for key, value in nsmap.items():
            self.assertIn(key, ns,
                          msg=f"Namespace {key} is not found.")
            self.assertEqual(value, nsmap[key],
                             msg=f"Namespace URL is not equal to {value}.")

    def test_abbrev_tag(self):
        tags = ["{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description",
                "{http://purl.org/net/biblio#}BookSection",
                "{http://purl.org/net/biblio#}Journal",
                "{http://purl.org/net/biblio#}Article",
                "{http://www.zotero.org/namespaces/export#}Attachment"]
        tag_refs = ["rdf:Description",
                    "bib:BookSection", "bib:Journal", "bib:Article",
                    "z:Attachment"]

        for tag, tag_ref in zip(tags, tag_refs):
            tag_abbrev = self.entry_parser.get_abbrev_tag(tag)
            self.assertEqual(tag_ref, tag_abbrev,
                             msg=f"Abbrevation of {tag} is incorrect.")

    def test_get_journal_paper(self):
        entry_ref = {"title": "Res2Net: A New Multi-Scale Backbone Architecture",
                     "date": "2021-02", "pages": "652-662"}
        self.entry_parser.collect_journals(self.root)
        node = self.root.find("bib:Article", self.entry_parser.nsmap)
        entry = self.entry_parser.get_entry(node)
        for key, value in entry_ref.items():
            self.assertIn(key, entry, msg=f"Field {key} has not been extracted.")
            self.assertEqual(value, entry[key], msg=f"Field {key} is incorrect.")

    def test_get_booksection(self):
        entry_ref = {"title": "Visualizing and Understanding Convolutional Networks",
                     "date": "2014/09/06", "pages": "818-833"}
        node = self.root.find("bib:BookSection", self.entry_parser.nsmap)
        entry = self.entry_parser.get_entry(node)
        for key, value in entry_ref.items():
            self.assertIn(key, entry, msg=f"Field {key} has not been extracted.")
            self.assertEqual(value, entry[key], msg=f"Field {key} is incorrect.")

    def test_get_rdfdesc(self):
        entry_ref = {"title": "VoxelNet: End-to-End Learning for Point Cloud Based 3D Object Detection",
                     "date": "June 2018"}
        node = self.root.find("rdf:Description", self.entry_parser.nsmap)
        entry = self.entry_parser.get_entry(node)
        for key, value in entry_ref.items():
            self.assertIn(key, entry, msg=f"Field {key} has not been extracted.")
            self.assertEqual(value, entry[key], msg=f"Field {key} is incorrect.")

    def test_get_journal(self):
        jnl = self.root.find("bib:Journal", self.entry_parser.nsmap)
        journal = self.entry_parser.get_journal(jnl)
        journal_ref = {"journalTitle": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
                       "volume": "43", "number": "2",
                       "issn": "ISSN 1939-3539",
                       "doi": "DOI 10.1109/TPAMI.2019.2938758"}
        for key, value in journal_ref.items():
            self.assertIn(key, journal, msg=f"{key} has not been extracted.")
            self.assertEqual(journal[key], value, msg=f"{key} is incorrect.")

        jnl = self.root.find("rdf:Description/dcterms:isPartOf/bib:Journal", self.entry_parser.nsmap)
        title = self.entry_parser.get_xml_tag(jnl, "dc:title")
        self.assertEqual("The IEEE Conference on Computer Vision and Pattern Recognition (CVPR)",
                         title, msg="Title is incorrect")

    def test_collect_journals(self):
        self.entry_parser.collect_journals(self.root)
        jnls = self.entry_parser.journals
        self.assertEqual(len(jnls), 1, msg="Number of jounals is incorrect.")

    def test_get_creators(self):
        node = self.root.find("bib:Article/bib:authors", self.entry_parser.nsmap)
        authors = self.entry_parser.get_creators(node)
        # self.assertTrue(creators['editors'] == [], msg="There should be no editors.")
        self.assertEqual(len(authors), 6, msg="There are 6 authors.")

        author = authors[0]
        au_ref = {"surname": "Gao", "givenName": "Shang-Hua"}
        self.assertEqual(author, au_ref,
                         msg=f"The first author is {au_ref['givenName']} {au_ref['surname']}")

        author = authors[-1]
        au_ref = {"surname": "Torr", "givenName": "Philip"}
        self.assertEqual(author, au_ref,
                         msg=f"The last author is {au_ref['givenName']} {au_ref['surname']}")
            

class TestZoteroParser(TestCase):

    def setUp(self):
        self.rdf_parser = ZoteroRDFParser()

    def test_iteritem(self):
        ret = self.rdf_parser.load(RDF_FILEPATH)
        self.assertIsNotNone(ret, msg=f"Error loading {RDF_FILEPATH}.")

# 
# test_zothelper.py ends here
