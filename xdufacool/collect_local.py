# -*- encoding: utf-8 -*-
# collect_local.py ---
#
# Filename: collect_local.py
# Author: Fred Qi
# Created: 2017-01-03 20:35:44(+0800)
#
# Last-Updated: 2017-01-08 19:24:52(+0800) [by Fred Qi]
#     Update #: 473
#

# Commentary:
#
#
#

# Change Log:
#
#
#

# Remove the import statement as Python 2 is deprecated.
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


def temporal_func():
    classid = sys.argv[1]

    folders = glob.glob(classid + '-*')

    for fld in folders:
        if not os.path.isdir(fld):
            continue
        print(fld)
        subfolders = os.listdir(fld)
        for stu in subfolders:
            if os.path.isdir(stu):
                stu_id = stu
                print(stu_id)


def move_file():
    """Move files out of sub-directories in the current working directory."""
    # print("\n".join(os.listdir(filepath)))
    # folders = [os.path.join(filepath, fld) for fld in os.listdir(filepath)]
    # print(filepath + ":\n  " + "\n  ".join(folders))
    folders = filter(os.path.isdir, os.listdir(u"."))
    # print("Sub-folders: ", u"\n".join(folders))
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
    print(filepath, filename)
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
    print(filepath, filename)
    for name in names:
        if name[-1] == "/" or os.path.isdir(name):
            print("  Skipping: ", name)
            continue
        if name.find("__MACOSX") >= 0:
            print("  Skipping: ", name)
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


