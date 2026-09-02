import logging
import hashlib
import random
import os
import re
import warnings
from pathlib import Path
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from abc import ABC, abstractmethod
from tqdm import TqdmExperimentalWarning

from xdufacool import mail_helper

warnings.filterwarnings("ignore", category=TqdmExperimentalWarning)
from tqdm.rich import tqdm

from .utils import format_list
from .homework_manager import parse_subject
from .mail_helper import MailHelper
from .models import (
    Course,
    Student,
    CodingSubmission,
    ReportSubmission,
    ChallengeSubmission,
    CodingAssignment,
    ReportAssignment, 
    ChallengeAssignment
)
from .converters import EmailTemplateRenderer

# how about refactor the initialization argument from assignment to course or assignments, and update inherited classes accordingly?
class SubmissionCollector(ABC):
    """Abstract base class for submission collectors.

    The base collector keeps both a primary assignment context and a course-wide
    assignment map so subclasses can handle single-assignment and multi-assignment
    flows with the same interface.
    """
    
    def __init__(self, course):
        self.course = course
        self.assignments = course.assignments
        self.submission_manager = SubmissionManager()
        self.identity_resolver = SubmissionIdentityResolver()
        
    @abstractmethod
    def collect_submissions(self):
        """Collect submissions and return a dictionary of student_id: Submission."""
        pass


class SubmissionManager:
    """Shared manager for submission lifecycle and file ingestion."""

    def get_or_create_submission(self, assignment, student_id, student_name, submission_date):
        """Get an existing submission by student ID, or create a new one."""
        submission = assignment.submissions.get(student_id)
        if submission is not None:
            return submission

        student = Student(student_id, student_name)
        if isinstance(assignment, CodingAssignment):
            submission = CodingSubmission(assignment, student, submission_date)
        if isinstance(assignment, ReportAssignment):
            submission = ReportSubmission(assignment, student, submission_date)
        if isinstance(assignment, ChallengeAssignment):
            logging.warning("! Challenge submissions need explicit file contract; skipping for now.")
        if submission is not None:
            assignment.add_submission(submission)
        else:
            logging.error(f"Unknown assignment type: {type(assignment)}")
        return submission

    def classify_file_extension(self, assignment, file_path):
        """Classify a saved submission file by extension policy."""
        file_ext = Path(file_path).suffix.lower()
        if file_ext in assignment.accepted_extensions['compressed']:
            return 'accepted_compressed'
        if file_ext in assignment.accepted_extensions['document']:
            return 'accepted_document'
        if file_ext in assignment.alternative_extensions['document']:
            return 'alternative_document'
        if file_ext in assignment.alternative_extensions['compressed']:
            return 'alternative_compressed'
        return 'ignored'

    def ingest_saved_file(self, assignment, submission, file_path):
        """Ingest a file already saved to disk using assignment extension rules."""
        status = self.classify_file_extension(assignment, file_path)
        file_path = Path(file_path)
        try:
            relative_path = file_path.relative_to(assignment.dirs['submissions'])
        except ValueError:
            relative_path = file_path

        if status == 'accepted_compressed':
            if hasattr(submission, 'generate_report'):
                submission.generate_report(file_path)
                return {'status': status, 'action': 'generate_report'}

            submission.add_report(file_path)
            return {'status': status, 'action': 'add_report'}

        if status == 'accepted_document':
            submission.add_report(file_path)
            return {'status': status, 'action': 'add_report'}

        if status == 'alternative_document':
            logging.warning(f"! To convert: {relative_path}")
            return {'status': status, 'action': 'manual_convert'}

        if status == 'alternative_compressed':
            logging.warning(f"! To decompress manually: {relative_path}")
            return {'status': status, 'action': 'manual_decompress'}

        logging.warning(f"! Ignore: {relative_path}")
        return {'status': 'ignored', 'action': 'ignore'}


