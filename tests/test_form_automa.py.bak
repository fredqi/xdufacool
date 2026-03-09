# test_form_automa.py ---
#
# Filename: test_form_automa.py
# Author: Fred Qi
# Created: 2023-11-06 10:40:12(+0800)
#
# Last-Updated: 2023-11-06 13:54:19(+0800) [by Fred Qi]
#     Update #: 19
# 

# Commentary:
#
#
# 

# Change Log:
#
#
#
import os
import unittest
from xdufacool.form_automa import MarkdownDocxMerger


class TestMarkdownDocxMerger(unittest.TestCase):
    def setUp(self):
        self.merger = MarkdownDocxMerger('tests/data/forms.ini')

    def test_parse_frontmatter(self):
        metadata, _ = self.merger.parse_markdown('tests/data/forms.md')
        self.assertIn('学院', metadata)  # Replace 'title' with an actual metadata key

    def test_merge_document(self):
        # merged_doc_path =
        self.merger.generate_docx('tests/data/forms.md')
        # self.assertTrue(os.path.exists(merged_doc_path))


# 
# test_form_automa.py ends here
