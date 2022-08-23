# form_automa.py ---
#
# Filename: form_automa.py
# Author: Fred Qi
# Created: 2022-08-21 16:02:49(+0800)
#
# Last-Updated: 2022-08-24 06:56:34(+0800) [by Fred Qi]
#     Update #: 234
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
import glob
import openpyxl
from os import path
from mailmerge import MailMerge
from datetime import date

WORKDIR = "/home/fred/cloud/share/senior-design"

DATA_FILE = path.join(WORKDIR, "0.毕业设计成绩登记表.xlsx")
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
    wb = openpyxl.load_workbook(filename)
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
    data = []
    for row in sheet.iter_rows(min_row=min_row, values_only=True):
        row_dict = {k:v for k, v in zip(keys, row)}
        # print(row_dict['id'], row_dict['name'])
        data.append(row_dict)
    return data


def document_merge(template, data):
    """Merge data into a docx template."""
    document = MailMerge(template)
    for row in data:
        document.merge(**row)
        sid, name = row['id'], row['name']
        output_dir = path.join(OUTPUT_DIR, f'{sid}-{name}')
        if not path.exists(output_dir):
            os.mkdir(output_dir)
        output_file = path.basename(template)
        print(output_file, sid, name)
        document.write(path.join(output_dir, output_file))
           
    
def template_dict(template_dir, sheets):
    """Create a dictionary of templates."""
    sheet_names = list(sheets)
    template_files = glob.glob(f"{template_dir}/*.docx")
    templates = {}
    for filename in template_files:
        for name in sheet_names:
            if filename.find(name) >= 0:
                templates[name] = filename
                sheet_names.remove(name)
    return templates
    

# template = "daily-scores.docx"
# os.mkdir("output")

# templates = glob.glob(f"{TEMPLATE_DIR}/*.docx")
# for template in templates:
#     basename = path.basename(template)
#     # print(basename, template)
#     document = MailMerge(template)
#     # print("\n".join(list(document.get_merge_fields())))


#     document.merge(id="001",
#                    reviewer="kkk",
#                    discipline="智能科学与技术",
#                    school="人工智能学院",
#                    title="title",
#                    score="90",
#                    name="姓名")

#     outfile = path.join(OUTPUT_DIR, f"test-{basename}")
#     document.write(outfile)


if __name__ == "__main__":
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
    
    
# 
# form_automa.py ends here
