# -*- encoding: utf-8 -*-
# collect_local.py ---
#
# Filename: collect_local.py
# Author: Fred Qi
# Created: 2017-01-03 20:35:44(+0800)
#
# Last-Updated: 2024-02-04 15:21:33(+0800) [by Fred Qi]
#     Update #: 575
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
import os
import sys
import glob
import shutil
from pathlib import Path
from zipfile import ZipFile
import subprocess as subproc

import csv
import nbformat
import subprocess
import logging
import zipfile
import tempfile
from datetime import date, datetime

try:
    from xdufacool.converters import LaTeXConverter    
    from xdufacool.converters import NotebookConverter
    from xdufacool.converters import PDFCompiler
except ImportError:
    from .converters import LaTeXConverter
    from .converters import NotebookConverter
    from .converters import PDFCompiler
# # Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s - %(levelname)s - %(message)s",
#     handlers=[
#         logging.FileHandler("collect_local.log"),  # Log to a file
#         logging.StreamHandler(sys.stdout)  # Also log to the console
#     ]
# )

# # Get the StreamHandler for stdout
# stdout_handler = None
# for handler in logging.getLogger().handlers:
#     if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
#         stdout_handler = handler
#         break

# # Set the level for stdout handler to WARNING
# if stdout_handler:
#     stdout_handler.setLevel(logging.WARNING)

# Add the parent directory of xdufacool to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def temporal_func():
    classid = sys.argv[1]

    folders = glob.glob(classid + '-*')

    for fld in folders:
        if not os.path.isdir(fld):
            continue
        logging.info(fld)
        subfolders = os.listdir(fld)
        for sfld in subfolders:
            if sfld.startswith('20'):
                logging.info('  ' + sfld)
                files = os.listdir(os.path.join(fld, sfld))
                for afile in files:
                    if afile.endswith('.pdf'):
                        logging.info('    ' + afile)

def move_file():
    """Move files out of sub-directories in the current working directory."""
    # logging.info("\n".join(os.listdir(filepath)))
    # folders = [os.path.join(filepath, fld) for fld in os.listdir(filepath)]
    # logging.info(filepath + ":\n  " + "\n  ".join(folders))
    folders = filter(os.path.isdir, os.listdir(u"."))
    # logging.info("Sub-folders: ", u"\n".join(folders))
    for folder in folders:
        files = [os.path.join(folder, fn) for fn in os.listdir(folder)]
        files = filter(os.path.isfile, files)
        for fn in files:
            _, filename = os.path.split(fn)
            shutil.move(fn, filename)
        assert 0 == len(os.listdir(folder))

def extract_rar(filename):
    """Filename include path."""
    cwd = os.getcwd()
    filepath, filename = os.path.split(filename)
    logging.info(f"Extracting {filename} in {filepath}")
    os.chdir(filepath)
    subproc.call(["7z", "x", "-y", filename], stdout=subproc.PIPE)
    move_file()
    os.chdir(cwd)

def extract_zip(filename):
    """Filename include path."""
    code_pages = [u"ascii", u"utf-8", u"GB18030", u"GBK", u"GB2312", u"hz"]
    cwd = os.getcwdu()
    filepath, filename = os.path.split(filename)
    os.chdir(filepath)
    zip_obj = ZipFile(filename, 'r')
    names = zip_obj.namelist()
    logging.info(f"Extracting {filename} in {filepath}")
    for name in names:
        if name[-1] == "/" or os.path.isdir(name):
            logging.info(f"  Skipping directory: {name}")
            continue
        if name.find("__MACOSX") >= 0:
            logging.info(f"  Skipping: {name}")
            continue
        succeed = False
        name_sys = name
        for coding in code_pages:
            try:
                name_sys = name.decode(coding)
                succeed = True
            except:
                succeed = False
            if succeed:
                break
        _, name_sys = os.path.split(name_sys)
        the_file = zip_obj.open(name, 'r')
        contents = the_file.read()
        the_file.close()
        the_file = open(name_sys, 'w')
        the_file.write(contents)
        the_file.close()
    zip_obj.close()
    # move_file()
    os.chdir(cwd)

def check_local_homeworks(folders, scores):
    """Check local homeworks."""
    re_id = re.compile(r'(?P<stuid>[0-9]{10,11})')
    for folder, sc in zip(folders, scores):
        files = glob.glob(folder + "/*/*.py")
        files += glob.glob(folder + "/*/*.ipynb")
        homeworks = dict()
        for filename in files:
            m = re_id.search(filename)
            if m is not None:
                stu_id = m.group('stuid')
                homeworks[stu_id] = [sc]
        write_dict_to_csv(folder + ".csv", homeworks)

def find_duplication(homework):
    """Find duplications in submitted homework."""
    re_id = re.compile(r'(?P<stuid>[0-9]{10,11})')
    dup_check = dict()
    with open(homework, 'r') as data:
        lines = data.readlines()
        for ln in lines:
            dt = ln.split()
            csum, right = dt[0], dt[1]
            if csum not in dup_check:
                dup_check[csum] = list()
            m = re_id.search(right)
            if m is not None:
                stu_id = m.group('stuid')
                dup_check[csum].append(stu_id)
    dup_check = filter(lambda k, v: len(v) > 1, dup_check.items())
    dup_check = [(key, sorted(val)) for key, val in dup_check]
    return dup_check