def process_ipynb_submission(ipynb_file, student_name, student_id, assignment_title):
    """Convert a single ipynb file to LaTeX format and compile to PDF."""
    
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
                for _ in range(3):  # Run twice for references
                    subprocess.run(
                        ['xelatex', '-interaction=nonstopmode', '-quiet', tex_basename],
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
                    # print(parent_dir)
                    relpathfile = os.path.relpath(pathfile, parent_dir)
                    # print("PDF:", relpathfile)
                    return relpathfile
                    
            finally:
                # Always return to original directory
                os.chdir(original_dir)
                
    except Exception as e:
        print(f"  ! Error processing {ipynb_file}: {str(e)}")
        return None


def merge_pdfs(pdf_files, output_pdf):
    """Merge multiple PDF files into a single PDF using pdfpages."""
    try:
        # Create a master LaTeX document for merging PDFs
        master_content = r"""
\documentclass{article}
\usepackage{pdfpages}
\usepackage{hyperref}

\begin{document}

% Table of Contents
\tableofcontents
\newpage

"""
        # Add each PDF with a bookmark and section
        for item in pdf_files:
            pdf_file, student_name, student_id, assignment_title = item
            toc_title = f"{assignment_title} from {student_name} ({student_id})"
            master_content += f"\\includepdf[pages=-,addtotoc={{1,section,1,{toc_title},sec:{student_id}}}]{{{pdf_file}}}\n\n"

        master_content += "\n\\end{document}"
        
        # Save master document
        output_dir = os.path.dirname(output_pdf)
        master_tex = os.path.join(output_dir, "merged_submissions.tex")
        with open(master_tex, 'w', encoding='utf-8') as f:
            f.write(master_content)
        subprocess.run(
            ['latexmk', '-cd', '-interaction=nonstopmode', '-quiet', '-pdf',master_tex],
            check=True,
            stdout=subprocess.DEVNULL,  # Suppress standard output
            stderr=subprocess.DEVNULL   # Suppress error output
            )
        subprocess.run(
            ['latexmk', '-cd', '-interaction=nonstopmode', '-quiet', '-c',master_tex],
            stdout=subprocess.DEVNULL,  # Suppress standard output
            stderr=subprocess.DEVNULL   # Suppress error output
            )
                
        print(f"  - Created merged PDF: {output_pdf}")
        return True
        
    except Exception as e:
        print(f"  ! Error merging PDFs: {str(e)}")
        return False


def process_ipynb_submissions(zip_file, merge=True):
    """Process all ipynb submissions in a zip file."""
    output_dir = os.path.dirname(zip_file)
    with ZipFile(zip_file, 'r') as zip_ref:
        items = [
            item for item in zip_ref.namelist() 
            if not (item.endswith('/') or '@PaxHeader' in item or '__MACOSX' in item or '__pycache__' in item)
        ]
            
        common_path = os.path.commonpath(items) if len(items) > 1 else os.path.dirname(items[0])
        # print(f"Common path: {common_path}")
        
        for item in items:
            item_wocp = os.path.relpath(item, common_path)
            if item_wocp.startswith('.'):
                # item_path = os.path.join(output_dir, item)
                print("  - Skipping: ", item)
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
            assignment_title
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
    # print(basename, parts)    
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
                        print(f"Error removing file {file_path}: {e}")
            
            # Remove all subdirectories
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    shutil.rmtree(dir_path)
                except OSError as e:
                    print(f"Error removing directory {dir_path}: {e}")
        
        cleaned_count += 1
        
    return cleaned_count


def load_student_mapping(csv_file):
    """Load student mapping from CSV file.
    
    Expected CSV format:
    姓名,西电学号,英方学号,FIRST_NAME,LAST_NAME
    张三,2023123456,123456,San,Zhang
    
    Args:
        csv_file (str): Path to CSV file containing student mappings
        
    Returns:
        dict: Mapping of v1_id to (xidian_id, english_name)
    """
    student_map = {}
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            v1_id = row['英方学号'].strip()
            xidian_id = row['西电学号'].strip()
            first_name = row['FIRST_NAME'].strip()
            last_name = row['LAST_NAME'].strip()
            english_name = f"{first_name} {last_name}"
            student_map[v1_id] = (xidian_id, english_name)
    return student_map

def formalize_homework_submissions(assignment_id, mapping_csv):
    """Formalize homework submissions using student mapping.
    
    Args:
        assignment_id (str): The assignment ID (e.g., 'HW24E01')
        mapping_csv (str): Path to CSV file containing student mappings
        
    Returns:
        int: Number of submissions formalized
    """
    # Load student mapping
    student_map = load_student_mapping(mapping_csv)
    
    # Find all directories and files matching the assignment pattern
    base_dir = f"MLEN-{assignment_id}"
    if not os.path.exists(base_dir):
        print(f"Assignment directory {base_dir} not found")
        return 0
        
    formalized_count = 0
    v1_id_pattern = re.compile(r'(?P<v1id>[H0-9]{8,9})')
    
    # Create formalized directory structure
    formalized_dir = os.path.join(base_dir, "formalized")
    os.makedirs(formalized_dir, exist_ok=True)
    
    # Find all zip files
    for root, _, files in os.walk(base_dir):
        for file in files:
            if not file.endswith('.zip'):
                continue
                
            # Extract v1 ID from original filename
            match = v1_id_pattern.search(file)
            if not match:
                print(f"  ! Could not extract v1 ID from {file}")
                continue
                
            v1_id = match.group('v1id')
            if v1_id not in student_map:
                print(f"  ! No mapping found for v1 ID: {v1_id}")
                continue
                
            # Get Xidian ID and English name
            xidian_id, english_name = student_map[v1_id]
            
            # Create formalized filename
            formalized_name = f"MLEN-{assignment_id}-{xidian_id}-{english_name}.zip"
            
            # Create student directory in formalized structure using only xidian_id
            student_dir = os.path.join(formalized_dir, xidian_id)
            os.makedirs(student_dir, exist_ok=True)
            
            # Copy and rename the zip file
            src_path = os.path.join(root, file)
            dst_path = os.path.join(student_dir, formalized_name)
            
            try:
                shutil.copy2(src_path, dst_path)
                formalized_count += 1
                print(f"  + Formalized: {file} -> {formalized_name}")
            except OSError as e:
                print(f"  ! Error copying {file}: {e}")
    
    return formalized_count


if __name__ == "__main__":
    assignment_id = "HW24E03"
    mapping_csv = "student_mapping.csv"  # Path to your mapping CSV file
    
    # # Clean up existing files first
    # cleaned = clear_homework_path(assignment_id)
    # print(f"Cleaned {cleaned} directories")
    
    # Formalize the submissions
    formalized = formalize_homework_submissions(assignment_id, mapping_csv)
    print(f"Formalized {formalized} submissions")

# collect_local.py ends here
