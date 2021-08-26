# parse_bib.py ---
#
# Filename: organize_bib.py
# Author: Fred Qi
# Created: 2020-03-26 00:45:19(+0800)
#
# Last-Updated: 2020-04-05 17:15:10(+0800) [by Fred Qi]
#     Update #: 477
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
import yaml
from yaml import Loader
from collections import OrderedDict

import shutil
from pathlib import Path

import argparse

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bibdatabase import BibDatabase


def load_bibtex(filename):
    parser = BibTexParser(ignore_nonstandard_types=False,
                          homogenize_fields=False,
                          common_strings=True)

    with open(filename) as bibfile:
        bib_database = bibtexparser.load(bibfile, parser)
        return bib_database


def entry_to_annotation(entry, PI):
    annotation = {'ackpage': [1]}
    annotation['ID'] = entry['ID']
    annotation['type'] = entry['ENTRYTYPE']
    annotation['title'] = entry['title']
    authors = [author.strip() for author in entry['author'].split('and')]
    try:
        idx = authors.index(PI)
        annotation['author_an'] = f'{idx+1}:family=corresponding;{idx+1}=self'
        annotation['label'] = 'masterpiece'
    except ValueError:
        print(f'{entry["ID"]}:\n    {PI} has not been found in the list of authors.')

    annotation['author'] = '; '.join(authors)
    annotation['file'] = entry['file'].split(':')[0]
    return annotation


def update_file(entry):
    if 'file' in entry:
        fields = entry['file'].split(':')
        if Path(fields[1]).is_file():
            shutil.copyfile(fields[1], fields[0])
            fields[1] = str(fields[0])
            entry['file'] = ':'.join(fields)        
    return entry


def gen_metadata(args):
    """Generate metadata and store them in a YAML file with given arguments."""
    with open(args.bibfile) as bibfile:
        bib_db = BibTexParser(common_strings=True).parse_file(bibfile)
        entries = sorted(list(bib_db.entries),
                         key=lambda x: x['year'], reverse=True)
        list([update_file(entry) for entry in entries])
        annotations = [entry_to_annotation(entry, args.PI) for entry in entries]
        stream = open(args.metadata, 'w')
        yaml.dump(annotations, stream, width=192, default_flow_style=False)
        stream.close()


def gen_attachments(args):
    """Generate attachments for uploading to NSFC website."""
    bash_header = '#!/usr/bin/env bash'
    gs_options = ' '.join(['-dNOPAUSE', '-dBATCH',
                           '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.5',
                           '-dPDFSETTINGS=/ebook'])
    shrink_pdf = ['# Ref: https://www.techwalla.com/articles/reduce-pdf-file-size-linux', '\n',
                  'shrink_pdf()', '\n{\n',
                  f'  OPTIONS="{gs_options}"', '\n',
                  '  echo "Shrinking $1..."', '\n',
                  '  gs $OPTIONS -sOutputFile=$FOLDER/$1 $1', '\n',
                  '}\n\n']
    bash_lines = [bash_header, '\n\n',
                  'FOLDER="attachments"', '\n\n',
                  '[[ -d $FOLDER ]] || mkdir $FOLDER', '\n\n']
    bash_lines += shrink_pdf
    convertion_lines = []
    input_specs, output_specs = [], []
    with open(args.metadata, 'r') as stream:
        metadata = yaml.load(stream, Loader=Loader)
        for item in metadata:
            filename = item.get('file')
            if item.get('label', None) == 'masterpiece':
                # line = f'pdf2ps {filename} - | ps2pdf - $FOLDER/{filename}\n'
                line = f'shrink_pdf {filename}\n'
                convertion_lines.append(line)
            else:
                att_symbol = chr(ord('A') + len(input_specs))
                pages = item.get('ackpage', [])
                input_specs.append(f'      {att_symbol}={filename} \\\n')
                output_specs += [f'{att_symbol}{page}' for page in pages]

    # print(output_specs)
    if input_specs:
        input_specs[0] = 'pdftk ' + input_specs[0].strip() + '\n'
        output_lines = ['      cat ', ' '.join(output_specs),
                        ' output attachments.pdf', '\n\n',
                        'shrink_pdf attachments.pdf\n']
    else:
        output_lines = []
    # 'pdf2ps $FOLDER/attach-large.pdf - | ps2pdf - $FOLDER/attachments.pdf\n']
    with open(args.script, 'w') as scriptfile:
        scriptfile.writelines(bash_lines)
        scriptfile.writelines(convertion_lines)
        scriptfile.writelines(input_specs)
        scriptfile.writelines(output_lines)


