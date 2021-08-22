#!/usr/bin/env python3
# rdf-org.py ---
#
# Filename: zothelper.py
# Author: Fred Qi
# Created: 2021-08-11 17:29:25(+0800)
#
# Last-Updated: 2021-08-22 20:05:35(+0800) [by Fred Qi]
#     Update #: 1309
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
import xml.etree.ElementTree as ET


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


def merge_duplicate_collections(root, ns):
    """
    Remove collections that duplicate with existing ones.
    """
    colls_remove, colls_keep = {}, {}
    for coll in root.iterfind("z:Collection", ns):
        name = coll.find("dc:title", ns).text
        if name in colls_keep:
            colls_remove[name].append(coll)
        else:
            colls_keep[name] = coll
            colls_remove[name] = []

    rdf_res = f"{{{ns['rdf']}}}resource"
    for key in colls_keep.keys():
        coll_keep = colls_keep[key]
        items = coll_keep.findall("dcterms:hasPart", ns)
        item_ids = set([item.get(rdf_res) for item in items])
        for coll in colls_remove[key]:
            for item in coll.iterfind("dcterms:hasPart", ns):
                item_id = item.get(rdf_res)                
                if item_id not in item_ids:
                    if item_id.find("collection") >= 0:
                        continue
                    coll.remove(item)
                    coll_keep.append(item)
                    item_ids.add(item_id)
            root.remove(coll)


def remove_automatic_tags(root, ns):
    """Find and remove all automatic tags."""
    for bib in root.iterfind("bib:*", ns):
        atags = bib.findall("dc:subject/z:AutomaticTag/..", ns)
        for atag in atags:
            bib.remove(atag)


def simplify_keywords(root, ns):
    """Collect and simplify keywords."""
    rdf_about = f"{{{ns['rdf']}}}about"
    item_types = ["bib:*", "z:Attachment", "rdf:Description"]
    for item_type in item_types:
        for bib in root.iterfind(item_type, ns):
            item_id = bib.get(rdf_about)
            for tag in bib.findall("dc:subject", ns):
                keyword = tag.text.strip()
                if len(keyword) == 0:
                    bib.remove(tag)
                elif keyword[0] == '#' or keyword[0] == "_":
                    bib.remove(tag)
                elif len(keyword.split(" ")) > 2:
                    bib.remove(tag)


def remove_extra_info(root, ns):
    """Remove tex.ids in extra field."""
    item_types = ["bib:*", "z:Attachment", "rdf:Description"]
    for item_type in item_types:
        for bib in root.iterfind(item_type, ns):
            for desc in bib.iterfind("dc:description", ns):
                lines = desc.text.split("\n")
                ln = list(filter(lambda x: x.find("tex.ids") >= 0, lines))
                if len(ln) == 1 and len(lines) > 1:
                    lines.remove(ln[0])
                    desc.text = "\n".join(lines)
                else:
                    bib.remove(desc)
                

def get_linked_attachments(root, ns):
    """
    Get a list of attachments with linkMode=3,
    which indicates a remotely linked attachment.
    """
    atts = []
    for att in root.iterfind("z:Attachment", ns):
        link = att.find("z:linkMode", ns)
        if link is not None and link.text in ["3"]:
            atts.append(att)
    return atts


def remove_linked_attachments(root, atts, ns):
    """Remove linked attachments and related linkage."""
    rdf_about = f"{{{ns['rdf']}}}about"
    rdf_res = f"{{{ns['rdf']}}}resource"
    att_ids = set([att.get(rdf_about) for att in atts])    
    for bib in root.iterfind("bib:*", ns):
        att_to_remove = []
        for att in bib.findall('link:link', ns):
            att_id = att.get(rdf_res)
            if att_id in att_ids:
                att_to_remove.append(att)
        for att in att_to_remove:
            # print("DEL:", att.get(rdf_res))
            bib.remove(att)

    for att in atts:
        # print("DEL:", att.get(rdf_about))
        root.remove(att)


def get_jpaper_doi(elem, dc_id="dc:identifier",
                   ns={"dc": "http://purl.org/dc/elements/1.1/",
                       "bib": "http://purl.org/net/biblio#"}):
    """From an elem to obtain paper DOI."""
    ids = [x.text for x in elem.iterfind(dc_id, ns)]
    doi = next((x for x in ids if x.find("DOI") >= 0), None)
    return doi
        

def collect_journals(root, ns):
    """To update all journal information."""
    rdf_about = f"{{{ns['rdf']}}}about"
    dc_id = f"{{{ns['dc']}}}identifier"
    
    doi_map = {}
    for jnl in root.iterfind("bib:Journal", ns):
        doi = get_jpaper_doi(jnl)
        if doi:
            jnl_ref = jnl.get(rdf_about)
            doi_map[jnl_ref] = doi
    return doi_map
       