class SubmissionIdentityResolver:
    """Resolve student identity from subject or canonical filename."""

    def from_subject(self, subject):
        """Resolve identity from email subject using legacy parser."""
        student_id, student_name = parse_subject(subject)
        if not student_id:
            return None
        return {
            'student_id': student_id,
            'student_name': student_name,
        }

    def from_filename(self, filename):
        """Resolve identity from canonical local/email filename.

        Pattern: <course>-<assignment>-<student_id>-<student_name>.<ext>
        """
        stem = Path(filename).stem
        parts = stem.split('-', 3)
        if len(parts) != 4:
            return None

        _, _, student_id, student_name = parts
        if not student_id:
            return None

        return {
            'student_id': student_id,
            'student_name': student_name,
        }

class LocalSubmissionCollector(SubmissionCollector):
    """Collects submissions from local filesystem."""
    
    def __init__(self, assignment):
        super().__init__(assignment.course)
        self.primary_assignment = assignment
        self.submission_dir = assignment.dirs['submissions']
        logging.info(f"* Collecting submissions from {self.submission_dir} ...")
        
        if not self.submission_dir.exists():
            logging.error(f"! Directory {self.submission_dir} does not exist.")
            return None
        
    def collect_submissions(self):
        """Collect submissions from local filesystem."""
        assignment_code = self.primary_assignment.common_name()
        # assignment_code = self.primary_assignment.assignment_id
        file_paths = list(self.submission_dir.rglob(f"{assignment_code}*"))
        file_paths.sort(key=lambda x: (x.suffix.lower() != '.pdf', x))
        
        for file_path in tqdm(file_paths, desc=f"[{assignment_code}] Collecting submissions"):
            # relative_path = file_path.relative_to(self.submission_dir)
            if not file_path.is_file():
                continue
            identity = self.identity_resolver.from_filename(file_path.name)
            if identity is None:
                logging.warning(f"! Ignore malformed filename: {file_path.name}")
                continue

            submission_date = datetime.fromtimestamp(file_path.stat().st_mtime)
            submission = self.submission_manager.get_or_create_submission(
                self.primary_assignment,
                identity['student_id'],
                identity['student_name'],
                submission_date
            )
            if submission is None:
                continue

            self.submission_manager.ingest_saved_file(self.primary_assignment, submission, file_path)


