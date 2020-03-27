# parse_bib.py ---
#
# Filename: organize_bib.py
# Author: Fred Qi
# Created: 2020-03-26 00:45:19(+0800)
#
# Last-Updated: 2020-03-27 09:34:36(+0800) [by Fred Qi]
#     Update #: 368
# 

# Commentary:
#
#
# 

# Change Log:
#
#
#

import yaml
from yaml import Loader

import shutil
# from pathlib import Path

import argparse

import bibtexparser
from bibtexparser.bparser import BibTexParser


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


def gen_metadata(args):
    """Generate metadata and store them in a YAML file with given arguments."""
    with open(args.bibfile) as bibfile:
        bib_db = BibTexParser(common_strings=True).parse_file(bibfile)
        entries = sorted(list(bib_db.entries),
                         key=lambda x: x['year'], reverse=True)
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
    input_specs[0] = 'pdftk ' + input_specs[0].strip() + '\n'
    output_lines = ['      cat ', ' '.join(output_specs),
                    ' output attachments.pdf', '\n\n',
                    'shrink_pdf attachments.pdf\n']
    # 'pdf2ps $FOLDER/attach-large.pdf - | ps2pdf - $FOLDER/attachments.pdf\n']
    with open(args.script, 'w') as scriptfile:
        scriptfile.writelines(bash_lines)
        scriptfile.writelines(convertion_lines)
        scriptfile.writelines(input_specs)
        scriptfile.writelines(output_lines)
        
        
# for entry in bib_db.entries:
#     # print(entry['ID'], entry['ENTRYTYPE'], entry.get('doi'))
#     update_file(entry)
#     print(entry['author'])
#     # print(entry.keys())
#     print(format_entry(entry))
#     print()
#     # print(entry['file'])
#     # print(display_file(entry['file']))
#     # print(list(entry.keys()))


def update_file(entry):
    if 'file' in entry:
        fields = entry['file'].split(':')
        if Path(fields[1]).is_file():
            shutil.copyfile(fields[1], fields[0])
            fields[1] = str(fields[0])
            entry['file'] = ':'.join(fields)        
    return entry


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

    help_attach = 'Create attachements for uploading to NSFC website.'
    parser_attach = subparsers.add_parser('genattach', help=help_attach)
    parser_attach.add_argument('--metadata', '-m',
                             help='Metadata in YAML format specifying the task.')
    parser_attach.add_argument('--script', '-s',
                             help='Bash script for creating tasks.')
    parser_attach.set_defaults(func=gen_attachments)    
    
    args = parser.parse_args()
    # print(args)
    args.func(args)
        
# 
# parse_bib.py ends here