def display_dup(dup_result):
    """Display the duplication check results."""
    lines = [k + ": " + ", ".join(v) for k, v in dup_result]
    return lines

def load_csv_to_dict(filename):
    """Load a CSV file into a dict with the first column as the key."""
    row_len = list()
    result = dict()
    with open(filename, 'r') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            key = row[0].strip()
            values = [v.strip() for v in row[1:]]
            result[key] = values
            row_len.append(len(values))
    return result, max(row_len)

def write_dict_to_csv(filename, data):
    """Write a dictionary to a CSV file with the key as the first column."""
    with open(filename, 'w') as csvfile:
        writer = csv.writer(csvfile)
        keys = sorted(data.keys())
        for key in keys:
            value = data[key]
            row = [str(key)] + [str(v) for v in value]
            writer.writerow(row)

def merge_csv(csv_files):
    """Merge CSV files based on keywords."""
    results = dict()
    data_all = list()
    keys = set()
    for filename in csv_files:
        data, row_len = load_csv_to_dict(filename)
        keys |= set(data.keys())
        data_all.append((data, row_len))
    for key in keys:
        values = list()
        for value, row_len in data_all:
            fill = ["0"]*row_len
            dt = value[key] if key in value else fill
            values.extend(dt)
        results[key] = values
    return results

def collect_figures_from_assignment(assignment_dir):
    """
    Collects a list of figure filenames from the assignment directory.

    Args:
        assignment_dir (str): Path to the original assignment directory.

    Returns:
        list: List of figure filenames found in the assignment directory.
    """
    figures = []
    for filename in os.listdir(assignment_dir):
        if filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.pdf')):  # Add other image formats if needed
            figures.append(filename)
    return figures

def ensure_figures_available(assignment_dir, figures_dir, figures):
    """
    Ensure that all required figures are available in the output directory.
    If a figure is missing, copy it from the assignment directory.

    Args:
        assignment_dir (str): Path to the original assignment directory.
        output_dir (str): Path to the directory where the LaTeX file is being processed.
        figures (list): List of figure filenames required for the assignment.
    """
    os.makedirs(figures_dir, exist_ok=True)

    for figure in figures:
        figure_path = os.path.join(figures_dir, figure)
        if not os.path.exists(figure_path):
            source_path = os.path.join(assignment_dir, figure)
            if os.path.exists(source_path):
                logging.info(f"Copying missing figure '{figure}' from assignment directory.")
                shutil.copy2(source_path, figure_path)
            else:
                logging.warning(f"Figure '{figure}' is missing and not found in assignment directory.")

def truncate_long_outputs(nb, max_lines=128):
    """Truncates long outputs in a notebook object, keeping the first and last max_lines/2 lines.

    Args:
        nb (nbformat.NotebookNode): The notebook object.
        max_lines (int): The maximum number of lines allowed for an output.
    """
    half_lines = int(max_lines / 2)
    for cell in nb.cells:
        if cell.cell_type == 'code':
            for output in cell.outputs:
                if 'text' in output:
                    if isinstance(output['text'], str):
                        lines = output['text'].splitlines()
                        if len(lines) > max_lines:
                            output['text'] = '\n'.join(lines[:half_lines])
                            output['text'] += '\n...[Output truncated due to length]...\n'
                            output['text'] += '\n'.join(lines[-half_lines:])
                elif 'data' in output and 'text/plain' in output['data']:
                    if isinstance(output['data']['text/plain'], str):
                        lines = output['data']['text/plain'].splitlines()
                        if len(lines) > max_lines:
                            output['data']['text/plain'] = '\n'.join(lines[:half_lines])
                            output['data']['text/plain'] += '\n...[Output truncated due to length]...\n'
                            output['data']['text/plain'] += '\n'.join(lines[-half_lines:])

