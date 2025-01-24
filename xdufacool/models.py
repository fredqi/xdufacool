import yaml
import shutil
import logging
import tempfile
import tarfile
import jupytext
import pypandoc
from tqdm import tqdm
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from nbformat.v4 import new_markdown_cell, new_code_cell
from mailmerge import MailMerge
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from xdufacool.utils import validate_paths, format_list
from xdufacool.converters import NotebookConverter, PDFCompiler, LaTeXConverter
from xdufacool.form_automa import SummaryComposer

@dataclass
class Teacher:
    teacher_id: str
    name: str
    email: str = None
    department: str = None
    title: str = None

    def __str__(self):
        return f"{self.name}"

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

# 班级 (in Chinese)
@dataclass
class StudentGroup:
    """A group of students."""
    course: "Course"
    group_id: str
    admin_classes: List[str] = field(default_factory=list)    
    teacher_ids: List[str] = field(default_factory=list)
    students: Dict[str, "Student"] = field(default_factory=dict)
    score_filename: str = None
    summary_filepath: Optional[str] = None

    def __str__(self):
        class_names = format_list(self.admin_classes)
        return f"Student Group for {self.group_id} ({class_names})"
    
    def add_student(self, student):
        self.students[student.student_id] = student

    def get_student(self, student_id):
        return self.students.get(student_id)

    def remove_student(self, student_id):
        if student_id in self.students:
            self.students.pop(student_id)

    def add_admin_class(self, admin_class_name):
        self.admin_classes.append(admin_class_name)

    def create_summary(self, working_dir):
        working_dir = Path(working_dir)
        if not working_dir.exists():
            logging.error(f"Working directory {working_dir} does not exist.")
            return

        composer = SummaryComposer(self.group_id)
        composer.fill_titlepage(self, working_dir)
        if not self.summary_filepath.exists():
            logging.error(f"Summary file {self.summary_filepath} does not exist.")
            return
        composer.create_summary(self.summary_filepath,
                                working_dir / self.course.summary['teaching_record'],
                                working_dir / self.score_filename,
                                working_dir / self.course.summary['text']),

@dataclass
class Course:
    course_id: str
    abbreviation: str
    topic: str
    semester: str
    # teaching_plan: str
    course_year: int
    start_date: datetime.date
    end_date: datetime.date
    teaching_hours: int
    credits: float
    notification_template: str
    summary: Dict[str, Dict[str, str]] = field(default_factory=dict)
    # summary_filepath: str
    # score_filepath: str
    # submission_dir: str
    teachers: Dict[str, "Teacher"] = field(default_factory=dict)
    groups: List["StudentGroup"] = field(default_factory=list)
    assignments: Dict[str, "Assignment"] = field(default_factory=dict)

    def add_assignment(self, assignment):
        self.assignments[assignment.assignment_id] = assignment

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
        
        course_conf = config['course']
        course_conf['teachers'] = {item['teacher_id']: Teacher(**item) for item in config["teachers"]}
        course = Course(**course_conf)

        for item in config['groups']:
            stduent_group = StudentGroup(course=course, **item)
            course.groups.append(stduent_group)

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
        self.assignment_folder = None
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

    def generate_notification(self, output_dir):
        """Generates a notification for the assignment using Jinja2 directly.

        Args:
            output_dir (str): The directory to store the notification.
        """
        context = {
            'task_id': self.common_name(),
            'task_topic': self.title,
            'task_description': self.description,
            'due_date': self.due_date.strftime('%Y-%m-%d'),
            'teachers': format_list(self.course.teachers),
        }
        logging.debug(f"Course context: {self.course} {self.assignment_folder.parent}")
        notification_template = self.course.notification_template
        env = Environment(loader=FileSystemLoader(self.assignment_folder.parent))
        # template_file = self.assignment_folder.parent / notification_template
        # with open(template_file, 'r') as f:
        #     template_source = f.read()
        #     template = env.parse(template_source)
        #     required_keys = meta.find_undeclared_variables(template)
        #     remaining_keys = required_keys - context.keys()
        #     logging.debug(f"Remaining keys: {remaining_keys}")
        template = env.get_template(notification_template)
        markdown_content = template.render(context)
        try:
            output_html_path = output_dir / f'notification-{self.common_name()}.html'
            pypandoc.convert_text(markdown_content, 'html', format='md', outputfile=str(output_html_path))
            logging.info(f'Generated HTML notification: {output_html_path}')

        except Exception as e:
            logging.error(f'Error during notification generation or conversion: {e}')

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
        self.assignment_folder = Path(assignment_folder)

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

    def prepare(self, output_dir):
        """Prepares the coding assignment for distribution."""
        logging.info(f"Preparing assignment {self.assignment_id}...")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            logging.debug(f"Created temporary directory: {temp_dir}")
            self.render_environment_file(temp_dir)
            self.convert_py_to_ipynb(temp_dir)
            self.copy_assignment_files(temp_dir)
            tarball_path = self.package_assignment(output_dir, temp_dir)
            logging.info(f"Assignment {self} prepared successfully: {tarball_path}")
            return tarball_path

    def render_environment_file(self, output_dir):
        """Renders the environment file using Jinja2."""
        logging.debug(f"{self.assignment_folder}")
        template = self.assignment_folder / self.environment_template
        env = Environment(loader=FileSystemLoader(template.parent))
        template = env.get_template(template.name)
        context = {'course_abbrev': self.course.abbreviation, 'serial_number': self.assignment_id}
        rendered_content = template.render(context)
        output_file = output_dir / "environment.yml"
        with open(output_file, 'w') as f:
            f.write(rendered_content)
        logging.info(f"Rendered environment file to {output_file}")

    def convert_py_to_ipynb(self, output_dir):
        """Convert Python scripts to Jupyter notebooks with additional processing."""
        source = self.assignment_folder / self.notebook['source']
        dest = output_dir / self.notebook['output']
        notebook = jupytext.read(source)
        extra_cells = []
        for cell in self.notebook['extra_cells']:
            if cell['type'] == 'markdown':
                extra_cells.append(new_markdown_cell(cell['content']))
            elif cell['type'] == 'code':
                extra_cells.append(new_code_cell(cell['content']))
        notebook.cells = extra_cells + notebook.cells
        notebook.metadata['jupytext'] = {'formats': 'ipynb'}
        jupytext.write(notebook, dest)
        logging.info(f"Converted {source} to {dest}")
            

    def copy_assignment_files(self, output_dir):
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

        destination_dir = Path(output_dir)

        for item in self.data + self.figures:
            src = self.assignment_folder / item
            dest = destination_dir / item
            if not src.exists():
                logging.warning(f"Source file does not exist: {src}")
                continue
            try:
                shutil.copy2(src, dest)
                logging.info(f"Copied {src} to {dest}")
            except OSError as e:
                logging.error(f"Failed to copy {src} to {dest}: {e}")

    def package_assignment(self, output_dir, temp_dir):
        """Packages the assignment into a tarball for distribution."""
        tarball_name = f"{self.common_name()}-dist.tar.gz"
        tarball_path = Path(output_dir) / tarball_name
        with tarfile.open(tarball_path, "w:gz") as tar:
            for item in temp_dir.iterdir():
                tar.add(item, arcname=f"{self.common_name()}/{item.name}")
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

