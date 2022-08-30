# form_automa.py ---
#
# Filename: form_automa.py
# Author: Fred Qi
# Created: 2022-08-21 16:02:49(+0800)
#
# Last-Updated: 2022-08-24 16:23:41(+0800) [by Fred Qi]
#     Update #: 295
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
import openpyxl
import warnings
from os import path
from glob import glob
from mailmerge import MailMerge
from datetime import date
from docx2pdf import convert
from PyPDF2 import PdfReader
from PyPDF2 import PdfMerger


# WORKDIR = "/home/fred/cloud/share/senior-design"
WORKDIR = "C:\\Users\\fredq\\github\\senior-design"

DATA_FILE = path.join(WORKDIR, "毕业设计表单数据.xlsx")
TEMPLATE_DIR = path.join(WORKDIR, "templates")
OUTPUT_DIR = WORKDIR


def mailmerge_fields(sheet):
    """Get mail merge fields from a given excel sheet."""
    fields = []
    for row in sheet.iter_rows(min_row=2, max_col=2):
        fields.append((c.value for c in row))
    return dict(fields)


def load_form_data(filename):
    """Load data from excel file."""
    wb = openpyxl.load_workbook(filename, data_only=True)
    fields = mailmerge_fields(wb["Fields"])
    return fields, wb


def sheet_column_keys(sheet, fields):
    """Create dict keys from an excel sheet."""
    # print(sheet.title)    
    header = sheet.iter_rows(max_row=1, values_only=True)
    keys = [fields[value] for value in list(header)[0]]
    return keys


def sheet_row_dict(sheet, keys, min_row=5):
    """Create a dictionary from a row of a excel sheet."""
    score_range = {'及格': 60, '中等': 70, '良好': 80, '优秀': 90}
    max_row = 24
    data = []
    for row in sheet.iter_rows(min_row=min_row, max_row=max_row):
        row_dict = {k:v.value for k, v in zip(keys, row)}
        if 'sc' in row_dict and 'score' in row_dict:
            # print(row_dict['sc'], row_dict['score'])
            sc, score = row_dict['sc'], row_dict['score']
            sc = 0 if sc is None else sc
            sc_min = score_range[score]
            # print(sc, score, sc_min)
            if sc < sc_min or sc >= (sc_min + 10):
                warnings.warn(f"成绩等级与分数不一至 {row_dict['id']} {sc} {score}")
                
        if 'date' in row_dict:
            dt = row_dict['date']
            row_dict['date_data'] = dt
            row_dict['date'] = f'{dt.year}年{dt.month}月{dt.day}日'
        data.append(row_dict)
    return data


def document_merge(template, data):
    """Merge data into a docx template."""
    output_filename = path.basename(template)
    print(output_filename)
    for row in data:
        document = MailMerge(template)
        missing_fields = document.get_merge_fields() - row.keys()
        if missing_fields:
            print(output_filename, missing_fields)
        document.merge(**row)
        sid, name = row['id'], row['name']
        output_dir = path.join(OUTPUT_DIR, f'{sid}-{name}')
        if not path.exists(output_dir):
            os.mkdir(output_dir)
        # print(output_filename, sid, name, row['date'])
        # print(f"    {sid} {name} {row['sc']} {row['score']}")
        document.write(path.join(output_dir, output_filename))
           
    
def template_dict(template_dir, sheets):
    """Create a dictionary of templates."""
    sheet_names = list(sheets)
    template_files = glob(f"{template_dir}/*.docx")
    templates = {}
    for filename in template_files:
        for name in sheet_names:
            if filename.find(name) >= 0:
                templates[name] = filename
                sheet_names.remove(name)
    return templates

    
def form_auto_merge():
    sheet_names = ['日常考核', '软硬件验收', '中期检查', '指导教师评分表', '评阅评分表', '答辩登记表']
    templates = template_dict(TEMPLATE_DIR, sheet_names)
    # print("\n".join([f'{k}={v}' for k,v in templates.items()]))
    fields, wb = load_form_data(DATA_FILE)
    # print(fields)
    for sheet_name in sheet_names:
        template = templates[sheet_name]
        keys = sheet_column_keys(wb[sheet_name], fields)
        data = sheet_row_dict(wb[sheet_name], keys)
        document_merge(template, data)


def merge_replacements(folder):
    sheet_names = ['日常考核', '中期检查', '指导教师评分表', '评阅评分表', '软硬件验收', '答辩登记表']
    files_pdf = glob(path.join(folder, "*.pdf"))
    merger = PdfMerger()

    for name in sheet_names:
        pdf_file = glob(path.join(folder, f"*{name}*.pdf"))
        pdf_stream = open(pdf_file[0], 'rb')
        merger.append(pdf_stream)

    output = open(path.join(folder,  "replacements.pdf"), 'wb')
    merger.write(output)
    merger.close()
    output.close()


def replace_pages(student_id, name, page_begin, page_end):
    filename = f"{student_id}-{name}-毕业设计归档材料.pdf"
    archive_filepath = path.join(WORKDIR, "archived", filename)
    
    reader = PdfReader(archive_filepath)
    n_pages = len(reader.pages)
    archive_stream = open(archive_filepath, 'rb')

    replacement_filepath = path.join(WORKDIR, f"{student_id}-{name}", "replacements.pdf")
    replacement_stream = open(replacement_filepath, 'rb')

    merger = PdfMerger()
    merger.append(archive_stream, pages=(0, page_begin))
    merger.append(replacement_stream)
    merger.append(archive_stream, pages=(page_end, n_pages))

    output_filepath = path.join(WORKDIR, "updated", filename)    
    output_stream = open(output_filepath, 'wb')
    merger.write(output_stream)

    merger.close()
    output_stream.close()    


def convert_merge_replace():
    folders = glob(path.join(WORKDIR, "1*"))
    for folder in folders:
        convert(folder)
        merge_replacements(folder)


if __name__ == "__main__":
    # form_auto_merge()
    # convert_merge_replace()
    wb = openpyxl.load_workbook(DATA_FILE, data_only=True)
    sheet = wb["replace"]
    for row in sheet.iter_rows(min_row=2, values_only=True):
        print(row)
        replace_pages(*row)
    # merge_replacements("16020520025-马丁扬")
    # replace_pages("16020520025", "马丁扬", 17, 26)
 
    # attentions = []
    # for folder in folders:
    #     print(f"Processing {folder}...")
    #     convert(folder)
    #     pdfs = glob(f"{folder}/*.pdf")
    #     for pdf in pdfs:
    #         reader = PdfReader(pdf)
    #         n_pages = len(reader.pages)
    #         if n_pages > 1:
    #             print(n_pages, pdf)
    #             attentions.append(f"{n_pages} pages in {pdf}")
    # print("\n".join(attentions))
    
# 
# form_automa.py ends here