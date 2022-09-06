# form_automa.py ---
#
# Filename: form_automa.py
# Author: Fred Qi
# Created: 2022-08-21 16:02:49(+0800)
#
# Last-Updated: 2022-09-06 12:11:28(+0800) [by Fred Qi]
#     Update #: 1722
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
import sys
import fitz
import openpyxl
import warnings
from os import path
from glob import glob
from dataclasses import dataclass, field, asdict, fields
from configparser import ConfigParser
from configparser import ExtendedInterpolation

from mailmerge import MailMerge
from datetime import datetime
from PyPDF2 import PdfReader
from PyPDF2 import PdfMerger
from docx import Document
from docx.styles import style
from docx.shared import Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.table import WD_ALIGN_VERTICAL

import mistletoe
from mistletoe.block_tokens import Heading, Paragraph
from mistletoe.span_tokens import RawText, LineBreak, Strong, Emphasis
from mistletoe.base_elements import WalkItem


if 'linux' == sys.platform:
    WORKDIR = "/home/fred/cloud/share/senior-design"
    TEACHDIR = "/home/fred/cloud/share/teaching"
elif 'win32' == sys.platform:
    from docx2pdf import convert
    WORKDIR = "C:\\Users\\fredq\\github\\senior-design"
    TEACHDIR = "C:\\Users\\fredq\\github\\teaching"

DATA_FILE = path.join(WORKDIR, "毕业设计表单数据.xlsx")
TEMPLATE_DIR = path.join(WORKDIR, "templates")
OUTPUT_DIR = WORKDIR


class Markdown2Docx(object):
    def __init__(self, filename):
        # help(Heading)
        self.sections = {}
        with open(filename, 'r') as istream:
            text = istream.read()
            doc = mistletoe.Document.read(text)
            for item in doc.children:
                if isinstance(item, Heading) and 1 == item.level:
                    key = self.get_text(item)
                    contents = list()
                    self.sections[key] = contents
                else:
                    contents.append(item)

    @staticmethod
    def get_text(token):
        if isinstance(token, RawText):
            return token.content
        elif not isinstance(token, LineBreak):
            raw_text = token.children[0]
            assert isinstance(raw_text, RawText)
            return raw_text.content.strip()

    def add_paragraph(self, cell, paragraphs, styles=None):
        # print(style)
        for idx, item in enumerate(paragraphs):
            if 0 == idx:
                tblp = cell.paragraphs[0]
                if "Heading 2" in styles:
                    tblp.style = styles["Heading 2"]
            else:
                tblp = cell.add_paragraph()
            if isinstance(item, Heading):
                tblp.style = styles["Heading 2"]
                run = tblp.add_run()
                run.add_text(self.get_text(item)).bold = True
            elif isinstance(item, Paragraph):
                for item in item.children:
                    if isinstance(item, LineBreak):
                        tblp = cell.add_paragraph()
                        continue
                    tblp.style = styles["Table Text"]
                    run = tblp.add_run()
                    content = self.get_text(item)
                    if isinstance(item, Emphasis):
                        content = f"    {content}    "
                    run.add_text(content)
                    if isinstance(item, Strong):
                        run.bold = True
                    elif isinstance(item, Emphasis):
                        run.underline = True


class RowMapper(object):
    def __init__(self, keys, headers):
        self.indices = []
        for key in keys:
            self.indices.append(headers.index(key))

    def get(self, values):
        return [values[idx] for idx in self.indices]                              
            

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


def sheet_row_dict(sheet, keys, min_row=5, max_row=24):
    """Create a dictionary from a row of a excel sheet."""
    score_range = {'及格': 60, '中等': 70, '良好': 80, '优秀': 90}
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


def sheet_replace():
    wb = openpyxl.load_workbook(DATA_FILE, data_only=True)
    sheet = wb["replace"]
    for row in sheet.iter_rows(min_row=2, values_only=True):
        print(row)
        replace_pages(*row)