def parse_ieee_title_old(ieeebib):
    if isinstance(ieeebib, str):
        with open(ieeebib, 'r') as title_file:
            lines = title_file.readlines()

    if not lines:
        return None
    title_lines = filter(lambda x: x.startswith('@'), lines)

    pattern = r"@STRING\{(?P<key>IEEE_(?P<code>[JOM]_[A-Z]+))\W+="
    parser = re.compile(pattern, re.IGNORECASE)

    special_cases = {'TPROC': 'JPROC', 'OACC': 'ACCESS'}
    abbrevs = {}
    for line  in title_lines:
        match = parser.search(line)
        if not match: continue
        key, code = match.group('key', 'code')
        code = code.replace('J_', 'T') if code.startswith('J_') else code.replace('_', '')
        if code in special_cases:
            code = special_cases[code]
        doi = f"10.1109/{code}"
        # print(match.group('key', 'code'), code, doi)
        abbrevs[doi] = {'key': key, 'line': line.strip()}
    # for key, value in abbrevs.items():
    #     print(value['line'])
    #     print(' '*len('@STRING'), value['key'], '\t', key)
    return abbrevs


def collect_ieee_titles(strings):
    special_cases = {'TPROC': 'JPROC',
                     'TSPL': 'LSP',
                     'TWCOML': 'WCL',
                     'OACC': 'ACCESS'}
    titles = {}
    for key, title in strings.items():
        ks = key.upper().replace('IEEE_', '')
        code = ks.replace('J_', 'T') if ks.startswith('J_') else ks.replace('_', '')
        doi_key = code
        if code.startswith('TCAS'):
            doi_key = code.replace('TCAS', 'TCS')
        elif code in special_cases:
            doi_key = special_cases[code]
        doi = f"10.1109/{doi_key}"
        titles[doi] = (key.upper(), title)
    return titles


class DOIParser(object):
    def __init__(self):
        pattern = r'(?P<key>10.\d{4}/[A-Za-z\.]+)\.\d{4}\.'
        self.parser = re.compile(pattern)

    def get_doi_key(self, doi):
        match = self.parser.search(doi)
        return match.group('key') if match else None


class JournalPatcher(object):
    def __init__(self):
        pattern = r'journaltitle\s+=\s+\{([A-Z_]+)\}'
        self.patcher = re.compile(pattern)

    def patch(self, text):
        pattern_new = r'journal = \g<1>'
        text_updated = self.patcher.sub(pattern_new, text)
        return text_updated

class StringPatcher(object):
    def __init__(self):
        pattern = r'\n^(@string.+)$\n'
        self.patcher = re.compile(pattern, flags=re.M)

    def patch(self, text):
        pattern_new = r'\g<1>\n'
        text_updated = self.patcher.sub(pattern_new, text)
        return text_updated


def extract_citation_keys(auxfile):
    with open(auxfile, 'r') as aux_stream:
        lines = aux_stream.readlines()
    if not lines: return None
    cite_lines = filter(lambda x: x.startswith('\\abx@aux@cite'), lines)
    cite_key_pattern = re.compile('abx@aux@cite\{(?P<key>\S+)\}')
    keys = []
    for line in cite_lines:
        match = cite_key_pattern.search(line)
        if not match: continue
        keys.append(match.group('key'))
    return set(keys)


