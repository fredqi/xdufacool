import shutil
import tarfile
import logging
import tempfile
import jupytext
import pypandoc
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from nbformat.v4 import new_markdown_cell, new_code_cell
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

    def create_summary(self, summary_config):
        # working_dir = Path(summary_config.get('working_dir', '.'))
        # if not working_dir.exists():
        #     logging.error(f"Working directory not found: {working_dir}")
        #     return
        composer = SummaryComposer(self.group_id,
                                   self.course.base_dir,
                                   self.course.workspace_dir)
        composer.fill_titlepage(self, summary_config)
        if not self.summary_filepath.exists():
            logging.error(f"Summary file {self.summary_filepath} does not exist.")
            return
        # logging.debug(f"{working_dir} {summary_config.get('text', 'README.md')}")
        logging.debug(f"    Summary report: {self.summary_filepath.relative_to(self.course.base_dir)}")
        composer.create_summary(self.summary_filepath,
                                composer.summary_dir / summary_config.get('teaching_record', ""),
                                composer.summary_dir / self.score_filename,
                                composer.summary_dir / summary_config.get('text', "README.md"))

@dataclass
class Course:
    course_id: str
    abbreviation: str
    topic: str
    start_date: datetime.date
    end_date: datetime.date
    teaching_hours: int
    credits: float
    base_dir: Path
    summary: Dict[str, Dict[str, str]] = field(default_factory=dict)
    teachers: Dict[str, "Teacher"] = field(default_factory=dict)
    groups: List["StudentGroup"] = field(default_factory=list)
    assignments: Dict[str, "Assignment"] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize course metadata and directory structure after creation"""
        self.course_year = self.start_date.year
        self.semester_season = "Spring" if self.start_date.month < 7 else "Fall"
        if self.semester_season == "Spring":
            self.semester = f"{self.course_year-1}-{self.course_year}学年第二学期"
        else:
            self.semester = f"{self.course_year}-{self.course_year+1}学年第一学期"
        self.workspace_dir = self.base_dir / f"{self.abbreviation}-{self.course_year}-{self.semester_season}"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"* Initialized course workspace for {self.semester}")

    def add_assignment(self, assignment):
        self.assignments[assignment.assignment_id] = assignment

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

    def __str__(self):
        return f"{self.topic} ({self.course_id})"

    @staticmethod
    def from_dict(data, base_dir):
        """Creates a Course instance from a dictionary."""
        course_data = data['course']
        teachers = {t['teacher_id']: Teacher(**t) for t in data['teachers']}
        course = Course(
            base_dir=Path(base_dir),  # Add base directory
            course_id=course_data['course_id'],
            abbreviation=course_data['abbreviation'],
            topic=course_data['topic'],
            start_date=datetime.strptime(course_data['start_date'], '%Y-%m-%d').date(),
            end_date=datetime.strptime(course_data['end_date'], '%Y-%m-%d').date(),
            teaching_hours=course_data['teaching_hours'],
            credits=course_data['credits'],
            teachers=teachers,
        )
        course.groups = [StudentGroup(course=course, **g) for g in data['groups']]
        for group in course.groups:
            logging.debug(f"Course group: {group}")
        for assignment_data in data['assignments']:
            assignment_type = assignment_data['type']
            if assignment_type == 'coding':
                assignment = CodingAssignment.from_dict(assignment_data, course)
            elif assignment_type == 'report':
                assignment = ReportAssignment.from_dict(assignment_data, course)
            elif assignment_type == 'challenge':
                assignment = ChallengeAssignment.from_dict(assignment_data, course)
            else:
                raise ValueError(f"Unknown assignment type: {assignment_type}")
            course.add_assignment(assignment)

        return course

class Assignment:
    def __init__(self, assignment_id, course, title, alias, description, due_date, max_score=100):
        self.assignment_id = assignment_id
        self.course = course
        self.title = title
        self.alias = alias
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
        
        self.dirs = {
            'exercise': course.base_dir / 'exercise' / self.alias,
            'dist': course.workspace_dir / 'assignments',
            'submissions': course.workspace_dir / self.common_name()
        }

        for dir_key in ('dist', 'submissions'):
            dir_path = self.dirs[dir_key]
            dir_path.mkdir(parents=True, exist_ok=True)

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

    def generate_notification(self, notification_template):
        """Generates a notification for the assignment using Jinja2 directly.

        Args:
            output_dir (str): The directory to store the notification.
        """
        context = {
            'task_id': self.common_name(),
            'task_topic': self.title,
            'task_description': self.description,
            'due_date': self.due_date.strftime('%Y-%m-%d'),
            'teachers': format_list(list(self.course.teachers.values())),
        }
        template_dir = self.course.base_dir / 'templates'   
        logging.debug(f"Course context: {self.course} {template_dir}")
        env = Environment(loader=FileSystemLoader(template_dir))
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
            output_html_path = self.dirs['dist'] / f'notification-{self.common_name()}.html'
            pypandoc.convert_text(markdown_content, 'html', format='md', outputfile=str(output_html_path))
            logging.info(f'Generated HTML notification: {output_html_path}')

        except Exception as e:
            logging.error(f'Error during notification generation or conversion: {e}')

    def merge_submissions(self, output_name=None):
        """
        Merges all PDF submissions for the assignment into a single PDF file.
        Uses LaTeXConverter for template rendering and PDF generation.
        """
        pdf_files = []
        submissions_dir = self.dirs['submissions']
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
            tex_file = submissions_dir / f"{output_name}.tex"
            with open(tex_file, "w") as f:
                f.write(latex_content)

            pdf_compiler = PDFCompiler() 
            pdf_path = pdf_compiler.compile(tex_file, submissions_dir, True)

            if not pdf_path:
                logging.error(f"! Failed to merge PDFs for {self.assignment_id}")
                return None
            
        except Exception as e:
            logging.error(f"! Error processing {self.assignment_id}: {e}")
            return None

class ReportAssignment(Assignment):
    def __init__(self, assignment_id, course, title, alias, description, due_date, instructions, max_score=100):
        super().__init__(assignment_id, course, title, alias, description, due_date, max_score)
        self.instructions = instructions

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

    @staticmethod
    def from_dict(config_data, course):
        """Creates a ReportAssignment instance from a dictionary.

        Args:
            config_data (dict): A dictionary containing the assignment configuration.
            course (Course): The Course object to which the assignment belongs.

        Returns:
            ReportAssignment: A ReportAssignment object.
        """
        assignment_data = {
            'assignment_id': config_data['assignment_id'],
            'course': course,
            'title': config_data['title'],
            'alias': config_data['alias'],
            'description': config_data['description'],
            'due_date': datetime.strptime(config_data['due_date'], '%Y-%m-%d'),
            'instructions': config_data.get('instructions', ''),
            'max_score': config_data.get('max_score', 100)
        }
        return ReportAssignment(**assignment_data)

class CodingAssignment(Assignment):
    def __init__(self, assignment_id, course, title, alias, description, due_date,
                 environment_template=None, notebook=[], data=[], figures=[]):
        super().__init__(assignment_id, course, title, alias, description, due_date)
        
        assignment_folder = self.dirs['exercise']
        self.environment_template = validate_paths(assignment_folder,
                                                   environment_template,
                                                   'Environment template file')[0]
        self.data = validate_paths(assignment_folder, data, 'Data file')
        self.figures = validate_paths(assignment_folder, figures, 'Figure file')
        logging.debug(f"Notebook source files: {notebook}")
        notebook['source'] = validate_paths(assignment_folder, notebook['source'], 'Notebook source file')[0]
        self.notebook = notebook
        self.environment_template = environment_template
        self.notebook = notebook
        self.data = data
        self.figures = figures

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

    def prepare(self):
        """Prepares the assignment for distribution."""
        logging.info(f"Preparing assignment {self.assignment_id}...")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            logging.debug(f"Created temporary directory: {temp_dir}")
            self.render_environment_file(temp_dir)
            self.convert_py_to_ipynb(temp_dir)
            self.copy_assignment_files(temp_dir)
            tarball_path = self.package_assignment(temp_dir)
            logging.info(f"Assignment {self} prepared successfully: {tarball_path}")
            return tarball_path

    def render_environment_file(self, temp_dir):
        """Renders the environment file using Jinja2."""
        logging.debug(f"{self.dirs['exercise']}")
        template = self.dirs['exercise'] / self.environment_template
        env = Environment(loader=FileSystemLoader(template.parent))
        template = env.get_template(template.name)
        context = {'course_abbrev': self.course.abbreviation, 'serial_number': self.assignment_id}
        rendered_content = template.render(context)
        output_file = temp_dir / "environment.yml"
        with open(output_file, 'w') as f:
            f.write(rendered_content)
        logging.info(f"Rendered environment file to {output_file}")

    def convert_py_to_ipynb(self, temp_dir):
        """Convert Python scripts to Jupyter notebooks with additional processing."""
        source = self.dirs['exercise'] / self.notebook['source']
        dest = temp_dir / self.notebook['output']
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
            
    def copy_assignment_files(self, temp_dir):
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
        for item in self.data + self.figures:
            src = self.dirs['exercise'] / item
            dest = temp_dir / item
            if not src.exists():
                logging.warning(f"Source file does not exist: {src}")
                continue
            try:
                shutil.copy2(src, dest)
                logging.info(f"Copied {src} to {dest}")
            except OSError as e:
                logging.error(f"Failed to copy {src} to {dest}: {e}")

    def package_assignment(self, temp_dir):
        """Packages the assignment into a tarball for distribution."""
        tarball_name = f"{self.common_name()}-dist.tar.gz"
        tarball_path = self.dirs['dist'] / tarball_name
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
        notebook_config = config_data.get('notebook')
        if not notebook_config:
            raise ValueError("Missing 'notebook' section in configuration.")

        assignment_data = {
            'assignment_id': config_data['assignment_id'],
            'course': course,
            'title': config_data['title'],
            'alias': config_data['alias'],
            'description': config_data['description'],
            'due_date': datetime.strptime(config_data['due_date'], '%Y-%m-%d'),
            'environment_template': config_data.get('environment_template', 'environment.yml.j2'),
            'notebook': notebook_config,
            'data': config_data.get('data', []),
            'figures': config_data.get('figures', []),
        }
        return CodingAssignment(**assignment_data)

class ChallengeAssignment(Assignment):
    def __init__(self, assignment_id, course, title, alias, description, due_date, evaluation_metric, max_score=100):
        super().__init__(assignment_id, course, title, alias, description, due_date, max_score)
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
        self.submission_path = None
        self.report_path = None

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

    def __str__(self):
        return f"Submission by {self.student} on {self.assignment}"

    def formal_name(self):
        """Returns the formal name of the submission."""
        return f"{self.assignment.common_name()}-{self.student.student_id}-{self.student.name}"

    def add_report(self, report_file):
        """Adds a report file to the submission"""
        report_file = Path(report_file)
        if not report_file.exists():
            raise FileNotFoundError(f"Report file not found: {report_file}")
            
        if report_file.suffix.lower() == '.pdf':
            self.report_file = report_file.relative_to(self.assignment.dirs['submissions'])
            logging.info(f"Added report: {self.report_file}")
        else:
            logging.warning(f"! Invalid report file format: {report_file}")

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

    def generate_report(self, compressed_file):
        """
        Generates or converts the submission to a PDF.

        Args:
            base_dir (str): The base directory where submissions are stored.

        Returns:
            Path: The path to the generated PDF file, or None if an error occurred.
        """
        if self.report_file:
            report_filepath = self.assignment.dirs['submissions'] / self.report_file
            if report_filepath.exists():
                return report_filepath

        if not compressed_file.exists():
            logging.error(f"! File not found: {compressed_file}")
            return None

        common_name = self.assignment.common_name()
        formal_name = self.formal_name()

        try:
            # Create a temporary directory
            with tempfile.TemporaryDirectory(prefix=f"{common_name}-") as temp_dir:
                temp_dir = Path(temp_dir)
                logging.debug(f"Created temporary directory: {temp_dir}")

                with ZipFile(compressed_file, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)

                ipynb_files = list(temp_dir.rglob("*.ipynb"))
                logging.debug(f"Found IPYNB {len(ipynb_files):2d} files: {ipynb_files}")

                if ipynb_files:
                    ipynb_file = ipynb_files[0]
                    logging.debug(f"Found IPYNB file for coding assignment: {ipynb_file}")
                    converter = NotebookConverter()
                    # TODO: Get submission date from email metadata instead of zip file modification time
                    submission_date = datetime.fromtimestamp(compressed_file.stat().st_mtime)
                    metadata = {
                        'title': str(self.assignment),
                        'authors': [{"name": f"{self.student}"}],
                        'date': submission_date.strftime("%Y-%m-%d %H:%M")
                    }
                    tex_file = converter.convert_notebook(ipynb_file,
                                                          self.assignment.dirs['exercise'],
                                                          self.assignment.figures,
                                                          metadata)
                    if tex_file is None:
                        logging.error(f"! Failed to convert {ipynb_file} to tex")
                        return None
                    # Compile to PDF using PDFCompiler
                    pdf_compiler = PDFCompiler()
                    pdf_file = pdf_compiler.compile(tex_file, tex_file.parent)
                    if pdf_file:
                        dest_file = compressed_file.parent / f"{formal_name}.pdf"
                        shutil.move(pdf_file, dest_file)
                        self.add_report(dest_file)
                        logging.debug(f"Generated PDF: {self.report_file}")
                        return self.report_file
                    else:                        
                        logging.error(f"! Failed to compile PDF for {ipynb_file}")
                        return None
                else:
                    logging.warning(f"! No IPYNB file found in {compressed_file}")
                    return None

        except Exception as e:
            logging.error(f"! Error processing {compressed_file}: {str(e)}")

class ChallengeSubmission(Submission):
    def __init__(self, assignment, student, submission_date, model_file, results_file, score=0.0):
        super().__init__(assignment, student, submission_date, score)
        self.model_file = model_file
        self.results_file = results_file
        self.rank = None

    def __repr__(self):
        return f"{type(self).__name__}({vars(self)}) at {hex(id(self))}"