def process_ipynb_submission(ipynb_file, student_name, student_id, assignment_title, assignment_dir, figures):
    """Convert a single ipynb file to LaTeX format, compile to PDF, and ensure figures are available."""

    try:
        # Initialize NotebookConverter
        converter = NotebookConverter()

        # Move the unzipped file to the directory containing the input zip file
        zip_dir = os.path.dirname(ipynb_file)
        unzipped_file = os.path.basename(ipynb_file)
        target_path = os.path.join(zip_dir, unzipped_file)
        os.rename(ipynb_file, target_path)

        # Set metadata for the notebook
        with open(target_path, 'r', encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)
        if 'metadata' not in nb:
            nb.metadata = {}
        nb.metadata['title'] = assignment_title
        nb.metadata['authors'] = [{"name": f"{student_name} (ID: {student_id})"}]
        nb.metadata['date'] = ""
        with open(target_path, 'w', encoding='utf-8') as f:
            nbformat.write(nb, f)

        # Convert to LaTeX
        output_dir = os.path.dirname(target_path)
        tex_file = converter.convert_notebook(target_path, output_dir, figures)

        if tex_file is None:
            return None

        # Store current directory
        original_dir = os.getcwd()

        try:
            # Change to output directory for compilation
            os.chdir(output_dir)
            tex_basename = os.path.basename(tex_file)

            # Compile to PDF using latexmk
            subprocess.run(
                ['latexmk', '-pdfxe', '-quiet', tex_basename],
                check=True,
                stdout=subprocess.DEVNULL,  # Suppress standard output
                stderr=subprocess.DEVNULL   # Suppress error output
            )

            # Cleanup auxiliary files, excluding checkpoints
            for ext in ['.aux', '.log', '.out']:
                aux_file = tex_basename.replace('.tex', ext)
                if os.path.exists(aux_file):
                    os.remove(aux_file)

            # Return the full path to the generated PDF
            pdf_file = tex_basename.replace('.tex', '.pdf')
            if os.path.exists(pdf_file):
                pathfile = os.path.join(output_dir, pdf_file)
                parent_dir = os.path.dirname(output_dir)
                relpathfile = os.path.relpath(pathfile, parent_dir)
                return relpathfile

        finally:
            # Always return to original directory
            os.chdir(original_dir)

    except Exception as e:
        logging.error(f"Error processing {ipynb_file}: {str(e)}")
        return None

def merge_pdfs(title, pdf_files, output_pdf):
    """Merge multiple PDF files into a single PDF using pdfpages."""
    try:
        # Create a master LaTeX document for merging PDFs
        master_content = r"""
\documentclass{article}
\usepackage{pdfpages}
\usepackage[colorlinks=true]{hyperref}
"""
        master_content += f"\\title{{{title}}}\n\\author{{}}\n\\date{{}}\n"
        master_content += r"""
\begin{document}
\maketitle
% Table of Contents
\tableofcontents
\newpage

"""
        # Add each PDF with a bookmark and section
        for item in pdf_files:
            pdf_file, student_name, student_id, assignment_title = item
            toc_title = f"{student_name} ({student_id})"
            master_content += f"\\includepdf[pages=-,addtotoc={{1,section,1,{toc_title},sec:{student_id}}}]{{{pdf_file}}}\n"

        master_content += "\n\\end{document}"
        
        master_tex = output_pdf.replace(".pdf", ".tex")
        with open(master_tex, 'w', encoding='utf-8') as f:
            f.write(master_content)
        subprocess.run(
            ['latexmk', '-cd', '-interaction=nonstopmode', '-quiet', '-pdf', master_tex],
            check=True,
            stdout=subprocess.DEVNULL,  # Suppress standard output
            stderr=subprocess.DEVNULL   # Suppress error output
            )
        logging.info(f"Created merged PDF: {output_pdf}")
        return True
        
    except Exception as e:
        logging.error(f"Error merging PDFs: {str(e)}")
        return False

def process_ipynb_submissions(zip_file, assignment_dir, figures, merge=True):
    """Process all ipynb submissions in a zip file."""
    output_dir = os.path.dirname(zip_file)
    with ZipFile(zip_file, 'r') as zip_ref:
        items = [
            item for item in zip_ref.namelist() 
            if not (item.endswith('/') or '@PaxHeader' in item or '__MACOSX' in item or '__pycache__' in item)
        ]
            
        common_path = os.path.commonpath(items) if len(items) > 1 else os.path.dirname(items[0])
        # logging.info(f"Common path: {common_path}")
        
        for item in items:
            item_wocp = os.path.relpath(item, common_path)
            if item_wocp.startswith('.'):
                # item_path = os.path.join(output_dir, item)
                logging.info(f"Skipping: {item}")
                continue

            zip_ref.extract(item, output_dir)
            extracted_file_path = os.path.join(output_dir, item)
            new_file_path = os.path.join(output_dir, item_wocp)
            new_dir = os.path.dirname(new_file_path)
            os.makedirs(new_dir, exist_ok=True)  # Create the directory if it doesn't exist
            shutil.move(extracted_file_path, new_file_path)
    
    # Find all ipynb files, excluding checkpoints
    ipynb_files = []
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.endswith('.ipynb'):
                ipynb_files.append(os.path.join(root, file))
    # Extract submission info from file path
    student_name, student_id, assignment_title = extract_submission_info(zip_file)
    pdf_files = []    
    for ipynb_file in ipynb_files:
        # Process the notebook with extracted info
        # Create an instance of IpynbConverter
        ipynb_converter = IpynbConverter(latex_converter)
        pdf_file = ipynb_converter.convert_to_pdf(
            ipynb_file,
            student_name,
            student_id,
            assignment_title,
            assignment_dir,  # Pass assignment directory
            figures  # Pass list of figures
        )
        if pdf_file:
            pdf_files.append((pdf_file, student_name, student_id, assignment_title))
    return pdf_files