class EmailSubmission:
    """One email-backed submission with its header, attachments, and reply."""

    def __init__(self, email_uid, header, submission):
        self.email_uid = email_uid
        self.header = header
        self.submission = submission
        self.body = ''
        self.attachments = []
        self.file_checksums = {}
        self.saved_files = []
        self.attachments_downloaded = False
        self.confirmation_sent = False

    @property
    def message_id(self):
        """Return the Message-ID used by confirmation replies."""
        return self.header.get('message-id')

    @property
    def submission_date(self):
        """Return the email submission timestamp."""
        return MailHelper.get_datetime(self.header['date'])

    def is_confirmed_by(self, replied_message_ids):
        """Return whether this email has already received a confirmation."""
        return self.message_id in replied_message_ids

    def download_attachments(self, mail_helper, force=False):
        """Fetch attachments once and compute checksums."""
        if self.attachments_downloaded and not force:
            return self.attachments

        self.body, self.attachments = mail_helper.fetch_email(self.email_uid)
        self.file_checksums = {}
        for filename, data in self.attachments:
            sha256 = hashlib.sha256(data).hexdigest()
            self.file_checksums[sha256] = filename

        self.attachments_downloaded = True
        return self.attachments

    def save_attachments(self, target_dir, overwrite=True):
        """Save already-downloaded attachments into one directory."""
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        self.saved_files = []
        for filename, data in self.attachments:
            saved_file = target_dir / filename
            if overwrite or not saved_file.exists():
                with open(saved_file, 'wb') as f:
                    f.write(data)
            self.saved_files.append(saved_file)

        return self.saved_files

    def create_confirmation_email(self, teacher_name, teacher_email,
                                  template_name='email_confirm.txt.j2',
                                  testing_addr=None):
        """Create a confirmation email for this exact submission email."""
        data = {
            'name': self.submission.student.name,
            # 'fromname': self.header.get('from', ''),
            'message_id': self.header['message-id'],
            'checksum': '\n'.join(f'{sha} {fn}'
                                 for sha, fn in self.file_checksums.items()),
            'course_name': self.submission.assignment.course.topic,
            'teacher_name': teacher_name,
            'comment': '',
            'language': self.submission.assignment.course.language,
        }

        msg = MIMEMultipart()
        msg['From'] = formataddr((teacher_name, teacher_email))
        to_addr = self.header['from']
        if testing_addr:
            logging.debug(f"    Would send to: {to_addr}")
            to_addr = testing_addr
            data['name'] = 'Testing'

        msg['To'] = formataddr((data['name'], to_addr))
        msg['In-Reply-To'] = self.header['message-id']
        msg['Subject'] = Header(self.header['subject'], 'utf-8')

        exts = {Path(fn).suffix.lower() for fn in self.file_checksums.values()}
        expected_exts = self.submission.assignment.get_extensions()
        has_doc = bool(exts & expected_exts)

        if not has_doc:
            if data['language'] == 'zh':
                data['comment'] += f"！ 缺少{expected_exts}格式的作业附件。\n提示：请勿使用\"超大附件\"功能发送作业。\n"
            else:
                data['comment'] += f"! Missing attachments with extensions: {expected_exts}.\n"

        if hasattr(self.submission, 'leaderboard'):
            score_percentage = self.submission.score * 100
            if data['language'] == 'zh':
                data['accuracy'] = f"您此次提交的结果正确率为{score_percentage:5.2f}%。"
            else:
                data['accuracy'] = f"The accuracy of your submission is {score_percentage:5.2f}%."

        base_dir = self.submission.assignment.course.base_dir
        template_renderer = EmailTemplateRenderer(base_dir/'templates')
        body = template_renderer.render_template(template_name, **data)
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        logging.debug(f"  - Confirmation created (To: {msg['To']}, Subject: {msg['Subject']})")
        return to_addr, msg

    def send_confirmation(self, mail_helper, teacher_email):
        logging.debug(f"    {mail_helper}")
        if not mail_helper:
            return None
        message = self.confirmation_message
        to_addr = self.confirmation_to_addr
        logging.debug(f"    Sending confirmation to {to_addr}/{self.confirmation_sent}")
        logging.debug(f"    Message: {message}")
        if not self.confirmation_sent and message:
            reta = mail_helper.send_email(teacher_email, to_addr, message)
            retb = mail_helper.flag(self.email_uid, ['Seen', 'Answered'])
            logging.debug(f"    email sending {reta} {retb}")
            self.confirmation_sent = True


