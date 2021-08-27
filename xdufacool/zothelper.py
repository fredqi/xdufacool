#!/usr/bin/env python3
# rdf-org.py ---
#
# Filename: zothelper.py
# Author: Fred Qi
# Created: 2021-08-11 17:29:25(+0800)
#
# Last-Updated: 2021-08-27 14:31:43(+0800) [by Fred Qi]
#     Update #: 2125
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
        
        pubid_pattern = "^\s*(?P<pubid_type>doi|issn|isbn).+$"
        self.pubid_parser = re.compile(pubid_pattern, re.I)

    def get_paper_id(self, text):
        """Obtain arxiv paper id from a given string."""
        pubid = {}
        is_uri = self.url_parser.match(text)
        if not is_uri:
            m = self.pubid_parser.match(text)
            if m:
                key = m.group("pubid_type").lower()
                pubid[key] = text.strip()
        else:
            domain, content = is_uri.group('domain'), is_uri.group('content')
            if domain in self.parsers:
                pm = self.parsers[domain].search(content)
                if pm:
                    pubid["uri"] = domain + " " + pm.group('paper_id')
        return pubid


class EntryParser(object):
    """Convert a xml tag to its abbreviation form according to namespace."""
    
    def __init__(self, filename):
        tag_ns_pattern = "^\{(?P<tag_ns>[\w\-:/\.#]+)\}(?P<tag>\w+)$"
        self.tag_parser = re.compile(tag_ns_pattern)
        pubid_pattern = "^\s*(?P<pubid_type>doi|issn|isbn).+$"
        self.pubid_parser = re.compile(pubid_pattern, re.I)
        self.nsmap = EntryParser.get_xml_namespaces(filename)
        self.insmap = dict([(v, k) for k, v in self.nsmap.items()])
       
        rdf_ns = self.nsmap['rdf']
        self.rdf_res = f"{{{rdf_ns}}}resource"
        self.rdf_about = f"{{{rdf_ns}}}about"
        self.dc_uri = "dcterms:URI"
        self.dc_ispart = "dcterms:isPartOf"
        self.dc_haspart = "dcterms:hasPart"

        self.paper_id_parser = paperIDParser()
        
        self.fields_pub = {"bib:Journal": {"dc:title": "journalTitle",
                                           "prism:volume": "volume",
                                           "prism:number": "number"},
                           "bib:Book": {"dc:title": "bookTitle"},
                           "bib:Series": {"dc:title": "seriesTitle",
                                          "dc:identifier": "seriesNumber"}}        
        # self.journal_fields = {"dc:title": "journalTitle",
        #                        "prism:volume": "volume", "prism:number": "number"}
        # self.book_fields = {"dc:title": "bookTitle", "dc:identifier": "isbn"}
        # self.series_fields = {"dc:title": "seriesTitle", "dc:identifier": "seriesNumber"}
        self.fields = { "z:itemType": "entryType", "dc:title": "title",
                        "dcterms:abstract": "abstract",
                        "foaf:name": "publisher",
                        "bib:pages": "pages", "dc:date": "date"}
        self.fields_creators = {"bib:authors": "authors", "bib:editors": "editors"}
        self.name_parts = {"foaf:surname": "surname", "foaf:givenName": "givenName"}
        self.non_entry = set(["bib:Journal", "z:Attachment", "z:Collection"])
        
        self.journals = {}
        self.attachments = {}

    @staticmethod
    def get_xml_namespaces(filename):
        namespaces = []
        for _, value in ET.iterparse(filename, events=['start-ns']):
            namespaces.append(value)
        return dict(namespaces)

    def get_abbrev_tag(self, tag):
        m = self.tag_parser.match(tag)
        if m is None:
            return None
        tag_ns = m.group('tag_ns')
        return self.insmap[tag_ns] + ':' + m.group('tag')

    def get_xml_tag(self, elem, tag_name):
        """Get tag text."""
        value = None
        tag = elem.find(tag_name, self.nsmap)
        value = tag.text.strip()
        return value

    def parse_node(self, node, fields,
                   fields_seq={"link:link": "links", "dc:subject": "keywords"}):
        """Extract fields from flatten leaves of the given node."""

        def update_seq(entry, key, value):
            entry[key] = entry.get(key, []) + [value]
            
        entity, children = {}, []
        for item in node:
            tag = self.get_abbrev_tag(item.tag)
            if not item.text:
                if tag in fields_seq:
                    key, link = fields_seq[tag], item.get(self.rdf_res)
                    update_seq(entity, key, link)
                else:
                    children.append(item) # dcterms:isPartOf with children
            elif not item.text.strip():
                children.append(item) # authors and publisher
            elif tag in fields:
                key = fields[tag]
                entity[key] = item.text.strip()
            elif tag in fields_seq:
                key = fields_seq[tag]
                update_seq(entity, key, item.text.strip())
            elif "dc:identifier" == tag:
                children.append(item) # pubid special treatment
        return entity, children

    # def parse_fields(self, elem):
    #     entry = {}
    #     for node in elem:
    #         tag_abbrev = self.get_abbrev_tag(node.tag)
    #         if tag_abbrev in self.fields:
    #             key = self.fields[tag_abbrev]
    #             entry[key] = node.text.strip()
    #         if tag_abbrev in self.fields_creators:
    #             key = self.fields_creators[tag_abbrev]
    #             entry[key] = self.get_creators(node)
    #     return entry

    def get_creators(self, elem):
        """Get creators of the given entry."""
        creators = []
        for node in elem.iter():
            tag = self.get_abbrev_tag(node.tag)
            if "foaf:Person" == tag:
                person, _ = self.parse_node(node, self.name_parts)
                creators.append(person)
        return creators

    def get_pubid(self, node):
        pubid = {}
        if node.text and node.text.strip():
            item = self.paper_id_parser.get_paper_id(node.text)
            pubid.update(item if item else {})
        else:
            for sn in node.iterfind(f"{self.dc_uri}/rdf:value", self.nsmap):
                item = self.paper_id_parser.get_paper_id(sn.text)
                pubid.update(item if item else {})
        return pubid
    
    # def get_publication_ids(self, id_elems):
    #     """To obtain publication IDs, such as DOI, ISSN, ISBN, etc, from a
    #     given element.

    #     """
    #     ids = {}
    #     for item in id_elems:
    #         m = self.pubid_parser.match(item.text)
    #         if m:
    #             key = m.group("pubid_type").lower()
    #             ids[key] = item.text.strip()
    #     return ids

    def get_publication(self, elem, fields):
        """Get a publication."""
        pub, id_nodes = self.parse_node(elem, fields)
        nodes_left = []
        for item in id_nodes:
            tag = self.get_abbrev_tag(item.tag)
            if "dc:identifier" == tag:
                pub.update(self.get_pubid(item))
            else:
                nodes_left.append(item)
        return pub, nodes_left                                    
        
    # def get_journal(self, elem):
    #     """Collect information of all journals."""
    #     journal, id_nodes = self.parse_node(elem, self.journal_fields)
    #     for sn in id_nodes:
    #         journal.update(self.get_pubid(sn))
    #     return journal

    # def get_book(self, elem):
    #     book, id_nodes = self.parse_node(elem, self.book_fields)
    #     # Search series
    #     while id_nodes:
    #         node = id_nodes.pop()
    #         tag = self.get_abbrev_tag(node.tag)
    #         if "bib:Series" == tag:
    #             series, _ = self.parse_node(node, self.series_fields)
    #             book.update(series)
    #         else:
    #             id_nodes.extend([sn for sn in node])
    #     return book

    def get_entry(self, elem):
        entry, nodes = self.parse_node(elem, self.fields)
        while nodes:
            node = nodes.pop()
            tag = self.get_abbrev_tag(node.tag)
            if tag in self.fields_pub:
                pub, nodes_left = self.get_publication(node, self.fields_pub[tag])
                entry.update(pub)
                nodes.extend(nodes_left)
            elif "dc:identifier" == tag:
                entry.update(self.get_pubid(node))
            elif "dc:subject" == tag:
                if "keywords" not in entry:
                    entry["keywords"] = []
                entry["keywords"].append(node.text)
            elif tag in self.fields_creators:
                creator_type = self.fields_creators[tag]
                entry[creator_type] = self.get_creators(node)
            elif self.dc_ispart == tag:
                jref_id = node.get(self.rdf_res)
                if jref_id in self.journals:
                    entry.update(self.journals[jref_id])
                else:
                    nodes.extend([sn for sn in node])
        # keys = ["doi", "isbn", "issn", "uri"]
        # print(" ".join([entry.get(key, "") for key in keys]))
        return entry

    def collect_journals(self, rdf_root):
        """Collect all journals in the given RDF file."""
        for elem in rdf_root.iterfind("bib:Journal", self.nsmap):
            jnl_ref = elem.get(self.rdf_about)
            journal, _ = self.get_publication(elem, self.fields_pub["bib:Journal"])
            self.journals[jnl_ref] = journal
            
    def collect_attachments(self, rdf_root):
        """Collect all attachments in the given RDF file."""
        for item in rdf_root.iterfind("z:Attachment", self.nsmap):
            att_ref = item.get(self.rdf_about)
            entry = self.get_entry(item)
            self.attachments[att_ref] = entry
       
    def get_all_entries(self, rdf_root):
        """Get all entries in a given RDF XML tree."""
        if not self.journals:
            self.collect_journals(rdf_root)
        if not self.attachments:
            self.collect_attachments(rdf_root)

        entries = []
        for item in rdf_root:
            tag = self.get_abbrev_tag(item.tag)
            if tag not in self.non_entry:
                entry = self.get_entry(item)
                entries.append(entry)
        return entries


class ZoteroRDFParser(object):
    """To parse a zotero xml RDF file."""

    def __init__(self):
        # self._tree = None
        # self._root = None
        # self.tag_abbrev = None
        # self.articles = {}
        # self.attachments = {}
        self.entries = None

    def load(self, filename):
        self._tree = ET.parse(filename)
        self._root = self._tree.getroot()
        self.tag_abbrev = EntryParser(filename)

        entry_parser = EntryParser(filename)
        root = ET.parse(filename).getroot()
        self.entries = entry_parser.get_all_entries(root)

    def save(self, filename):
        pass
        

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