def extract_submission_info(zip_file):
    """Extract student ID, name and assignment info from file path."""
    basename = os.path.basename(zip_file)
    basename_no_ext = os.path.splitext(basename)[0]  # Remove the file extension
    parts = basename_no_ext.split('-')
    
    # Dictionary for homework titles
    homework_titles = {
        "HW24E01": "Linear Regression",
        "HW24E02": "Logistic Regression",
        "HW24E03": "Neural Networks",
        "HW24E04": "Convolutional Neural Networks"
    }
    
    # Retrieve title using the second part of the filename
    hwid = parts[1] if len(parts) > 1 else "Unknown"
    assignment_title = f"{homework_titles.get(hwid, 'Unknown')} ({hwid})"
    
    student_name = parts[3] if len(parts) > 3 else "Unknown"
    student_id = parts[2] if len(parts) > 2 else "Unknown"
    # logging.info(basename, parts)    
    return student_name, student_id, assignment_title

def clear_homework_path(assignment_id):
    """Clear homework path keeping only zip files for the given assignment ID.
    
    Args:
        assignment_id (str): The assignment ID (e.g., 'HW24E01')
        
    Returns:
        int: Number of directories cleaned
    """
    # Find all directories matching the assignment pattern
    assignment_dirs = glob.glob(f"MLEN-{assignment_id}/*")
    cleaned_count = 0
    
    for dir_path in assignment_dirs:
        if not os.path.isdir(dir_path):
            continue
            
        # Get all files and directories in the current path
        for root, dirs, files in os.walk(dir_path, topdown=False):
            # Remove all files except zip files
            for file in files:
                if not file.endswith('.zip'):
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        logging.error(f"Error removing file {file_path}: {e}")
            
            # Remove all subdirectories
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    shutil.rmtree(dir_path)
                except OSError as e:
                    logging.error(f"Error removing directory {dir_path}: {e}")
        
        cleaned_count += 1
        
    return cleaned_count

class StudentMapper:
    def __init__(self, mapping_csv, use_chinese_names=False):
        self.use_chinese_names = use_chinese_names
        self.student_map = self.load_student_mapping(mapping_csv)
        self.reverse_map = self.create_reverse_mapping()
        self.uku_id_pattern = re.compile(r'(?P<uku_id>[hH][0-9]{8})')
        self.xidian_id_pattern = re.compile(r'(?P<xidian_id>[0-9]{11}[xX]?)')

    def load_student_mapping(self, csv_file):
        """Load student mapping from CSV file."""
        student_map = {}
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                v1_id = row['英方学号'].strip().upper()
                xidian_id = row['西电学号'].strip().upper()
                if self.use_chinese_names:
                    english_name = row['姓名'].strip()
                else:
                    first_name = row['FIRST_NAME'].strip()
                    last_name = row['LAST_NAME'].strip()
                    english_name = f"{first_name} {last_name}"
                student_map[v1_id] = (xidian_id, english_name)
        return student_map

    def create_reverse_mapping(self):
        """Create a reverse mapping from Xidian ID to name."""
        reverse_map = {}
        for uku_id, (xidian_id, name) in self.student_map.items():
            reverse_map[xidian_id] = name
        return reverse_map

    def get_student_info(self, filename, directory):
        """Retrieve student info based on IDs found in filename or directory."""
        uku_id = self.extract_id(self.uku_id_pattern, filename, directory)
        xidian_id = self.extract_id(self.xidian_id_pattern, filename, directory)

        if uku_id and uku_id in self.student_map:
            xidian_id, name = self.student_map[uku_id]
            return xidian_id, name
        elif xidian_id and xidian_id in self.reverse_map:
            name = self.reverse_map[xidian_id]
            return xidian_id, name
        return None

    def extract_id(self, pattern, filename, directory):
        """Extract ID using a regex pattern from filename or directory."""
        match = pattern.search(filename)
        if match:
            return match.group(0).upper()
        match = pattern.search(os.path.basename(directory))
        if match:
            return match.group(0).upper()
        return None

def formalize_homework_submissions(assignment_id, mapping_csv, use_chinese_names=False):
    """Formalize homework submissions using student mapping.  Handles both zip and non-zip submissions."""
    # Initialize the StudentMapper
    student_mapper = StudentMapper(mapping_csv)

    base_dir = f"MLEN-{assignment_id}"
    formalized_dir = os.path.join(os.path.dirname(base_dir), f"MLEN-{assignment_id}-formalized")
    os.makedirs(formalized_dir, exist_ok=True)

    formalized_count = 0

    for root, _, files in os.walk(base_dir):
        for file in files:
            full_path = os.path.join(root, file)
            student_info = student_mapper.get_student_info(file, root)

            if not student_info:
                logging.warning(f"No mapping found for file: {file}")
                continue

            xidian_id, english_name = student_info
            student_dir = os.path.join(formalized_dir, xidian_id)
            os.makedirs(student_dir, exist_ok=True)

            if file.endswith(".zip"):
                formalized_name = f"MLEN-{assignment_id}-{xidian_id}-{english_name}.zip"
                dst_path = os.path.join(student_dir, formalized_name)
                try:
                    shutil.copy2(full_path, dst_path)
                    formalized_count += 1
                    logging.info(f"Formalized: {file} -> {formalized_name}")
                except OSError as e:
                    logging.error(f"Error copying {file}: {e}")
            elif file.endswith((".pdf")):
                formalized_name = f"MLEN-{assignment_id}-{xidian_id}-{english_name}.pdf"
                dst_path = os.path.join(student_dir, formalized_name)
                try:
                    shutil.copy2(full_path, dst_path)
                    formalized_count += 1
                    logging.info(f"Formalized: {file} -> {formalized_name}")
                except OSError as e:
                    logging.error(f"Error copying {file}: {e}")
            else:
                logging.info(f"Skipping file {file} (not a zip or pdf)")

    return formalized_count