class EmailSubmissionCollector(SubmissionCollector):
    """Collects submissions from email."""
    
    def __init__(self, assignment, config):
        """Initialize collector with assignment and config dictionary."""
        super().__init__(assignment.course)
        self.primary_assignment = assignment
        self.config = config
        self.email_histories = {}  # student_id -> EmailSubmissionHistory
        
        self.teacher_name = format_list(list(assignment.course.teachers.values()),
                                        lang=assignment.course.language)
        
        self.teacher_email = config.get('email', '')
        self.email_template = config.get('email_template', '')
        self.mail_label = config.get('mail_label', '"[Gmail]/All Mail"')
        self.batch_mode = config.get('batch_mode', False)
        self.collection_mode = config.get('collection_mode', 'single')
        self.unmatched_dir = Path(
            config.get(
                'unmatched_attachments_dir',
                assignment.dirs['submissions'] / 'unmatched'
            )
        )
        self.mail_helper = None
        self.testing_addr = None
        if config.get('testing', False):
            self.testing_addr = config.get('testing_addr', 'fred.qi@gmail.com')

    def connect(self, connect_smtp=False):
        """Establish connection to mail server."""
        if self.mail_helper:
            return

        proxy = self.config.get('proxy', None)
        if proxy:
            proxy = proxy.split(':')
            proxy = proxy[0], int(proxy[1])
            
        imap_server = self.config.get('imap_server', "imap.gmail.com")
        smtp_server = None
        if connect_smtp:
            smtp_server = self.config.get('smtp_server', "smtp.gmail.com")
        self.mail_helper = MailHelper(imap_server, smtp_server, proxy=proxy)
        self.mail_helper.login(self.config.get('email', ''),
                               os.getenv('EMAIL_PASSWORD', self.config.get('email_password', '')),
                               self.mail_label)
        logging.info(f"* Logged in as {self.config.get('email', '')}")
        
    def disconnect(self):
        """Close mail server connection."""
        if self.mail_helper:
            logging.info('* Logging out from email servers...')
            self.mail_helper.quit()
            self.mail_helper = None
            
    def collect_submissions(self):
        """Collect submissions from email."""
        self.connect()
        conditions = self._build_search_conditions()
        email_uids = self.mail_helper.search(conditions)
        logging.debug(f"* Found {len(email_uids)} emails to check")
        
        description = f"[{self._search_subject()}] Checking submissions"
        for email_uid in tqdm(email_uids, desc=description):
            self._process_email_header(email_uid)

        student_ids = list(self.email_histories.keys())
        if self.testing_addr and len(student_ids) > 5:
            student_ids = random.sample(student_ids, 5)
            logging.debug(f"* Testing mode")
        logging.info(f"* Processing {len(student_ids)} email submissions")
        self._process_submissions(student_ids)
        self.disconnect()

        if self.batch_mode:
            logging.info("* Confirmation emails are skipped in batch mode.")
            return
        
        self.connect(connect_smtp=True)
        self._send_confirmations(student_ids)
        self.disconnect()
    
    def _process_email_header(self, email_uid):
        """Process email header to build submission history."""
        header = self.mail_helper.fetch_header(email_uid)
        logging.debug(f"  - Processing {header['subject']} ({email_uid})")
        identity = self.identity_resolver.from_subject(header['subject'])
        
        if identity is None:
            logging.warning(f'  ! Invalid subject format: {header["subject"]} ({email_uid})')
            return
        student_id = identity['student_id']
        student_name = identity['student_name']

        submission_date = self.mail_helper.get_datetime(header['date'])
        submission = self.submission_manager.get_or_create_submission(
            self.primary_assignment,
            student_id,
            student_name,
            submission_date
        )
        if submission is None:
            return
            
        # Create or get submission and history
        if student_id not in self.email_histories:
            self.email_histories[student_id] = EmailSubmissionHistory(submission)
            
        history = self.email_histories[student_id]
        prev_uid = history.update_from_email(email_uid, header, self.teacher_email)
        
        # Mark previous email as seen if this is newer
        if prev_uid:
            self.mail_helper.flag(prev_uid, ['Seen'])
            
    def _build_search_conditions(self):
        """Build email search conditions based on configuration."""
        conditions = []
        
        # Add subject search condition
        subject_pattern = self._search_subject()
        conditions.append(f'SUBJECT "{subject_pattern}"')
            
        # Add date condition if course has start date
        if hasattr(self.course, 'start_date'):
            # Convert datetime to IMAP date format (DD-MMM-YYYY)
            imap_date = self.course.start_date.strftime("%d-%b-%Y")
            conditions.append(f'SINCE "{imap_date}"')
            
        # In non-batch mode, only check unseen emails
        if not self.batch_mode:
            conditions.append('UNSEEN')
            
        search_condition = '(' + ' '.join(conditions) + ')'
        logging.debug(f"Search condition: {search_condition}")
        return search_condition

    def _search_subject(self):
        """Return the subject pattern used for email search and progress labels."""
        assignment_id = self.primary_assignment.assignment_id
        if self.collection_mode == 'bulk':
            prefix = EmailSubmissionCollector._extract_search_prefix(assignment_id)
            abbrev = self.course.abbreviation
            if prefix.find(self.course.abbreviation) >= 0:
                parts = [self.course.abbreviation, prefix]
                return "-".join(parts)
            return f"{self.course.abbreviation}-{prefix}"
        return self.primary_assignment.common_name()

    @staticmethod
    def _extract_search_prefix(assignment_id):
        """Normalize assignment ID to bulk scan prefix.

        Expected normalization for semester/experiment sequence IDs:
        - HW26S01 -> HW26
        - HW26F01 -> HW26
        - HW26E01 -> HW26
        """
        match = re.match(r'^(?P<prefix>.+?)([SsFfEe]\d{1,2})$', assignment_id)
        logging.debug(f"{match}/{match.group('prefix') if match else assignment_id}")
        if match:
            return match.group('prefix')
        return assignment_id

    def _resolve_assignment_by_filename(self, filename):
        """Resolve assignment and identity by canonical attachment filename."""
        stem = Path(filename).stem
        parts = stem.split('-', 3)
        if len(parts) != 4:
            return None, None

        course_abbrev, assignment_id, _, _ = parts
        if course_abbrev != self.course.abbreviation:
            return None, None

        target_assignment = self.assignments.get(assignment_id)
        if target_assignment is None:
            return None, None

        identity = self.identity_resolver.from_filename(filename)
        return target_assignment, identity

    def _save_unmatched_attachment(self, email_uid, filename, data):
        """Save malformed/unmatched files for manual review."""
        self.unmatched_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.unmatched_dir / f"{email_uid}-{filename}"
        with open(file_path, 'wb') as f:
            f.write(data)
        logging.warning(f"  ! Saved unmatched attachment: {file_path}")
        return file_path

    def _save_attachment_to_assignment(self, assignment, identity, email_submission, filename, data):
        """Save attachment bytes to an assignment and ingest via manager."""
        submission = self.submission_manager.get_or_create_submission(
            assignment,
            identity['student_id'],
            identity['student_name'],
            email_submission.submission_date,
        )
        if submission is None:
            return None

        student_dir = assignment.dirs['submissions'] / identity['student_id']
        student_dir.mkdir(parents=True, exist_ok=True)
        file_path = student_dir / filename
        logging.info(
            f"  + Saving {filename} for {identity['student_id']} "
            f"({email_submission.email_uid})"
        )
        with open(file_path, 'wb') as f:
            f.write(data)

        self.submission_manager.ingest_saved_file(assignment, submission, file_path)
        return file_path

    def _attachment_assignment(self, student_id, email_submission, filename):
        """Resolve where one email attachment should be saved."""
        if self.collection_mode == 'bulk':
            return self._resolve_assignment_by_filename(filename)

        identity = {
            'student_id': student_id,
            'student_name': email_submission.submission.student.name,
        }
        return self.primary_assignment, identity
    
    def _save_email_submission_attachment(self, student_id, email_submission, filename, data):
        """Route and save one attachment from an EmailSubmission."""
        assignment, identity = self._attachment_assignment(student_id, email_submission, filename)
        if assignment is None or identity is None:
            return self._save_unmatched_attachment(email_submission.email_uid, filename, data)

        return self._save_attachment_to_assignment(
            assignment,
            identity,
            email_submission,
            filename,
            data,
        )

    def _download_and_save_email_submission(self, email_submission, student_id):
        """Download one email submission and save its attachments."""
        email_submission.download_attachments(self.mail_helper)
        email_submission.saved_files = []
        for filename, data in email_submission.attachments:
            saved_file = self._save_email_submission_attachment(
                student_id,
                email_submission,
                filename,
                data,
            )
            if saved_file:
                email_submission.saved_files.append(saved_file)
        return email_submission.saved_files

    def _email_submissions_to_confirm(self, history):
        """Select email submissions to confirm for the current collection mode."""
        if self.collection_mode == 'bulk':
            return history.unconfirmed_email_submissions()

        email_submission = history.latest_email_submission()
        if email_submission and (
                not email_submission.is_confirmed_by(history.replied_message_ids)
                or self.testing_addr):
            return [email_submission]

        return []

    def _process_submissions(self, student_ids):
        """Download, save, and optionally confirm selected email submissions."""
        description = f"[{self._search_subject()}] Processing submissions"
        for student_id in tqdm(student_ids, desc=description):
            history = self.email_histories[student_id]
            if self.batch_mode:
                email_submissions = history.email_submissions_in_order()
            else:
                email_submissions = self._email_submissions_to_confirm(history)

            for email_submission in email_submissions:
                logging.debug(
                    f"  - Processing submission for {student_id} "
                    f"({email_submission.email_uid})"
                )
                self._download_and_save_email_submission(email_submission, student_id)
                
    def _send_confirmations(self, student_ids):
        """Send prepared confirmation emails."""
        logging.info(f"* Sending confirmations for {len(student_ids)} students")
        description = f"[{self._search_subject()}] Sending confirmations"
        for student_id in tqdm(student_ids, desc=description):
            history = self.email_histories[student_id]
            for email_submission in self._email_submissions_to_confirm(history):
                if email_submission.confirmation_sent:
                    continue
                logging.debug(f"  - Sending confirmation for {student_id}")
                to_addr, message = email_submission.create_confirmation_email(
                    self.teacher_name,
                    self.teacher_email,
                    self.email_template,
                    testing_addr=self.testing_addr
                )
                if message:
                    self.mail_helper.send_email(self.teacher_email, to_addr, message)
                    self.mail_helper.flag(email_submission.email_uid, ['Seen', 'Answered'])
                    email_submission.confirmation_sent = True