def collect_rdf_identifiers(root, ns):
    """Collect DOIs, ISBNs, or URLs from a Zotero RDF XML file."""
    rdf_about = f"{{{ns['rdf']}}}about"
    rdf_res = f"{{{ns['rdf']}}}resource"
    dc_id = f"{{{ns['dc']}}}identifier"

    # "bib:ConferenceProceedings", 1
    # "bib:Data", 1
    # "bib:Report", 3
    # "bib:BookSection", 
    item_tags = ["bib:Document", "bib:Thesis"]
    id_keys = ['DOI', 'ISBN', 'ISSN']

    doi_map = collect_journals(root, ns)

    items = {}
    for item in root.iterfind("bib:Book", ns):        
        item_id = item.get(rdf_about, ns)
        ids = [x.text for x in item.iterfind("dc:identifier", ns)]
        item_id = next((x for x in ids if x.find("ISBN") >= 0), item_id)
        if item_id.find("#item") >= 0:
            item_id = item.find("dc:title", ns).text.strip()
        items[item_id] = item

    for item in root.iterfind("bib:Patent", ns):
        app_num = item.find("z:applicationNumber", ns)
        if app_num:
            item_id = app_num.text.strip()
        else:
            item_id = item.find("prism:number", ns).text.strip()
        items[item_id] = item

    dc_id = "bib:Journal/dc:identifier"
    dc_part = "dcterms:isPartOf"
    pidp = paperIDParser()
    for tag in ["bib:Article", "bib:BookSection", "rdf:Description"]:
        for item in root.iterfind(tag, ns):
            item_id = item.get(rdf_about, ns)
            jnl = item.find(dc_part, ns)
            if jnl is not None:
                jnl_ref = jnl.get(rdf_res)                
                doi = doi_map.get(jnl_ref, None) if jnl_ref else get_jpaper_doi(jnl, dc_id)
            if doi is not None:
                item_id = doi
            else:
                url_id = pidp.get_paper_id(item_id)
                if url_id is not None:
                    item_id = url_id
            if item_id.find("#item") < 0:
                items[item_id] = item
    return items

    
def collect_zotero_attachments(rdfname):
    """Get the set of attachments in zotero by parsing a rdf file."""
    ns = {'z': 'http://www.zotero.org/namespaces/export#',
          'bib': 'http://purl.org/net/biblio#',
          'link': 'http://purl.org/rss/1.0/modules/link/',
          'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'}

    rdf_res = f"{{{ns['rdf']}}}resource"
    root = ET.parse(rdfname).getroot()
    atts = []
    for att in root.iterfind("z:Attachment", ns):
        for res in att.iterfind("rdf:resource", ns):
            filepath = res.get(rdf_res).split(":")[-1]
            atts.append(filepath)
    # print("\n".join(atts))
    return atts


def reorganize_zotero():

    ns = {'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
          'z': "http://www.zotero.org/namespaces/export#",
          'dc': "http://purl.org/dc/elements/1.1/",
          'vcard': "http://nwalsh.com/rdf/vCard#",
          'foaf': "http://xmlns.com/foaf/0.1/",
          'bib': "http://purl.org/net/biblio#",
          'link': "http://purl.org/rss/1.0/modules/link/",
          'dcterms': "http://purl.org/dc/terms/",
          'prism': "http://prismstandard.org/namespaces/1.2/basic/"}

    xmlfile = "/home/fred/backup/zotdb/zoto/zoto.rdf"
    tree = ET.parse(xmlfile)
    root = tree.getroot()

    remove_automatic_tags(root, ns)
    simplify_keywords(root, ns)
    merge_duplicate_collections(root, ns)
    remove_extra_info(root, ns)
    
    atts = get_linked_attachments(root, ns)
    remove_linked_attachments(root, atts, ns)

    xmlfile = "/home/fred/backup/zotdb/zoto/zoto-updated.rdf"
    tree.write(xmlfile, encoding="UTF-8")


def simplify_zotero_rdf():

    ns = {'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
          'z': "http://www.zotero.org/namespaces/export#",
          'dc': "http://purl.org/dc/elements/1.1/",
          'vcard': "http://nwalsh.com/rdf/vCard#",
          'foaf': "http://xmlns.com/foaf/0.1/",
          'bib': "http://purl.org/net/biblio#",
          'link': "http://purl.org/rss/1.0/modules/link/",
          'dcterms': "http://purl.org/dc/terms/",
          'prism': "http://prismstandard.org/namespaces/1.2/basic/"}

    root = ET.parse("zotero.rdf").getroot()
    items = collect_rdf_identifiers(root, ns)

    tree_prev = ET.parse("zotero-prev.rdf")
    root_prev = tree_prev.getroot()
    items_prev = collect_rdf_identifiers(root_prev, ns)

    n_removed = 0
    for key, node in items_prev.items():
        if key in items:
            root_prev.remove(node)
            n_removed += 1

    xmlfile = "zotero-prev-simplified.rdf"
    tree_prev.write(xmlfile, encoding="UTF-8")
  
# 
# rdf-org.py ends here