def generate_merged_submissions(assignments, base_dir):
    """Generate merged submissions for all formalized homeworks."""
    directories = {"HW24E01": "regression",
                   "HW24E02": "classification",
                   "HW24E03": "neural-nets",
                   "HW24E04": "conv-nets"}
    
    for assignment_id in assignments:
        formalized_dir = os.path.join(base_dir, f"MLEN-{assignment_id}-formalized")
        if not os.path.exists(formalized_dir):
            logging.warning(f"Formalized directory {formalized_dir} not found.")
            continue

        # Collect figures from the assignment directory
        assignment_dir = os.path.join("/home/fred/lectures/PRML/exercise", directories[assignment_id])
        figures = collect_figures_from_assignment(assignment_dir)

        # Process all zip files in the formalized directory
        pdf_files = []
        for root, _, files in os.walk(formalized_dir):
            for file in files:
                if file.endswith('.zip'):
                    zip_path = os.path.join(root, file)
                    submission_pdfs = process_ipynb_submissions(zip_path, assignment_dir, figures)
                    if submission_pdfs:
                        pdf_files.extend(submission_pdfs)

        if not pdf_files:
            logging.warning(f"No PDF files generated for {assignment_id}")
            continue

        # Merge all PDFs into a single file
        title = f"MLEN-{assignment_id}: {directories[assignment_id].capitalize()}"
        output_pdf = os.path.join(formalized_dir, f"MLEN-{assignment_id}-merged.pdf")
        merge_pdfs(title, pdf_files, output_pdf)
        logging.info(f"Created merged PDF for {assignment_id}: {output_pdf}")

def collect_reports(formalized_dir):
    """Collects PDF report files from a formalized assignment directory.

    Args:
        formalized_dir: The directory containing student report submissions.

    Returns:
        list: A list of PDF file paths.  Returns an empty list if no suitable files are found.
    """
    report_files = []
    for root, _, files in os.walk(formalized_dir):
        for filename in files:
            if filename.endswith(".pdf"):
                filepath = os.path.join(root, filename)
                parts = os.path.basename(filename).split("-")
                student_id, student_name = parts[2], parts[3]
                report_relpath = os.path.relpath(filepath, formalized_dir)
                item = (report_relpath, student_name, student_id, "Report")
                report_files.append(item)
            elif filename.endswith(".zip"):
                zip_filepath = os.path.join(root, filename)
                parts = os.path.basename(filename).split("-")
                student_id, student_name = parts[2], parts[3]
                try:
                    with ZipFile(zip_filepath, 'r') as zip_ref:
                        for member in zip_ref.infolist():
                            if member.filename.endswith(".pdf"):
                                extracted_filepath = os.path.join(root, member.filename)
                                zip_ref.extract(member, root)
                                report_relpath = os.path.relpath(extracted_filepath, formalized_dir)
                                item = (report_relpath, student_name, student_id, "Report")
                                report_files.append(item)
                                break  # Extract only the first PDF
                except zipfile.BadZipFile as e:
                    logging.error(f"Error decompressing zip file {zip_filepath}: {e}")
    return report_files