class EmailSubmissionHistory:
    """Tracks email submission history and handles confirmation emails."""
   
    def __init__(self, submission):
        self.submission = submission
        self.latest_email_uid = None
        self.email_uids = []
        self.response_uids = []
        self.replied_message_ids = set()
        self.latest_header = None
        self.email_submissions = {}

    def update_from_email(self, email_uid, header, teacher_email):
        """Update submission history from new email."""
        # Skip if this is a confirmation email from teacher
        if header['from'] == teacher_email:
            if 'in-reply-to' in header:
                self.replied_message_ids.add(header['in-reply-to'])
            self.response_uids.append(email_uid)
            return None
            
        # Check if this is a newer submission
        email_time = MailHelper.get_datetime(header['date'])
        should_update = False
        
        if self.latest_email_uid is None:
            should_update = True
        else:
            prev_time = MailHelper.get_datetime(self.latest_header['date'])
            if email_time > prev_time:
                should_update = True
                
        prev_uid = self.latest_email_uid
        self.email_uids.append(email_uid)
        self.email_submissions[email_uid] = EmailSubmission(email_uid, header, self.submission)
        
        if should_update:
            self.latest_email_uid = email_uid
            self.latest_header = header
            self.submission.submission_date = email_time
            
        return prev_uid if should_update else None

    def email_submissions_in_order(self):
        """Return email submissions from earliest to latest."""
        return sorted(
            self.email_submissions.values(),
            key=lambda email_submission: email_submission.submission_date,
        )

    def unconfirmed_email_submissions(self):
        """Return unconfirmed email submissions from earliest to latest."""
        return [
            email_submission
            for email_submission in self.email_submissions_in_order()
            if not email_submission.is_confirmed_by(self.replied_message_ids)
        ]

    def latest_email_submission(self):
        """Return the latest email submission object."""
        if not self.latest_email_uid:
            return None
        return self.email_submissions.get(self.latest_email_uid)
        
    def is_confirmed(self):
        """Check if latest submission has been confirmed."""
        return (self.latest_header and 
                self.latest_header.get('message-id') in self.replied_message_ids)