def add_score_table():
    template = "教学一览表-机器学习（双语）-AI204025-2021-2022学年第一学期-02.docx"
    datafile_path = path.join(TEACHDIR, 'teaching-data.xlsx')
    _, wb = load_form_data(datafile_path)
    sheet = wb["2021-2022学年第一学期-02"]

    data = []
    for row in sheet.iter_rows():
        data.append([item.value for item in row])

    document = Document(path.join(TEACHDIR, template))
    document.add_page_break()
    document.add_heading("西安电子科技大学学习过程考核记录表", 1)
    table = document.add_table(rows=0, cols=len(data[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    for row in data:
        row_cells = table.add_row().cells
        for idx, value in enumerate(row):
            text = "" if value is None else f"{value}"
            row_cells[idx].text = text
            row_cells[idx].vertical_alignment = WD_ALIGN_VERTICAL.CENTER 

    document.add_page_break()
    document.save(path.join(TEACHDIR,'demo.docx'))


def testing_docx():
    from docx.shared import Inches
    document = Document(path.join(TEACHDIR, template))

    document.add_page_break()

    document.add_heading('Document Title', 1)

    p = document.add_paragraph('A plain paragraph having some ')
    p.add_run('bold').bold = True
    p.add_run(' and some ')
    p.add_run('italic.').italic = True

    document.add_heading('Heading, level 1', level=1)
    # document.add_paragraph('Intense quote', style='Intense Quote')

    # document.add_paragraph(
    #     'first item in unordered list', style='List Bullet'
    # )
    # document.add_paragraph(
    #     'first item in ordered list', style='List Number'
    # )

    # document.add_picture('monty-truth.png', width=Inches(1.25))

    records = (
        (3, '101', 'Spam'),
        (7, '422', 'Eggs'),
        (4, '631', 'Spam, spam, eggs, and spam')
    )

    table = document.add_table(rows=1, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Qty'
    hdr_cells[1].text = 'Id'
    hdr_cells[2].text = 'Desc'
    for qty, id, desc in records:
        row_cells = table.add_row().cells
        row_cells[0].text = str(qty)
        row_cells[1].text = id
        row_cells[2].text = desc

    document.add_page_break()
    document.save(path.join(TEACHDIR,'demo.docx'))


class SummaryComposer(object):
    """Composer for teaching summary."""
    # def __init__(self, data, working_dir=TEACHDIR):
    #     self.data = data
    #     self.working_dir = working_dir
    #     # self.template_file = self.get_summary_file(data)
    #     # template_path = path.join(working_dir, self.template_file)
    #     # if not path.exists(template_path):
    #     #     template_path = None
    #     markdown_path = path.join(TEACHDIR, '2021-2022学年第二学期-02.md')
    #     self.md2docx = Markdown2Docx(markdown_path)
    #     self.table_width = Cm(15)
    #     self.table_height = Cm(22.5)
    #     self.document = Document(data['summary_filepath'])
    #     self.setup_core_properties()
    #     self.config_styles()

    def __init__(self, course, term):
        self.course = course
        self.term = term
        self.table_width = Cm(15)
        self.table_height = Cm(22.5)
        text_filepath = path.join(term.data_dir, term.summary_text)
        self.md2docx = Markdown2Docx(text_filepath)
        record_filepath = path.join(term.data_dir, term.record)
        wb = openpyxl.load_workbook(record_filepath)
        self.teaching_records = wb.active
        wb = openpyxl.load_workbook(course.score_filepath)
        self.scores = wb.active
        self.document = Document(course.summary_filepath)
        self.setup_core_properties()
        self.config_styles()
        

    @staticmethod
    def get_summary_file(data):
        """Get the file name of the teaching summary."""
        fields = set(['course_name', 'course_id', 'course_order', 'semester'])
        intersection = fields & data.keys()
        assert len(intersection) == len(fields)
        name = data['course_name']
        cid  = data['course_id']
        cord = data['course_order']
        term = data['semester']
        summary_filename = f"教学一览表-{name}-{cid}-{term}-{cord}.docx"
        return summary_filename

    @staticmethod
    def set_center(cell):
        p = cell.paragraphs[0]
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    @staticmethod
    def set_bold(cell, text):
        p = cell.paragraphs[0]
        p.add_run(text).bold = True

    def config_styles(self):
        self.styles = {}
        for item in self.document.styles:
            name = item.name
            if name.find("Table") >= 0:
                self.styles[name] = item
            elif name.find("Heading") >= 0:
                self.styles[name] = item
            # if name in self.styles:
            #     print(name, self.styles[name])
                    
    def setup_core_properties(self):
        """Setup core properties of the summary fiel."""
        core_prop = self.document.core_properties
        core_prop.author = self.course.teachers
        # self.data['teachers']
        dt = self.course.summary_date
        dt = datetime.strptime(dt, "%Y-%m-%d")
        core_prop.created = dt
        core_prop.last_printed = dt
        # core_prop.created = self.data['date_data']
        # core_prop.last_printed = self.data['date_data']
        summary_filename = path.basename(self.course.summary_filepath)
        # SummaryComposer.get_summary_file(self.data)
        core_prop.title = summary_filename.replace(".docx", "")
        core_prop.comments = "Comments"

    def add_table(self, heading, rows, cols=1,
                  headers=None, widths=None, style=None):
        self.document.add_page_break()
        self.document.add_heading(heading, 1)
        n_cols = len(headers) if headers else cols
        table_style = self.styles.get(style, None)
        table = self.document.add_table(rows=rows, cols=n_cols,
                                        style=table_style)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        if headers and widths and len(headers) == len(widths):
            table.autofit = False
            table.allow_autofit = False
            for idx in range(len(widths)):
                table.columns[idx].width = widths[idx]
                table.cell(0, idx).width = widths[idx]
        else:
            table.autofit = False
            table.allow_autofit = False

        # framed page contents
        if 1 == rows and 1 == n_cols:
            table.columns[0].width = self.table_width
            table.rows[0].height = self.table_height
            cell = table.cell(0, 0)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            cell.paragraphs[0].style = self.styles["Heading 2"]
        elif headers:
            for idx, text in enumerate(headers):
                cell = table.cell(0, idx)
                p = cell.paragraphs[0]
                p.add_run(text).bold = True
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        return table

    def add_teaching_record(self):
        """Add a table recording the teaching process."""

        # semester = self.data['semester']
        # course_order = self.data['course_order']
        # records = wb_records[semester]
        records = self.teaching_records
        course_order = self.course.course_order
        keys = [f"上课时间-{course_order}", "知识点", "教学过程记录"]
        row_mapper = RowMapper(keys, next(records.values))
        
        headers = ["序号", "上课时间", "知识点", "教学过程记录"]
        widths = [Cm(1.25), Cm(2.5), Cm(4.25), Cm(7.5)]
        table = self.add_table("教学过程记录", rows=1,
                               headers=headers, widths=widths,                               
                               style="Teaching Table")

        idx = 1
        for row in records.iter_rows(min_row=2, values_only=True):
            values = row_mapper.get(row)
            row_cells = table.add_row().cells
            self.set_center(row_cells[0])
            self.set_bold(row_cells[0], f"{idx:d}")
            row_cells[1].text = f"{values[0]:%Y-%m-%d}"
            self.set_center(row_cells[1])
            
            row_cells[2].text = values[1]
            
            row_cells[3].paragraphs[0].text = values[2]
            p = row_cells[3].add_paragraph()
            p.text = "课堂秩序良好"
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            idx += 1

    def add_framed_section(self, section_title):
        table = self.add_table(section_title, rows=1, cols=1,
                               style="Frame Table")
        
        cell = table.cell(0, 0)
        paragraphs = self.md2docx.sections[section_title]
        self.md2docx.add_paragraph(cell, paragraphs, self.styles)

    def add_teaching_goal(self):
        section_title = "课程教学目标及与毕业要求的对应关系"
        table = self.add_table(section_title, rows=1, cols=1,
                               style="Frame Table")
        
        cell = table.cell(0, 0)
        paragraphs = self.md2docx.sections[section_title]
        self.md2docx.add_paragraph(cell, paragraphs, self.styles)

    def add_scoring_rules(self):
        section_title = "课程考核方式及成绩评定原则"
        table = self.add_table(section_title, rows=1, cols=1,
                               style="Frame Table")
        
        cell = table.cell(0, 0)
        paragraphs = self.md2docx.sections[section_title]
        self.md2docx.add_paragraph(cell, paragraphs, self.styles)

    def add_score_table(self):
        """Add score table."""
        sheet_title = f"{self.course.semester}-{self.course.course_order}"
        assert sheet_title == self.scores.title
        data = []
        for row in self.scores.iter_rows(min_row=5):
            data.append([item.value for item in row])
        
        table = self.add_table("西安电子科技大学学习过程考核记录表",
                               rows=1, headers=data[0],
                               style="Score Table")
        for row in data[1:]:
            row_cells = table.add_row().cells
            for idx, value in enumerate(row):
                text = "" if value is None else f"{value}"
                row_cells[idx].text = text
                row_cells[idx].vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    def add_exam_table(self):
        """Add exam sheet and grading rules."""
        table = self.add_table("课程考试试题及答案", rows=1, cols=1,
                               style="Frame Table")
        
        run = table.cell(0, 0).paragraphs[0].add_run()
        run.add_text("（试题、标准答案及评分细则）").bold = True
        run = table.cell(0, 0).add_paragraph().add_run()

        # exam_path = path.join(self.working_dir, f".{self.data['semester']}")
        # exam_pattern = path.join(exam_path, "page*.png")
        # for image in sorted(glob(exam_pattern)):
        for image in sorted(self.term.images):
            run.add_picture(image)

    def add_exam_analysis(self):
        section_title = "试卷（卷面）分析及总结"
        table = self.add_table(section_title, rows=1, cols=1,
                               style="Frame Table")
        
        cell = table.cell(0, 0)
        paragraphs = self.md2docx.sections[section_title]
        self.md2docx.add_paragraph(cell, paragraphs, self.styles)

    def add_ability_analysis(self):
        section_title = "课程能力达成度分析及总结"
        table = self.add_table(section_title, rows=1, cols=1,
                               style="Frame Table")
        
        cell = table.cell(0, 0)
        paragraphs = self.md2docx.sections[section_title]
        self.md2docx.add_paragraph(cell, paragraphs, self.styles)
        
    def create_summary(self):
        self.add_teaching_record()
        self.add_framed_section("课程教学目标及与毕业要求的对应关系")
        self.add_framed_section("课程考核方式及成绩评定原则")
        # self.add_teaching_goal()
        # self.add_scoring_rules()
        self.add_score_table()
        self.add_exam_table()
        self.add_framed_section("试卷（卷面）分析及总结")
        self.add_framed_section("课程能力达成度分析及总结")
        # self.add_exam_analysis()
        # self.add_ability_analysis()
        self.document.save(self.course.summary_filepath)
    
    
def prepare_teaching_summary(template, scorefile, recordfile,
                             working_dir=TEACHDIR):
    record_filepath = path.join(working_dir, recordfile)
    wb_records = openpyxl.load_workbook(record_filepath)
    fields, wb = load_form_data(path.join(working_dir, scorefile))
    sheet = wb['课程信息']
    keys = sheet_column_keys(sheet, fields)
    data = sheet_row_dict(sheet, keys, min_row=2, max_row=3)
    for row in data:
        semester, course_order = row['semester'], row['course_order']
        print(f"Processing {semester}-{course_order}...")
        summary_filename = SummaryComposer.get_summary_file(row)
        merger = MailMerge(path.join(working_dir, template))
        merger.merge(**row)
        merger.write(path.join(working_dir, summary_filename))

        composer = SummaryComposer(row)
        composer.add_teaching_record(wb_records)
        composer.add_framed_section("课程教学目标及与毕业要求的对应关系")
        composer.add_framed_section("课程考核方式及成绩评定原则")
        # composer.add_teaching_goal()
        # composer.add_scoring_rules()
        composer.add_score_table(wb)
        composer.add_exam_table(wb)
        composer.add_framed_section("试卷（卷面）分析及总结")
        composer.add_framed_section("课程能力达成度分析及总结")
        # composer.add_exam_analysis()
        # composer.add_ability_analysis()
        composer.save(summary_filename)


class PdfPage2Image(object):
    
    def __init__(self, dpi=300,
                 hmargin=3.5, vmargin=3.5,
                 paper_width=21, paper_height=29.7):
        self.dpi = dpi
        # 72 is the default sampling DPI
        # self.mat = fitz.Matrix(dpi/72, dpi/72)

        self.width  = paper_width - 2*hmargin
        self.height = paper_height - 2*vmargin
        left   = self.cm_to_dots(hmargin, self.dpi)
        top    = self.cm_to_dots(vmargin, self.dpi)
        right  = self.cm_to_dots(paper_width - hmargin, self.dpi)
        bottom = self.cm_to_dots(paper_height - vmargin, self.dpi)
        self.clip = fitz.Rect(left, top, right, bottom)
      

    @staticmethod
    def cm_to_dots(x, dpi=72):
        return x/2.54*dpi

    def convert(self, filepath, output_dir):
        if not path.exists(filepath):
            return None

        if not path.exists(output_dir):
            os.mkdir(output_dir)

        images = []
        doc = fitz.open(filepath)
        for page in doc:
            pixels = page.get_pixmap(dpi=self.dpi)
            image_clip = fitz.Pixmap(pixels, pixels.width, pixels.height, self.clip)
            image_clip.set_dpi(self.dpi, self.dpi)
            image_filepath = path.join(output_dir, f"page-{page.number:02d}.png")
            image_clip.save(image_filepath)
            images.append(image_filepath)

        return images


@dataclass
class TermInfo(object):
    """Information of a term."""
    
    semester: str
    data_dir: str
    record: str
    exam: str
    summary_text: str
    working_dir: str
    images: list = field(init=False)

    def __str__(self):
        return f"{self.semester}"

    def __post_init__(self):
        """Convert the exam pdf file to images."""
        output_dir = path.join(self.working_dir, f'.{self.semester}')
        exam_filepath = path.join(self.data_dir, self.exam)
        if path.exists(exam_filepath):
            pdf2image = PdfPage2Image()
            self.images = pdf2image.convert(exam_filepath, output_dir)

@dataclass
class CourseInfo(object):
    """Information of a course."""

    semester: str
    course_id: str
    course_name: str
    course_order: int
    credits: float
    hours: int
    teachers: str
    classes: str
    summary_date: str
    data_dir: str
    working_dir: str
    date: datetime = field(init=False)
    score_filepath: str = field(init=False)
    summary_file: str = field(init=False)
    summary_filepath: str = field(init=False)

    def __post_init__(self):
        self.date = datetime.strptime(self.summary_date, '%Y-%m-%d')
        score_file = f"scores-{self.course_order}.xlsx"
        self.score_filepath = path.join(self.data_dir, score_file)
        # Filename of the teaching summary.
        parts = ["教学一览表", self.course_name, self.course_id,
                 self.semester, self.course_order]
        self.summary_file = '-'.join(parts) + ".docx"
        self.summary_filepath = path.join(self.working_dir, self.summary_file)
        # self.summary_date = self.date.strftime('%Y年%m月%d日')
        
    def __str__(self):
        return f"{self.course_id:8} {self.course_name} {self.semester} {self.course_order} {self.teachers}"

    # def summary_file(self):
    #     """"""
    #     name = self.course_name
    #     cid  = self.course_id
    #     cord = self.course_order
    #     term = self.semester
    #     return f"教学一览表-{name}-{cid}-{term}-{cord}.docx"

    def compose_summary(self, template, term):
        # Create the title page with mail merge.
        merger = MailMerge(template)
        merger.merge(**asdict(self))
        merger.write(self.summary_filepath)

        # Create the full summary file
        composer = SummaryComposer(self, term)
        composer.create_summary()
       

def load_config(config_filepath):
    config = ConfigParser(interpolation=ExtendedInterpolation())
    config.read(config_filepath)
    # workdir = config.get('general', 'workdir')
    template = config.get('general', 'template_filepath')
    classes = config['general']['classes'].split(',')
    course_info_keys = [f.name for f in fields(CourseInfo)]
    for key in ['date', 'summary_file', 'summary_filepath', 'score_filepath']:
        course_info_keys.remove(key)
    term_keys = [f.name for f in fields(TermInfo)]
    term_keys.remove('images')
    
    courses, terms = [], {}
    data = dict(config.items('general', raw=False))
    for cls in classes:
        data.update(config.items(cls, raw=False))
        term_key = data['term_key']
        data.update(config.items(term_key, raw=False))

        properties = {key: data[key] for key in course_info_keys}
        info = CourseInfo(**properties)            
        courses.append(info)
        
        semester = data['semester']
        if semester not in terms:
            properties = {key: data[key] for key in term_keys}
            terms[semester] = TermInfo(**properties)

    return courses, terms, template
        
  
if __name__ == "__main__":

    # exams = { "2021-2022学年第一学期": "PRML-2021-autumn-summary.pdf",
    #           "2020-2021学年第二学期": "PRML21-summary.pdf",
    #           "2019-2020学年第二学期": "PRML20-summary.pdf",
    #           "2018-2019学年第二学期": "PRML19-summary.pdf"}

    # pdf2image = PdfPage2Image()
    # for semester, examfile in exams.items():
    #     print(f"Processing {semester} ({examfile})...")
    #     exam_filepath = path.join(TEACHDIR, 'exams', examfile)
    #     output_dir = path.join(TEACHDIR, f'.{semester}')
    #     images = pdf2image.convert(exam_fielpath, output_dir)

    # template_path = path.join(TEACHDIR, 'template.docx')
    # datafile_path = path.join(TEACHDIR, 'teaching-data.xlsx')
    # prepare_teaching_summary("template-titlepage.docx",
    #                          "teaching-data.xlsx",
    #                          "teaching-records.xlsx")

    config_filepath = "/home/fred/github/xdufacool/tests/data/teaching.ini"
    courses, terms, template_filepath = load_config(config_filepath)

    # exams = {key: value.exam_pdf_to_image() for key, value in terms.items()}
    for course in courses:
        print(course)
        course.compose_summary(template_filepath, terms[course.semester])

    # print(config.sections())
    # for cls in classes:
    #     data = dict(config.items(cls))
    #     course = data['course']
    #     data.update(config.items(course))

    #     composer = SummaryComposer(data)
        # composer.add_teaching_record(wb_records)
        # composer.add_framed_section("课程教学目标及与毕业要求的对应关系")
        # composer.add_framed_section("课程考核方式及成绩评定原则")
        # # composer.add_teaching_goal()
        # # composer.add_scoring_rules()
        # composer.add_score_table(wb)
        # composer.add_exam_table(wb)
        # composer.add_framed_section("试卷（卷面）分析及总结")
        # composer.add_framed_section("课程能力达成度分析及总结")
        # # composer.add_exam_analysis()
        # # composer.add_ability_analysis()
        # composer.save(summary_filename)
        

    # markdown_path = path.join(TEACHDIR, '2021-2022学年第二学期-02.md')
    # md2docx = Markdown2Docx(markdown_path)
    
    # testing_docx()
    # add_score_table()

    # form_auto_merge()
    # convert_merge_replace()
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
