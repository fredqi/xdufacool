from unittest import TestCase

from xdufacool.organize_bib import load_bibtex
from xdufacool.organize_bib import DOIParser
from xdufacool.organize_bib import JournalPatcher
from xdufacool.organize_bib import StringPatcher
from xdufacool.organize_bib import collect_ieee_titles
from xdufacool.organize_bib import extract_citation_keys


class TestBibExtraction(TestCase):

    def setUp(self):
        self.bibfile = 'tests/data/test.bib'
        self.auxfile = 'tests/data/component-inspection.aux'
        self.ieee_bibfile = 'tests/data/IEEEabrv.bib'

    def test_load_bibtex(self):
        bib_db = load_bibtex(self.bibfile)
        self.assertEqual(6, len(bib_db.entries),
                         "Count of BibTeX entries are NOT equal.")
        bib_ieee = load_bibtex(self.ieee_bibfile)
        self.assertEqual(263, len(bib_ieee.strings),
                         "Number of BibTeX string are NOT equal.")

    def test_parse_ieee_strings(self):
        test_data = [('10.1109/ACCESS', 'IEEE_O_ACC'),
                     ('10.1109/JPROC', 'IEEE_J_PROC'),
                     ('10.1109/TPAMI', 'IEEE_J_PAMI'),
                     ('10.1109/MIS', 'IEEE_M_IS')]

        bib_ieee = load_bibtex(self.ieee_bibfile)
        titles = collect_ieee_titles(bib_ieee.strings)
        for test_doi, test_key in test_data:
            self.assertTrue(test_doi in titles, f'Key {test_doi} not found.')
            key = titles[test_doi][0]
            self.assertEqual(key, test_key,
                             f'Line {test_key} has not been correctly parsed.')

    def test_parse_latex_aux(self):
        keys = extract_citation_keys(self.auxfile)
        test_keys = set(['xia_bottom-up_2016', 'qi_convolutional_2019', 'xia_nonlocal_2015'])
        intersetion = keys & test_keys
        self.assertEqual(intersetion, test_keys, "Some key are missing.")


class Test_DOIParser(TestCase):
    def setUp(self):
        self.doi_to_parse = ['10.1109/WCL.2013.101613.130587',
                             '10.1016/j.jvcir.2018.06.009',
                             '10.1109/ACCESS.2019.2915630',
                             '10.1109/TCSII.2016.2539079',
                             '10.1109/TGRS.2017.2753848']
        self.doi_keys = ['WCL', 'j.jvcir', 'ACCESS', 'TCSII', 'TGRS']

    def test_parse_doi(self):
        parser = DOIParser()
        for doi, key_ref in zip(self.doi_to_parse, self.doi_keys):
            prefix = parser.get_doi_key(doi)
            doi_key = prefix.split('/')[-1]
            self.assertEqual(doi_key, key_ref, f"Incorrect key for {doi}")


class TestJournalPatcher(TestCase):
    def setUp(self):
        self.journal = ' journaltitle = {IEEE_J_CASII},'
        self.journal_ref = ' journal = IEEE_J_CASII,'

    def test_patch(self):
        patcher = JournalPatcher()
        journal_patched = patcher.patch(self.journal)
        self.assertEqual(journal_patched, self.journal_ref,
                         "Failed to apply a patch.")


class TestStringPatcher(TestCase):
    def setUp(self):
        self.string = '\n@string{IEEE_J_IP = {{IEEE} Trans. Image Process.}}\n'
        self.string_ref = '@string{IEEE_J_IP = {{IEEE} Trans. Image Process.}}\n'

    def test_patch(self):
        patcher = StringPatcher()
        string_patched = patcher.patch(self.string)
        self.assertEqual(string_patched, self.string_ref,
                         "Failed to apply a patch.")
