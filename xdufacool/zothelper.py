#!/usr/bin/env python3
# rdf-org.py ---
#
# Filename: zothelper.py
# Author: Fred Qi
# Created: 2021-08-11 17:29:25(+0800)
#
# Last-Updated: 2021-08-22 19:28:44(+0800) [by Fred Qi]
#     Update #: 1287
# 

# Commentary:
#
#
# 

# Change Log:
#
#
#

import re


class paperIDParser(object):

    def __init__(self):
        """Initialize regular expression parsers for obtaining paper IDs."""
        url_patterns = "^(https?://)?([^\.]*\.)*(?P<domain>\w+)\.(org|com|cc)/(?P<content>.+)$"
        self.url_parser = re.compile(url_patterns, re.I)
        
        doi_pattern = "(?P<paper_id>10\.\d{4,9}/[^\s/]+)"
        patterns = {"arxiv": "(abs|pdf)/(?P<paper_id>\d{4,5}\.\d{4,5})v?\d?.*",
                    "sciencedirect": "[\w./]+/pii/(?P<paper_id>[SX\d]+)",
                    "worldscientific": f"doi/abs/{doi_pattern}",
                    "springer": f"(chapter|article)/{doi_pattern}",
                    "wiley": f"doi/?(abs|full)?/{doi_pattern}(/abstract)?",
                    "siam": f"doi/abs/{doi_pattern}",
                    "acm": f"{doi_pattern}",
                    "aps": f"doi/{doi_pattern}",
                    "doi": f"{doi_pattern}",
                    "thecvf": ".*/html/(?P<paper_id>.+)_paper.html",
                    "jmlr": "papers/(?P<paper_id>v\d+/\w+)\.html",
                    "nips": "paper/(?P<paper_id>\d{1,4}[a-z-]+)(.pdf)?",
                    "neurips": "paper/\d{4}/(hash|file)/(?P<paper_id>[0-9a-f]+)-\w+\.(pdf|html)" }
        self.parsers = dict([(k, re.compile(v)) for k, v in patterns.items()])
        
    def get_paper_id(self, url):
        """Obtain arxiv paper id from a given string."""
        m = self.url_parser.match(url)
        if not m:
            return None
        
        domain, content = m.group('domain'), m.group('content')
        if domain not in self.parsers:
            # print(domain, content)
            return None
        pm = self.parsers[domain].search(content)
        if pm is None:
            return None
        return domain + " " + pm.group('paper_id')
