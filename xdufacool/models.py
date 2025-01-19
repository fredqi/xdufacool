from datetime import datetime
import os
import glob
import yaml
import shutil
import tarfile
import jupytext
from nbformat.v4 import new_markdown_cell, new_code_cell
from jinja2 import Environment, FileSystemLoader, meta
from pathlib import Path
import logging
import argparse
from xdufacool.utils import setup_logging, validate_paths
from xdufacool.converters import NotebookConverter, PDFCompiler, LaTeXConverter
from zipfile import ZipFile
import tempfile
from tqdm import tqdm

class Teacher:
    def __init__(self, teacher_id, name, email=None, department=None):
        self.teacher_id = teacher_id
        self.name = name
        self.email = email
        self.department = department

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

    def __str__(self):
        return f"{self.name} ({self.teacher_id})"

class Student:
    def __init__(self, student_id, name, email=None, major=None):
        self.student_id = student_id
        self.name = name
        self.email = email
        self.major = major

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

    def __str__(self):
        return f"{self.name} (ID: {self.student_id})"

class Course:
    def __init__(self, course_id, abbreviation, topic, semester, teachers, teaching_plan, course_year, start_date):
        self.course_id = course_id
        self.abbreviation = abbreviation
        self.topic = topic
        self.semester = semester
        self.teachers = teachers
        self.teaching_plan = teaching_plan
        self.assignments = []
        self.course_year = course_year
        self.start_date = start_date

    def add_assignment(self, assignment):
        self.assignments.append(assignment)

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

    def __str__(self):
        return f"{self.topic} ({self.course_id})"

    @classmethod
    def from_config(cls, config_path):
        """Loads a Course object from a YAML configuration file.

        Args:
            config_path (str): Path to the YAML configuration file.

        Returns:
            Course: A Course object populated with data from the config file.
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        course_config = config['course']
        start_date = course_config.get('start_date', datetime.now().strftime('%Y-%m-%d'))
        course_data = {
            'course_id': course_config['course_id'],
            'abbreviation': course_config['abbreviation'],
            'topic': course_config.get('topic', 'Unknown Topic'),
            'semester': course_config.get('semester', 'Unknown Semester'),
            'course_year': course_config.get('year', datetime.now().year),
            'start_date': datetime.strptime(start_date, '%Y-%m-%d')
        }

        # Handle teachers (assuming a list of teacher IDs in the config)
        teachers = []
        for teacher_id in course_config.get('teachers', []):
            # Assuming you have a way to retrieve Teacher objects by ID
            teacher = get_teacher_by_id(teacher_id)
            if teacher:
                teachers.append(teacher)
        course_data['teachers'] = teachers

        # Handle teaching plan (assuming a dictionary in the config)
        course_data['teaching_plan'] = course_config.get('teaching_plan', {})

        # Create the Course object using dictionary unpacking
        course = Course(**course_data)

        # Handle assignments
        for assignment_config in config['assignments']:
            assignment_type = assignment_config['type']
            if assignment_type == 'coding':
                logging.info(f"Creating CodingAssignment for {assignment_config}")
                assignment = CodingAssignment.from_dict(assignment_config, course)
            elif assignment_type == 'report':
                assignment = ReportAssignment(
                    assignment_id=assignment_config['assignment_id'],
                    course=course,
                    title=assignment_config['title'],
                    description=assignment_config['description'],
                    due_date=datetime.strptime(assignment_config['due_date'], '%Y-%m-%d'),
                    instructions=assignment_config['report_config']['instructions']
                )
            elif assignment_type == 'challenge':
                evaluation_metric = assignment_config['challenge_config']['evaluation_metric']
                assignment = ChallengeAssignment(
                    assignment_id=assignment_config['assignment_id'],
                    course=course,
                    title=assignment_config['title'],
                    description=assignment_config['description'],
                    due_date=datetime.strptime(assignment_config['due_date'], '%Y-%m-%d'),
                    evaluation_metric=evaluation_metric
                )
            else:
                raise ValueError(f"Unknown assignment type: {assignment_type}")

            course.add_assignment(assignment)

        return course

class Assignment:
    def __init__(self, assignment_id, course, title, description, due_date, max_score=100):
        self.assignment_id = assignment_id
        self.course = course
        self.title = title
        self.description = description
        self.due_date = due_date
        self.max_score = max_score
        self.submissions = {}
        self.accepted_extensions = {
            'compressed': ['.zip'],
            'document': ['.pdf']
        }
        self.alternative_extensions = {
            'compressed': ['.rar', '.tar.gz', '.7z', '.tar'],
            'document': ['.doc', '.docx']
        }
        self.files_to_convert = []

    def common_name(self):
        """Returns the common name of the assignment, combining course abbreviation and assignment ID."""
        return f"{self.course.abbreviation}-{self.assignment_id}"

    def add_submission(self, submission):
        self.submissions[submission.student.student_id] = submission

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

    def __str__(self):
        return f"{self.title} ({self.assignment_id})"

    def get_submission(self, student_id):
        return self.submissions.get(student_id)

    def generate_notification(self, course_context):
        """Generates a notification for the assignment using Jinja2 directly.

        Args:
            course_context (dict): A dictionary containing course-level information.
        """
        notification_template = course_context["notification_template"]

        env = Environment(loader=FileSystemLoader('.'))
        template = env.get_template(notification_template)
        required_keys = meta.find_undeclared_variables(env.parse(template.render()))
        remaining_keys = required_keys - set(course_context.keys()) - {'homework_id'}

        # Get assignment-specific context
        assignment_context = {
            'homework_desc': self.description,
            'deadline': self.due_date.strftime('%Y-%m-%d'),
            'teacher': self.course.teachers[0].name,  # Assuming one teacher for simplicity
            'course_abbrev': self.course.abbreviation,
            'serial_number': self.assignment_id.split('-')[-1],  # Extract serial number from assignment_id
            'course_year': self.course.course_year
        }
        full_context = {'homework_id': self.assignment_id, **course_context, **assignment_context}
        markdown_content = template.render(full_context)

        # Save the Markdown notification directly
        self.save_notification(markdown_content)

    def save_notification(self, markdown_content):
        """Saves the Markdown notification to a file."""
        try:
            output_md_path = f'notification-{self.common_name()}.md'
            with open(output_md_path, 'w') as f:
                f.write(markdown_content)
            print(f'Generated notification to: {output_md_path}')
        except Exception as e:
            print(f'Error during saving Markdown: {e}')

    def collect_submissions(self, base_dir):
        """
        Collects submissions for this assignment from a given directory.

        Args:
            submission_dir (str): The directory to search for submissions.

        Returns:
            list: A list of dictionaries, where each dictionary represents a submission
                  and contains the extracted information (e.g., student_id, assignment_id, file_path).
        """
        submission_dir = Path(base_dir) / self.common_name()
        logging.info(f"Collecting submissions from {submission_dir} ...")
        if not submission_dir.exists():
            logging.error(f"Error: Directory {submission_dir} does not exist.")
            return None        
        file_paths = list(submission_dir.rglob(f"{self.common_name()}*"))
        file_paths.sort(key=lambda x: (x.suffix.lower() != '.pdf', x))
        pbar = tqdm(file_paths, desc="Processing submissions")
        for file_path in pbar:
            relative_path = file_path.relative_to(submission_dir)
            logging.info(f"Processing: {relative_path}")
            if not file_path.is_file():
                logging.debug(f"Skipping {relative_path}")
                continue
            student_id, student_name = file_path.stem.split('-')[-2:]
            if not student_id in self.submissions:
                student = Student(student_id, student_name)
                pbar.set_description(f"Processing {student}")
                submission_date = datetime.fromtimestamp(file_path.stat().st_mtime)
                if isinstance(self, CodingAssignment):
                    submission_class = CodingSubmission
                elif isinstance(self, ReportAssignment):
                    submission_class = ReportSubmission
                elif isinstance(self, ChallengeAssignment):
                    submission_class = ChallengeSubmission
                else:
                    logging.debug(f"Unknown assignment type: {type(self)}")
                    continue
                submission = submission_class(self, student, submission_date)
                self.add_submission(submission)
            else:
                submission = self.submissions[student_id]
                logging.info(f"{submission} already exists.")

            file_ext = file_path.suffix.lower()
            if file_ext in self.accepted_extensions['compressed']:
                submission.generate_report(relative_path, submission_dir)
            elif file_ext in self.accepted_extensions['document']:
                submission.add_report(submission_dir, relative_path)                
            elif file_ext in self.alternative_extensions['document']:
                # TODO: Implement conversion from .doc, .docx to PDF
                logging.warning(f"To convert: {relative_path}")
            elif file_ext in self.alternative_extensions['compressed']:
                # TODO: Implement extraction of alternative compressed formats (e.g., .rar, .7z)
                logging.warning(f"To decompress manually: {relative_path}")
            else:
                logging.warning(f"Ignore: {relative_path}")

    def merge_submissions(self, base_dir, output_name=None):
        """
        Merges all PDF submissions for the assignment into a single PDF file.
        Uses LaTeXConverter for template rendering and PDF generation.
        """
        base_dir = Path(base_dir) / self.common_name()
        pdf_files = []
        for student_id in sorted(self.submissions.keys()):
            submission = self.submissions[student_id]
            if not submission.report_file:
                logging.warning(f"No report file found for {submission}")
                continue
            if isinstance(submission, ReportSubmission) or isinstance(submission, CodingSubmission):
                pdf_files.append((
                    submission.report_file,
                    str(submission.student.name),
                    student_id
                ))

        if not output_name:
            output_name = f"{self.common_name()}-merged"

        try:
            latex_converter = LaTeXConverter()

            latex_content = latex_converter.render_template(
                'pdfmerge.tex.j2',
                course_id=self.course.course_id,
                assignment_id=self.assignment_id,
                date=datetime.now().strftime("%Y-%m-%d"),
                submissions=pdf_files
            )
            tex_file = base_dir / f"{output_name}.tex"
            with open(tex_file, "w") as f:
                f.write(latex_content)

            pdf_compiler = PDFCompiler() 
            pdf_path = pdf_compiler.compile(tex_file, base_dir, True)

            if not pdf_path:
                logging.error(f"Failed to merge PDFs for {self.assignment_id}")
                return None
            
        except Exception as e:
            logging.error(f"Error processing {self.assignment_id}: {e}")
            return None

class ReportAssignment(Assignment):
    def __init__(self, assignment_id, course, title, description, due_date, instructions, max_score=100):
        super().__init__(assignment_id, course, title, description, due_date, max_score)
        self.instructions = instructions

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

class CodingAssignment(Assignment):
    def __init__(self, assignment_id, course, title, description, due_date,
                 environment_template=None, notebook=None, data=None, figures=None, assignment_folder=None):
        super().__init__(assignment_id, course, title, description, due_date)
        self.environment_template = environment_template
        self.notebook = notebook or {}
        self.data = data or []
        self.figures = figures or []
        self.assignment_folder = assignment_folder

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

    def prepare(self, output_dir):
        """Prepares the coding assignment by rendering the environment file, converting the Python script to a notebook, and copying necessary files."""
        # Use assignment_id for directory and tarball name
        assignment_id = self.assignment_id
        output_dir = Path(output_dir)

        # 1. Render environment file
        self.render_environment_file(assignment_id, output_dir)

        # 2. Convert Python script to notebook
        self.convert_py_to_ipynb(assignment_id, output_dir)

        # 3. Copy assignment files
        self.copy_assignment_files(assignment_id, output_dir)

        # 4. Generate tarball
        self.generate_exercise_tarball(assignment_id, output_dir)

    def render_environment_file(self, assignment_id, output_dir):
        """Renders the environment file using Jinja2."""
        template = Path(self.environment_template)
        env = Environment(loader=FileSystemLoader(template.parent))
        template = env.get_template(template.name)

        rendered_content = template.render({
            'course_abbrev': self.course.abbreviation,
            'year': self.course.course_year,
            'assignment_id': assignment_id  # Use assignment_id
        })

        output_file = output_dir / assignment_id / "environment.yml"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(rendered_content)
        print(f"Rendered environment file to {output_file}")

    def convert_py_to_ipynb(self, assignment_id, output_dir):
        """Convert Python scripts to Jupyter notebooks with additional processing."""
        for item in self.notebook:
            source = self.assignment_folder / item['source']
            dest = output_dir / assignment_id / item['output']
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Read and convert to notebook
            notebook = jupytext.read(source)
            # Add additional cells if specified
            additional_cells = []
            for cell in item['additional_cells']:
                if cell['cell_type'] == 'markdown':
                    additional_cells.append(new_markdown_cell(cell['content']))
                elif cell['cell_type'] == 'code':
                    additional_cells.append(new_code_cell(cell['content']))
            # Add additional cell at the beginning of the notebook
            notebook.cells = additional_cells + notebook.cells
            # Disable syncing
            notebook.metadata['jupytext'] = {'formats': 'ipynb'}
            
            # Write notebook to destination
            jupytext.write(notebook, dest)
            print(f"Converted {source} to {dest}")

    def copy_assignment_files(self, assignment_id, output_dir):
        """
        Copy assignment files for a specific assignment.

        Args:
            assignment_id (str): The destination directory for the specific assignment.
            output_dir (str): The base output directory.

        Raises:
            KeyError: If 'folder_path' or 'direct_copy' keys are missing in the assignment config.
            FileNotFoundError: If a source file does not exist.
            OSError: If a copy operation fails due to permissions or other issues.
        """
        if not self.assignment_folder:
            raise KeyError("Missing 'assignment_folder' in assignment configuration.")

        # Ensure the destination directory exists
        destination_dir = output_dir / assignment_id
        destination_dir.mkdir(parents=True, exist_ok=True)

        for item in self.data:
            src = self.assignment_folder / item
            dest = destination_dir / item

            # Check if the source file exists
            if not src.exists():
                print(f"Source file does not exist: {src}")
                continue

            # Copy the file
            try:
                shutil.copy2(src, dest)
                print(f"Copied {src} to {dest}")
            except OSError as e:
                print(f"Failed to copy {src} to {dest}: {e}")

        for item in self.figures:
            src = self.assignment_folder / item
            dest = destination_dir / item

            # Check if the source file exists
            if not src.exists():
                print(f"Source file does not exist: {src}")
                continue

            # Copy the file
            try:
                shutil.copy2(src, dest)
                print(f"Copied {src} to {dest}")
            except OSError as e:
                print(f"Failed to copy {src} to {dest}: {e}")

    def generate_exercise_tarball(self, assignment_id, output_dir):
        """
        Generate a tarball for a programming exercise.

        Args:
            assignment_id (str): A unique identifier for the exercise (used as the directory name and tarball name).
            output_dir (str): The base output directory.

        Returns:
            str: Path to the generated tarball.

        Raises:
            FileNotFoundError: If the directory named by assignment_id does not exist.
            OSError: If there is an error during the tarball creation.
        """
        # Base directory is assumed to be named as assignment_id
        base_directory = output_dir / assignment_id
        if not base_directory.exists():
            raise FileNotFoundError(f"Directory does not exist: {base_directory}")
        if not base_directory.is_dir():
            raise ValueError(f"Path is not a valid directory: {base_directory}")

        # Tarball name and path in the current working directory
        tarball_name = f"{assignment_id}.tar.gz"
        tarball_path = Path.cwd() / tarball_name
        try:
            with tarfile.open(tarball_path, "w:gz") as tar:
                tar.add(base_directory, arcname=assignment_id)
            print(f"Tarball created at: {tarball_path}")
        except OSError as e:
            raise OSError(f"Failed to create tarball: {e}")

        return tarball_path

    @staticmethod
    def from_dict(config_data, course):
        """Creates a CodingAssignment instance from a dictionary.

        Args:
            config_data (dict): A dictionary containing the assignment configuration.
            course (Course): The Course object to which the assignment belongs.

        Returns:
            CodingAssignment: A CodingAssignment object.

        Raises:
            FileNotFoundError: If a specified folder or file does not exist.
        """
        assignment_folder = Path(config_data['folder'])
        if not assignment_folder.exists():
            raise FileNotFoundError(f"Folder not found: {assignment_folder}")

        environment_template = validate_paths(assignment_folder,
                                              config_data['environment_template'],
                                              'Environment template file')[0]
        data_files = validate_paths(assignment_folder, config_data.get('data', []), 'Data file')
        figure_files = validate_paths(assignment_folder, config_data.get('figures', []), 'Figure file')
        notebook_config = config_data.get('notebook')
        if not notebook_config:
            raise ValueError("Missing 'notebook' section in configuration.")
        notebook_config['source'] = validate_paths(assignment_folder,
                                                   notebook_config['source'],
                                                   'Notebook source file')[0]
        assignment_data = {
            'assignment_id': config_data['assignment_id'],
            'course': course,
            'title': config_data['title'],
            'description': config_data['description'],
            'due_date': datetime.strptime(config_data['due_date'], '%Y-%m-%d'),
            'environment_template': environment_template,
            'notebook': notebook_config,
            'data': data_files,
            'figures': figure_files,
            'assignment_folder': assignment_folder
        }
        return CodingAssignment(**assignment_data)

class ChallengeAssignment(Assignment):
    def __init__(self, assignment_id, course, title, description, due_date, evaluation_metric, max_score=100):
        super().__init__(assignment_id, course, title, description, due_date, max_score)
        self.evaluation_metric = evaluation_metric
        self.leaderboard = []

    def update_leaderboard(self):
        self.leaderboard.sort(key=lambda submission: submission.score, reverse=True)
        for i, submission in enumerate(self.leaderboard):
            submission.rank = i + 1

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

class Submission:
    def __init__(self, assignment, student, submission_date, score=0.0):
        self.assignment = assignment
        self.student = student
        self.submission_date = submission_date
        self.score = score
        self.report_file = None  # Initialize to None
        
    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

    def __str__(self):
        return f"Submission by {self.student} on {self.assignment}"

    def formal_name(self):
        """Returns the formal name of the submission."""
        return f"{self.assignment.common_name()}-{self.student.student_id}-{self.student.name}"

    def add_report(self, submission_dir, report_file):
        """
        Adds a report file to the submission if it exists and is a PDF.

        Args:
            submission_dir (str): The base directory for submissions.
            report_file (str): The path to the PDF file relative to submission_dir.
        """
        pdf_path = Path(submission_dir) / report_file
        if pdf_path.exists() and pdf_path.suffix.lower() == '.pdf':
            self.report_file = str(report_file)
            logging.info(f"Use directly: {report_file}")
        else:
            logging.warning(f"Invalid report file specified: {pdf_path}. Ignoring.")

class ReportSubmission(Submission):
    def __init__(self, assignment, student, submission_date, score=0.0):
        super().__init__(assignment, student, submission_date, score)

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

class CodingSubmission(Submission):
    def __init__(self, assignment, student, submission_date, score=0.0):
        super().__init__(assignment, student, submission_date, score)

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

    def generate_report(self, compressed_file, base_dir):
        """
        Generates or converts the submission to a PDF.

        Args:
            base_dir (str): The base directory where submissions are stored.

        Returns:
            Path: The path to the generated PDF file, or None if an error occurred.
        """
        if self.report_file and Path(base_dir / self.report_file).exists():
            return self.report_file

        zip_filepath = Path(base_dir) / compressed_file
        if not zip_filepath.exists():
            logging.error(f"File not found: {zip_filepath}")
            return None

        common_name = self.assignment.common_name()
        formal_name = self.formal_name()

        try:
            # Create a temporary directory
            with tempfile.TemporaryDirectory(prefix=f"{common_name}-") as temp_dir:
                temp_dir = Path(temp_dir)
                logging.debug(f"Created temporary directory: {temp_dir}")

                with ZipFile(zip_filepath, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)

                ipynb_files = list(temp_dir.rglob("*.ipynb"))
                logging.debug(f"Found IPYNB {len(ipynb_files):2d} files: {ipynb_files}")

                if ipynb_files:
                    ipynb_file = ipynb_files[0]
                    logging.debug(f"Found IPYNB file for coding assignment: {ipynb_file}")
                    # Initialize NotebookConverter
                    converter = NotebookConverter()
                    # TODO: Get submission date from email metadata instead of zip file modification time
                    submission_date = datetime.fromtimestamp(zip_filepath.stat().st_mtime)
                    metadata = {
                        'title': str(self.assignment),
                        'authors': [{"name": f"{self.student}"}],
                        'date': submission_date.strftime("%Y-%m-%d %H:%M")
                    }
                    tex_file = converter.convert_notebook(ipynb_file,
                                                          self.assignment.assignment_folder,
                                                          self.assignment.figures,
                                                          metadata)
                    if tex_file is None:
                        logging.error(f"Failed to convert {ipynb_file} to tex")
                        return None
                    # Compile to PDF using PDFCompiler
                    pdf_compiler = PDFCompiler()
                    pdf_file = pdf_compiler.compile(tex_file, tex_file.parent)
                    if pdf_file:
                        dest_file = zip_filepath.parent / f"{formal_name}.pdf"
                        shutil.move(pdf_file, dest_file)
                        self.report_file = dest_file.relative_to(base_dir)
                        logging.debug(f"Generated PDF: {self.report_file}")
                        return self.report_file
                    else:                        
                        logging.error(f"Failed to compile PDF for {ipynb_file}")
                        return None
                else:
                    logging.warning(f"No IPYNB file found in {zip_filepath}")
                    return None

        except Exception as e:
            logging.error(f"Error processing {zip_filepath}: {str(e)}")

class ChallengeSubmission(Submission):
    def __init__(self, assignment, student, submission_date, model_file, results_file, score=0.0):
        super().__init__(assignment, student, submission_date, score)
        self.model_file = model_file
        self.results_file = results_file
        self.rank = None

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

def collect_submissions(args):
    """Handles the 'collect' subcommand."""
    config_file = args.config
    logging.info(f"Collecting submissions...")
    course = Course.from_config(config_file)
    logging.info(f"Course created: {course}")
    submission_dir = Path(args.submission_dir)
    for assignment in course.assignments:
        logging.info(f"Collecting submissions for {assignment}")
        assignment.collect_submissions(submission_dir)
        logging.info("Collection process finished.")
        assignment.merge_submissions(submission_dir)
        logging.info("Merging process finished.")

def main():
    """Parses command-line arguments and dispatches to appropriate subcommands."""
    parser = argparse.ArgumentParser(description="Manage assignments and submissions.")
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("-c", "--config", default="config.yml", help="Config file path")
    subparsers = parser.add_subparsers(title="subcommands", dest="subcommand", required=True)
    collect_parser = subparsers.add_parser("collect", parents=[parent_parser], help="Collect submissions")
    collect_parser.add_argument("submission_dir", help="Submission directory")
    collect_parser.set_defaults(func=collect_submissions)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    setup_logging('xdufacool.log')
    logging.info("Starting xdufacool ...")
    main()
