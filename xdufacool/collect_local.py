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
from zipfile import ZipFile
import subprocess as subproc

import csv
import nbformat
from nbconvert import LatexExporter
import subprocess
import logging
import zipfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("collect_local.log"),  # Log to a file
        logging.StreamHandler(sys.stdout)  # Also log to the console
    ]
)

# Get the StreamHandler for stdout
stdout_handler = None
for handler in logging.getLogger().handlers:
    if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
        stdout_handler = handler
        break

# Set the level for stdout handler to WARNING
if stdout_handler:
    stdout_handler.setLevel(logging.WARNING)

def temporal_func():
    classid = sys.argv[1]

    folders = glob.glob(classid + '-*')

    for fld in folders:
        if not os.path.isdir(fld):
            continue
        logging.info(fld)
        subfolders = os.listdir(fld)
        for stu in subfolders:
            if os.path.isdir(stu):
                stu_id = stu
                logging.info(stu_id)

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
    
    def remove_hidden_folders(directory):
        """Remove hidden folders in the specified directory."""
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if item.startswith('.') and os.path.isdir(item_path):
                shutil.rmtree(item_path)  # Remove the hidden directory

    try:
        # Remove hidden folders in the directory of the input zip file
        zip_dir = os.path.dirname(ipynb_file)  # Get the directory of the input zip file
        # remove_hidden_folders(zip_dir)  # Call the function to remove hidden folders

        # Move the unzipped file to the directory containing the input zip file
        unzipped_file = os.path.basename(ipynb_file)  # Get the basename of the ipynb file
        target_path = os.path.join(zip_dir, unzipped_file)  # Target path in the zip directory
        os.rename(ipynb_file, target_path)  # Move the file

        with open(target_path, 'r', encoding='utf-8') as f:  # Use the moved file
            nb = nbformat.read(f, as_version=4)

            # Truncate long outputs
            truncate_long_outputs(nb)

            # Set metadata using the provided arguments
            if 'metadata' not in nb:
                nb.metadata = {}
            nb.metadata['title'] = assignment_title
            nb.metadata['authors'] = [{"name": f"{student_name} (ID: {student_id})"}]
            nb.metadata['date'] = ""

            # Configure the LaTeX exporter with custom template
            latex_exporter = LatexExporter()
            latex_exporter.exclude_input = False
            latex_exporter.exclude_output = False
            
            # Convert to LaTeX
            (body, resources) = latex_exporter.from_notebook_node(nb)

            # Ensure output directory exists
            output_dir = os.path.dirname(target_path)  # Use the new target path
            os.makedirs(output_dir, exist_ok=True)
            
            # Ensure required figures are available
            ensure_figures_available(assignment_dir, output_dir, figures)
            
            # Create figures directory if it doesn't exist
            figures_dir = os.path.join(output_dir, 'figures')
            os.makedirs(figures_dir, exist_ok=True)
            
            # Save figures if they exist in resources
            if 'outputs' in resources:
                for filename, data in resources['outputs'].items():
                    figure_path = os.path.join(figures_dir, filename)
                    with open(figure_path, 'wb') as f:
                        f.write(data)
                    
                    # Update the figure path in LaTeX content to use relative path
                    body = body.replace(filename, os.path.join('figures', filename))
            
            # Save LaTeX file
            tex_file = target_path.replace('.ipynb', '.tex')
            with open(tex_file, 'w', encoding='utf-8') as f:
                f.write(body)
            
            # Store current directory
            original_dir = os.getcwd()
            
            try:
                os.chdir(output_dir)
                tex_basename = os.path.basename(tex_file)
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
                    # logging.info(parent_dir)
                    relpathfile = os.path.relpath(pathfile, parent_dir)
                    # logging.info("PDF:", relpathfile)
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
        pdf_file = process_ipynb_submission(
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

if __name__ == "__main__":
    mapping_csv = "student_mapping.csv"
    base_dir = "."

    assignments = ["HW24E01", "HW24E02", "HW24E03", "HW24E04", "HW24E05"]
    for assignment_id in assignments[-1:]:
        ## Clean up existing files first
        # cleaned = clear_homework_path(assignment_id)
        # logging.info(f"Cleaned {cleaned} directories")
        
        # Formalize the submissions
        formalized = formalize_homework_submissions(assignment_id, mapping_csv)
        logging.info(f"Formalized {formalized} submissions")

        # Report processing
        formalized_report_dir = os.path.join(base_dir, f"MLEN-{assignment_id}-formalized")
        if os.path.exists(formalized_report_dir):
            report_files = collect_reports(formalized_report_dir)
            if report_files:
                title = f"MLEN-{assignment_id}: Reports"
                merged_report_path = os.path.join(formalized_report_dir, f"MLEN-{assignment_id}-reports.pdf")
                merge_pdfs(title, report_files, merged_report_path)
                logging.info(f"Created merged PDF for {assignment_id}: {merged_report_path}")
            else:
                logging.warning(f"No report files found in {formalized_report_dir}")
        else:
            logging.warning(f"Formalized directory not found for report assignment: {formalized_report_dir}")

    # # Generate merged submissions for all formalized homeworks
    # generate_merged_submissions(assignments[:4], base_dir)

# collect_local.py ends here