def process_zip_submission(zip_filepath):
    """
    Processes a zip submission, extracting contents to a temporary directory.
    Handles PDF and IPYNB files based on assignment type inferred from the file name.

    Args:
        zip_filepath (str): Path to the zip file.

    Returns:
        str: Path to the processed PDF file, or None if no suitable file was found.
    """
    # Extract information from the file name
    filename = os.path.basename(zip_filepath)
    match = re.match(r"(?P<course_key>[A-Z]{4})-(?P<assignment_id>HW\d+[A-Z]\d+)-(?P<student_id>[0-9]{11}X?)-(?P<student_name>.+)\.zip", filename, re.IGNORECASE)
    
    if not match:
        logging.error(f"Filename format is incorrect: {filename}")
        return None

    course_key = match.group('course_key')
    assignment_id = match.group('assignment_id')
    student_id = match.group('student_id')
    student_name = match.group('student_name')
    assignment_type = "coding"
    try:
        # Create a temporary directory with a UUID as part of its name
        with tempfile.TemporaryDirectory(prefix=f"{course_key}-") as temp_dir:
            temp_dir = Path(temp_dir)
            logging.info(f"Created temporary directory: {temp_dir}")

            with ZipFile(zip_filepath, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            pdf_files = glob.glob(os.path.join(temp_dir, "**/*.pdf"), recursive=True)
            ipynb_files = glob.glob(os.path.join(temp_dir, "**/*.ipynb"), recursive=True)

            if assignment_type == "report" and pdf_files:
                # Report assignment, prioritize PDF
                pdf_file = pdf_files[0]  # Assume first PDF is the relevant one
                logging.info(f"Found PDF file for report assignment: {pdf_file}")
                return pdf_file
            elif assignment_type == "coding" and ipynb_files:
                # Coding assignment, process IPYNB
                ipynb_file = ipynb_files[0]  # Assume first IPYNB is the relevant one
                logging.info(f"Found IPYNB file for coding assignment: {ipynb_file}")
                # Initialize NotebookConverter
                converter = NotebookConverter()
                metadata = {
                    'title': assignment_id,
                    'authors': [{"name": f"{student_name} (ID: {student_id})"}],
                    'date': datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                tex_file = converter.convert_notebook(ipynb_file, [], metadata)
                if tex_file is None:
                    return None
                # Compile to PDF using PDFCompiler
                pdf_compiler = PDFCompiler()
                pdf_file = pdf_compiler.compile(tex_file, str(temp_dir), False)
                if pdf_file:
                    src_path = Path(zip_filepath).parent
                    dest_file = f"{course_key}-{assignment_id}-{student_id}-{student_name}.pdf"
                    shutil.move(pdf_file, src_path / dest_file)
                    return src_path / dest_file
                else:
                    logging.error(f"Failed to compile PDF for {ipynb_file}")

            else:
                logging.warning(f"No suitable PDF or IPYNB file found in {zip_filepath}")
                return None

    except Exception as e:
        logging.error(f"Error processing {zip_filepath}: {str(e)}")
        return None
    finally:
        # Clean up the temporary directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            logging.info(f"Removed temporary directory: {temp_dir}")

class HomeworkManager:
    """
    Manages student homework submissions.

    Organizes submissions by assignment ID and student ID, handles various
    file formats (zip, pdf, docx, doc, rar, 7z, tar.gz), extracts zip files,
    converts ipynb files to PDF, and selects the latest submission for
    evaluation.
    """

    def __init__(self, base_dir, course_id, mapping_csv=None, assignment_ids=None):
        """
        Initializes the HomeworkManager.

        Args:
            base_dir (str): The base directory where student submissions are located.
            course_id (str): The course identifier (e.g., 'MLEN', 'PRML').
            mapping_csv (str, optional): Path to the CSV file containing student ID mappings.
                                      If None, student info will be extracted from filenames.
            assignment_ids (list, optional): List of specific assignment IDs to process.
                                          If None, processes all assignments.
        """
        self.base_dir = base_dir
        self.course_id = course_id
        self.student_mapper = StudentMapper(mapping_csv) if mapping_csv else None
        self.assignment_ids = assignment_ids
        self.assignments = {}  # Dictionary to store submissions by assignment ID
        self.latex_converter = LaTeXConverter()

    def collect_submissions(self):
        """
        Collects and organizes homework submissions from the base directory.
        Only processes directories that match the specified assignment IDs.
        """
        # If no specific assignments are specified, scan all directories
        if not self.assignment_ids:            
            for root, _, files in os.walk(self.base_dir):
                for file in files:
                    submission_info = self.extract_submission_info(file, root)
                    if submission_info:
                        self.add_submission(submission_info)
            return

        # Process only directories containing specified assignment IDs
        for assignment_id in self.assignment_ids:
            # Use glob to find all directories containing the assignment ID
            file_pattern = f"{self.base_dir}/{self.course_id}*{assignment_id}*/**"
            logging.info(f"Searching for files matching pattern: {file_pattern}")
            submission_files = glob.glob(file_pattern, recursive=True)
            for file_path in submission_files:
                if not os.path.isfile(file_path):
                    continue
                logging.info(f"Processing {file_path}")
                filename = os.path.basename(file_path)
                root = os.path.dirname(file_path)
                submission_info = self.extract_submission_info(filename, root)
                logging.info(f"    {submission_info}")
                if submission_info and submission_info["assignment_id"] == assignment_id:
                    self.add_submission(submission_info)
                        
            logging.info(f"Processed submissions for assignment: {assignment_id}")

    def _should_process_assignment(self, assignment_id):
        """
        Checks if an assignment should be processed based on assignment_ids filter.

        Args:
            assignment_id (str): The assignment ID to check.

        Returns:
            bool: True if the assignment should be processed, False otherwise.
        """
        return self.assignment_ids is None or assignment_id in self.assignment_ids

    def extract_submission_info(self, filename, root):
        """
        Extracts submission information from a file.

        Args:
            filename (str): The name of the file.
            root (str): The root directory containing the file.

        Returns:
            dict: Submission information or None if invalid
        """
        file_path = os.path.join(root, filename)
        file_ext = os.path.splitext(filename)[1].lower()
        
        # Skip non-submission files
        if not self._is_valid_submission(filename, file_ext):
            return None
        logging.info(f"Processing file: {filename}")
        # Extract assignment ID from filename or directory structure
        assignment_id = self._extract_assignment_id(filename, root)
        if not assignment_id:
            return None

        # Get student information
        student_id, student_name = self.get_student_info(filename, root)
        if not student_id or not student_name:
            logging.warning(f"Could not identify student for file: {filename}")
            return None

        return {
            "file_path": file_path,
            "file_ext": file_ext,
            "assignment_id": assignment_id,
            "student_id": student_id,
            "student_name": student_name,
            "filename": filename
        }

    def add_submission(self, submission_info):
        """
        Adds a submission to the assignments dictionary.
        If multiple submissions exist for the same student and assignment,
        keeps the latest one based on file modification time.

        Args:
            submission_info (dict): Information about the submission
        """
        assignment_id = submission_info["assignment_id"]
        student_id = submission_info["student_id"]
        file_path = submission_info["file_path"]
        
        # Convert absolute path to relative path and remove file_path
        submission_info["rel_path"] = os.path.relpath(file_path, self.base_dir)
        submission_info["timestamp"] = os.path.getmtime(file_path)
        del submission_info["file_path"]

        # Initialize assignment dictionary if it doesn't exist
        if assignment_id not in self.assignments:
            self.assignments[assignment_id] = {}

        # Update if no previous submission exists or if new submission is more recent
        if (student_id not in self.assignments[assignment_id] or 
            submission_info["timestamp"] > self.assignments[assignment_id][student_id]["timestamp"]):
            self.assignments[assignment_id][student_id] = submission_info
            logging.info(f"Updated submission for {student_id} in {assignment_id}")

    def get_absolute_path(self, submission_info):
        """
        Gets the absolute path for a submission.

        Args:
            submission_info (dict): Submission information containing rel_path

        Returns:
            str: Absolute path to the submission file
        """
        return os.path.join(self.base_dir, submission_info["rel_path"])

    def extract_and_process_submissions(self):
        """
        Extracts zip files and processes their contents (PDF or ipynb).
        """
        for assignment_id, students in self.assignments.items():
            for student_id, submission_info in students.items():
                if submission_info["file_ext"] == ".zip":
                    self.process_zip_submission(submission_info)

    def process_zip_submission(self, submission_info):
        """
        Processes a zip submission: extracts contents, handles PDF and ipynb files.

        Args:
            submission_info (dict): Submission information.
        """
        zip_file = os.path.join(self.base_dir, submission_info["rel_path"])
        extract_dir = os.path.splitext(zip_file)[0]  # Directory for extraction

        try:
            with ZipFile(zip_file, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

            # Look for PDF or ipynb files in the extracted directory
            extracted_files = []
            for root, _, files in os.walk(extract_dir):
                for file in files:
                    extracted_files.append(os.path.join(root, file))

            pdf_files = [f for f in extracted_files if f.lower().endswith(".pdf")]
            ipynb_files = [
                f for f in extracted_files if f.lower().endswith(".ipynb")
            ]

            if pdf_files:
                # Use the first PDF found (if multiple, you might want to add logic)
                submission_info["rel_path"] = os.path.relpath(pdf_files[0], self.base_dir)
                submission_info["file_ext"] = ".pdf"
            elif ipynb_files:
                # Process ipynb files using process_ipynb_submission
                assignment_dir = os.path.join(
                    "/home/fred/lectures/PRML/exercise",
                    submission_info["assignment_id"],
                )
                figures = collect_figures_from_assignment(assignment_dir)
                pdf_file = process_ipynb_submission(
                    ipynb_files[0],
                    submission_info["student_name"],
                    submission_info["student_id"],
                    submission_info["assignment_id"],
                    assignment_dir,
                    figures,
                )
                if pdf_file:
                    submission_info["rel_path"] = os.path.relpath(pdf_file, self.base_dir)
                    submission_info["file_ext"] = ".pdf"

        except Exception as e:
            logging.error(f"Error processing zip submission {zip_file}: {e}")

    def organize_submissions(self):
        """
        Organizes submissions into a formalized directory structure.
        """
        for assignment_id, students in self.assignments.items():
            for student_id, submission_info in students.items():
                self.formalize_submission(submission_info)

    def formalize_submission(self, submission_info):
        """
        Copies a single submission to the formalized directory structure.

        Args:
            submission_info (dict): Submission information.
        """
        assignment_id = submission_info["assignment_id"]
        student_id = submission_info["student_id"]
        student_name = submission_info["student_name"]
        file_ext = submission_info["file_ext"]
        src_path = submission_info["file_path"]

        formalized_dir = os.path.join(
            self.base_dir, f"{self.course_id}-{assignment_id}-formalized"
        )
        student_dir = os.path.join(formalized_dir, student_id)
        os.makedirs(student_dir, exist_ok=True)

        formalized_name = (
            f"{self.course_id}-{assignment_id}-{student_id}-{student_name}{file_ext}"
        )
        dst_path = os.path.join(student_dir, formalized_name)

        try:
            shutil.copy2(src_path, dst_path)
            logging.info(f"Formalized: {src_path} -> {dst_path}")
        except OSError as e:
            logging.error(f"Error copying {src_path}: {e}")

    def get_student_info(self, filename, root):
        """
        Gets student information from mapping, filename, or directory path.

        Args:
            filename (str): The name of the file
            root (str): The root directory path

        Returns:
            tuple: (student_id, student_name)
        """
        # Try student mapper first if available
        if self.student_mapper:
            student_id, student_name = self.student_mapper.get_student_info(filename)
            if student_id and student_name:
                return student_id, student_name

        # Try to extract from filename
        try:
            parts = filename.split('-')
            logging.info(f"    {parts}")
            if len(parts) >= 2:
                student_id = parts[-2]
                student_name = os.path.splitext(parts[-1])[0]
                if self._is_valid_student_id(student_id):
                    return student_id, student_name
        except Exception:
            pass

        # Fall back to directory path
        try:
            # Assuming directory structure like ".../COURSEID-HWID/STUDENTID/..."
            path_parts = root.split(os.path.sep)
            for part in path_parts:
                if self._is_valid_student_id(part):
                    return part, "NoName"
        except Exception as e:
            logging.warning(f"Could not extract student info from path {root}: {e}")

        return None, None

    def _is_valid_student_id(self, student_id):
        """
        Validates if a string looks like a student ID.
        
        Args:
            student_id (str): The potential student ID
            
        Returns:
            bool: True if it looks like a valid student ID
        """
        # Adjust this pattern based on your student ID format
        # Example: 8-10 digits
        return bool(re.match(r'^\d{8,11}$', student_id))

    def _extract_assignment_id(self, filename, root):
        """
        Extracts assignment ID from filename or directory path.
        
        Args:
            filename (str): The name of the file
            root (str): The root directory path
            
        Returns:
            str: Assignment ID or None if not found
        """
        # Try to get from filename first
        try:
            parts = filename.split('-')
            if len(parts) >= 2:
                # Look for pattern like 'HW24A01' in filename
                for part in parts:
                    if re.match(r'HW\d+[A-Z]\d+', part):
                        return part
        except Exception:
            pass

        # Fall back to directory path
        try:
            # Assuming directory structure like ".../COURSEID-HWID/..." or ".../HWID/..."
            path_parts = root.split(os.path.sep)
            for part in path_parts:
                if '-' in part:
                    # Try to find assignment ID in directory name
                    dir_parts = part.split('-')
                    for dir_part in dir_parts:
                        if re.match(r'HW\d+[A-Z]\d+', dir_part):
                            return dir_part
                elif re.match(r'HW\d+[A-Z]\d+', part):
                    return part
        except Exception as e:
            logging.warning(f"Could not extract assignment ID from path {root}: {e}")
        
        return None

    def _is_valid_submission(self, filename, file_ext):
        """
        Checks if a file is a valid submission based on its extension.

        Args:
            filename (str): The name of the file.
            file_ext (str): The extension of the file.

        Returns:
            bool: True if the file is a valid submission, False otherwise.
        """
        # This is a placeholder implementation. You might want to implement
        # a more robust check based on your specific requirements.
        return file_ext in [".zip", ".pdf", ".ipynb"]

    def merge_assignment_pdfs(self):
        """
        Merges all PDF submissions for each assignment into a single PDF file.
        Uses LaTeXConverter for template rendering and PDF generation.
        """
        for assignment_id, students in self.assignments.items():
            pdf_files = []
            for student_id in sorted(students.keys()):  # Sort by student ID
                student_info = students[student_id]
                if student_info["file_ext"].lower() == ".pdf":
                    pdf_files.append((
                        student_info["rel_path"],
                        student_info["student_name"],
                        student_id
                    ))

            if not pdf_files:
                logging.warning(f"No PDF files found for assignment {assignment_id}")
                continue

            # Render template and compile PDF
            output_name = f"{self.course_id}-{assignment_id}-merged"
            
            try:
                latex_content = self.latex_converter.render_template(
                    'pdfmerge.tex.j2',
                    course_id=self.course_id,
                    assignment_id=assignment_id,
                    date=date.today().strftime("%Y-%m-%d"),
                    submissions=pdf_files  # Already sorted by student_id
                )
                with open(f"{output_name}.tex", "w") as f:
                    f.write(latex_content)
                pdf_path = self.latex_converter.compile_pdf(
                    f"{output_name}.tex",
                    self.base_dir,
                    output_name
                )
                
                if pdf_path:
                    logging.info(f"Successfully merged PDFs for {assignment_id} to {pdf_path}")
                else:
                    logging.error(f"Failed to merge PDFs for {assignment_id}")
                    
            except Exception as e:
                logging.error(f"Error processing {assignment_id}: {e}")

if __name__ == "__main__":
    pass
