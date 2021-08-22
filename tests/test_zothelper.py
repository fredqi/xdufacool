# test_zothelper.py ---
#
# Filename: test_zothelper.py
# Author: Fred Qi
# Created: 2021-08-22 18:32:58(+0800)
#
# Last-Updated: 2021-08-22 19:23:10(+0800) [by Fred Qi]
#     Update #: 71
# 

# Commentary:
#
#
# 

# Change Log:
#
#
#

from unittest import TestCase
from xdufacool.zothelper import paperIDParser


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

        


# 
# test_zothelper.py ends here