def extract_bibtex(args):
    cited = extract_citation_keys(args.auxfile)
    bib_db = load_bibtex(args.bibfile)
    entries = bib_db.entries
    entries_filtered = list(filter(lambda x: x['ID'] in cited, entries))
    bib_db.entries = entries_filtered
    with open(args.output, 'w') as output_file:
        bibtexparser.dump(bib_db, output_file)


def simplify_bibtex(args):
    bib_db = load_bibtex(args.bibfile)
    bib_ieee = load_bibtex(args.bib_journal)

    strings = collect_ieee_titles(bib_ieee.strings)
    parser = DOIParser()
    strings_filtered = OrderedDict()
    for entry in bib_db.entries:
        if 'doi' in entry:
            doi_prefix = parser.get_doi_key(entry['doi'])
            if doi_prefix in strings:
                key, journal = strings[doi_prefix]
                strings_filtered[key] = journal
                entry['journaltitle'] = key
        if 'shortjournal' in entry:
            entry.pop('shortjournal')

    bib_db.strings = strings_filtered
    text = bibtexparser.dumps(bib_db)
    text_patched = JournalPatcher().patch(text)
    text_bibtex = StringPatcher().patch(text_patched)
    with open(args.output, 'w') as output_file:
        output_file.write(text_bibtex)


def format_entry(item):
    item_id = item['ID']
    item_type = item['ENTRYTYPE']
    item_doi = item.get('doi', '')
    item_title = item.get('title', '')
    item_file = ''
    if 'file' in item:
        fields = item['file'].split(':')
        item_file = '\n'.join([' > ' + fn for fn in fields])

    output = f'{item_id}: [{item_type} {item_doi}]\n{item_file}'
    return output


def organize_bib():
    """To parse command line and process the paper organization task."""

    parser = argparse.ArgumentParser(description='Organize papers')
    parser.add_argument('bibfile', help='The bibtex file to be processed.')
    subparsers = parser.add_subparsers(help='Available commands')

    help_tmpl = 'Create a YAML file describing metadata for the organization tasks.'
    parser_tmpl = subparsers.add_parser('genmetadata', help=help_tmpl)
    parser_tmpl.add_argument('--PI', default='Qi, Fei',
                             help='The name of the PI.')
    parser_tmpl.add_argument('--metadata', '-m',
                             help='Output metadata in a YAML file.')
    parser_tmpl.set_defaults(func=gen_metadata)

    help_patch = 'Create attachements for uploading to NSFC website.'
    parser_attach = subparsers.add_parser('genattach', help=help_patch)
    parser_attach.add_argument('--metadata', '-m',
                             help='Metadata in YAML format specifying the task.')
    parser_attach.add_argument('--script', '-s',
                             help='Bash script for creating tasks.')
    parser_attach.set_defaults(func=gen_attachments)    

    help_extract = 'Extract bib items based on a given aux file.'
    parser_extract = subparsers.add_parser('extract', help=help_extract)
    parser_extract.add_argument('--auxfile', '-x',
                                 help='AUX file created by LaTeX.')
    parser_extract.add_argument('--output', '-o',
                                 help='Output of cited references in BibTeX format.')
    parser_extract.set_defaults(func=extract_bibtex)

    help_simplify = 'Simplify a BibTeX file.'
    parser_simplify = subparsers.add_parser('simplify', help=help_simplify)
    parser_simplify.add_argument('--bib-journal', '-b',
                                help='BibTeX of canonical journal/conference titles.')
    parser_simplify.add_argument('--output', '-o',
                                help='Output of simplified BibTeX.')
    parser_simplify.set_defaults(func=simplify_bibtex)

    args = parser.parse_args()
    # print(args)
    args.func(args)
        
# 
# parse_bib.py ends here
