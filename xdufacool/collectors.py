import logging
import hashlib
import random
import os
import re
from pathlib import Path
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from abc import ABC, abstractmethod
from tqdm import tqdm

from .utils import format_list
from .homework_manager import parse_subject
from .mail_helper import MailHelper
from .models import (
    Student, 
    CodingSubmission, 
    ReportSubmission, 
    ChallengeSubmission,
    CodingAssignment,
    ReportAssignment, 
    ChallengeAssignment
)
from .converters import EmailTemplateRenderer


class SubmissionCollector(ABC):
    """Abstract base class for submission collectors."""
    
    def __init__(self, assignment):
        self.assignment = assignment
        
    @abstractmethod
    def collect_submissions(self):
        """Collect submissions and return a dictionary of student_id: Submission."""
        pass


class SubmissionManager:
    """Shared manager for submission lifecycle and file ingestion."""

    def create_submission_for_assignment(self, assignment, student, submission_date):
        """Create a submission instance for the given assignment type."""
        if isinstance(assignment, CodingAssignment):
            return CodingSubmission(assignment, student, submission_date)
        if isinstance(assignment, ReportAssignment):
            return ReportSubmission(assignment, student, submission_date)
        if isinstance(assignment, ChallengeAssignment):
            logging.warning("! Challenge submissions need explicit file contract; skipping for now.")
            return None

        logging.error(f"Unknown assignment type: {type(assignment)}")
        return None

    def get_or_create_submission(self, assignment, student_id, student_name, submission_date):
        """Get an existing submission by student ID, or create a new one."""
        submission = assignment.submissions.get(student_id)
        if submission is not None:
            return submission

        student = Student(student_id, student_name)
        submission = self.create_submission_for_assignment(assignment, student, submission_date)
        if submission is not None:
            assignment.add_submission(submission)
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
        super().__init__(assignment)
        self.submission_dir = assignment.dirs['submissions']
        self.submission_manager = SubmissionManager()
        self.identity_resolver = SubmissionIdentityResolver()
        logging.info(f"* Collecting submissions from {self.submission_dir} ...")
        
        if not self.submission_dir.exists():
            logging.error(f"! Directory {self.submission_dir} does not exist.")
            return None
        
    def collect_submissions(self):
        """Collect submissions from local filesystem."""
        assignment_code = self.assignment.common_name()
        # assignment_code = self.assignment.assignment_id
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
                self.assignment,
                identity['student_id'],
                identity['student_name'],
                submission_date
            )
            if submission is None:
                continue

            self.submission_manager.ingest_saved_file(self.assignment, submission, file_path)

class EmailSubmissionCollector(SubmissionCollector):
    """Collects submissions from email."""
    
    def __init__(self, assignment, config):
        """Initialize collector with assignment and config dictionary."""
        super().__init__(assignment)
        self.config = config
        self.email_histories = {}  # student_id -> EmailSubmissionHistory
        
        self.teacher_name = format_list(list(assignment.course.teachers.values()),
                                        lang=assignment.course.language)
        
        self.teacher_email = config.get('email', '')
        self.email_template = config.get('email_template', '')
        self.mail_label = config.get('mail_label', '"[Gmail]/All Mail"')
        self.batch_mode = config.get('batch_mode', 'none')
        self.collection_mode = config.get('collection_mode', 'single')
        self.submission_manager = SubmissionManager()
        self.identity_resolver = SubmissionIdentityResolver()
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
            EmailSubmissionHistory.testing_addr = self.testing_addr

    @classmethod
    def get_scan_key(cls, assignment, config):
        """Return mailbox scan key used to deduplicate IMAP scans.

        Contract:
        - In single mode, each assignment gets an independent scan key
          (`assignment.assignment_id`) to preserve legacy behavior.
        - In bulk mode, all assignments sharing a teaching-year prefix map to
          one shared scan key (`<course_abbrev>-<derived_prefix>`), so CLI can
          run exactly one collector per prefix and avoid duplicate mailbox scans.
        """
        collection_mode = config.get('collection_mode', 'single')
        if collection_mode != 'bulk':
            return assignment.assignment_id

        prefix = cls._extract_search_prefix_static(assignment.assignment_id)
        return f"{assignment.course.abbreviation}-{prefix}"
        
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
        
        assignment_code = self.assignment.common_name()
        description = f"[{assignment_code}] Checking submissions"
        for email_uid in tqdm(email_uids, desc=description):
            self._process_email_header(email_uid)
    
        student_ids = list(self.email_histories.keys())
        if self.testing_addr and len(student_ids) > 5:
            student_ids = random.sample(student_ids, 5)
            logging.debug(f"* Processing only {len(student_ids)} submissions (Testing mode)")
        else:
            logging.info(f"* Processing {len(student_ids)} submissions")
        
        description = f"[{assignment_code}] Saving attachments"
        for student_id in tqdm(student_ids, desc=description):
            history = self.email_histories[student_id]
            if self.batch_mode == "all":
                for email_uid in history.email_uids:
                    self._save_attachments(email_uid, student_id, history)
            else:
                if history.latest_email_uid:
                    self._save_attachments(history.latest_email_uid, student_id, history)
                    
        self.disconnect()
        return self.assignment.submissions
    
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
            self.assignment,
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
        common_name = self.assignment.common_name()
        assignment_id = self.assignment.assignment_id
        if self.collection_mode == 'bulk':
            prefix = self._extract_search_prefix(assignment_id)
            conditions.append(f'SUBJECT "{self.assignment.course.abbreviation}-{prefix}"')
        elif len(self.assignment.course.assignments) == 1:
            conditions.append(f'SUBJECT "{assignment_id}" OR SUBJECT "{common_name}"')
        else:
            conditions.append(f'SUBJECT "{assignment_id}"')
            
        # Add date condition if course has start date
        if hasattr(self.assignment.course, 'start_date'):
            # Convert datetime to IMAP date format (DD-MMM-YYYY)
            imap_date = self.assignment.course.start_date.strftime("%d-%b-%Y")
            conditions.append(f'SINCE "{imap_date}"')
            
        # In non-batch mode, only check unseen emails
        if self.batch_mode == 'none':
            conditions.append('UNSEEN')
            
        search_condition = '(' + ' '.join(conditions) + ')'
        logging.debug(f"Search condition: {search_condition}")
        return search_condition

    def _extract_search_prefix(self, assignment_id):
        """Derive teaching-year prefix from assignment ID.

        HW26S01/HW26F01/HW26E01 -> HW26
        """
        return self._extract_search_prefix_static(assignment_id)

    @staticmethod
    def _extract_search_prefix_static(assignment_id):
        """Normalize assignment ID to bulk scan prefix.

        Expected normalization for semester/experiment sequence IDs:
        - HW26S01 -> HW26
        - HW26F01 -> HW26
        - HW26E01 -> HW26
        """
        match = re.match(r'^(?P<prefix>.+?)([SsFfEe]\d{2})$', assignment_id)
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
        if course_abbrev != self.assignment.course.abbreviation:
            return None, None

        target_assignment = self.assignment.course.assignments.get(assignment_id)
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

    def _save_attachment_to_assignment(self, assignment, identity, filename, data, submission_date, email_uid):
        """Save attachment bytes to an assignment and ingest via manager."""
        submission = self.submission_manager.get_or_create_submission(
            assignment,
            identity['student_id'],
            identity['student_name'],
            submission_date,
        )
        if submission is None:
            return

        student_dir = assignment.dirs['submissions'] / identity['student_id']
        student_dir.mkdir(parents=True, exist_ok=True)

        file_path = student_dir / filename
        logging.info(f"  + Saving {filename} for {identity['student_id']} ({email_uid})")
        with open(file_path, 'wb') as f:
            f.write(data)

        self.submission_manager.ingest_saved_file(assignment, submission, file_path)
    
    def _save_attachments(self, email_uid, student_id, history):
        """Save email attachments with checksums."""
        _, attachments = self.mail_helper.fetch_email(email_uid)
        submission_date = datetime.now()
        if history and history.latest_header:
            submission_date = MailHelper.get_datetime(history.latest_header['date'])
        
        for filename, data in attachments:
            if history:
                history.add_attachment(filename, data)

            if self.collection_mode == 'bulk':
                assignment, identity = self._resolve_assignment_by_filename(filename)
                if assignment is None or identity is None:
                    self._save_unmatched_attachment(email_uid, filename, data)
                    continue
                self._save_attachment_to_assignment(
                    assignment,
                    identity,
                    filename,
                    data,
                    submission_date,
                    email_uid,
                )
                continue

            identity = {'student_id': student_id, 'student_name': history.submission.student.name}
            self._save_attachment_to_assignment(
                self.assignment,
                identity,
                filename,
                data,
                submission_date,
                email_uid,
            )
                
    def send_confirmations(self):
        """Send confirmation emails for unconfirmed submissions."""
        if self.batch_mode != 'none':
            logging.info(f"* Confirmation emails are skipped in '{self.batch_mode}' batch mode.")
            return

        student_ids = list(self.email_histories.keys())
        
        if self.testing_addr and len(student_ids) > 5:
            student_ids = random.sample(student_ids, 5)
            logging.debug(f"* Sending confirmations for {len(student_ids)} submissions (Testing mode)")
        else:
            logging.info(f"* Sending confirmations for {len(student_ids)} submissions")
        
        assignment_code = self.assignment.common_name()
        description = f"[{assignment_code}] Sending confirmations"
        self.connect(connect_smtp=True)
        for student_id in tqdm(student_ids, desc=description):
            history = self.email_histories[student_id]
            if not history.is_confirmed() or self.testing_addr:
                logging.debug(f"  - Creating confirmation for {student_id} ({history.latest_email_uid})")
                to_addr, msg = history.create_confirmation_email(
                    self.teacher_name, 
                    self.teacher_email,
                    self.email_template
                )
                
                if msg:
                    logging.debug(f"    Sending confirmation to {to_addr}")
                    self.mail_helper.send_email(self.teacher_email, to_addr, msg)
                    self.mail_helper.flag(history.latest_email_uid, ['Seen', 'Answered'])
        self.disconnect()

class EmailSubmissionHistory:
    """Tracks email submission history and handles confirmation emails."""

    testing_addr = None
   
    def __init__(self, submission):
        self.submission = submission
        self.latest_email_uid = None
        self.email_uids = []
        self.response_uids = []
        self.replied_message_ids = set()
        self.file_checksums = {}  # sha256 -> filename
        self.latest_header = None

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
        
        if should_update:
            self.latest_email_uid = email_uid
            self.latest_header = header
            self.submission.submission_date = email_time
            
        return prev_uid if should_update else None
        
    def add_attachment(self, filename, data):
        """Add attachment with checksum."""
        sha256 = hashlib.sha256(data).hexdigest()
        self.file_checksums[sha256] = filename
        return sha256
        
    def is_confirmed(self):
        """Check if latest submission has been confirmed."""
        return (self.latest_header and 
                self.latest_header.get('message-id') in self.replied_message_ids)
                
    def create_confirmation_email(self, teacher_name, teacher_email,
                                  template_name='email_confirm.txt.j2'):
        """Create confirmation email for latest submission.
        
        Args:
            teacher_name (str): Name of the teacher sending the confirmation
            teacher_email (str): Email address of the teacher
            
        Returns:
            tuple: (email message object, recipient address) or (None, None) if no submission
        """
        
        if not self.latest_header:
            return None, None
            
        data = {
            'name': self.submission.student.name,
            'fromname': self.latest_header.get('from', ''),
            'message_id': self.latest_header['message-id'],
            'checksum': '\n'.join(f'{sha} {fn}' 
                                 for sha, fn in self.file_checksums.items()),
            'course_name': self.submission.assignment.course.topic,
            'teacher_name': teacher_name,
            'comment': '',
            'language': self.submission.assignment.course.language,
        }

        msg = MIMEMultipart()
        from_addr = (teacher_name, teacher_email)
        msg['From'] = formataddr(from_addr)
        to_addr = self.latest_header['from']
        if EmailSubmissionHistory.testing_addr:  # If testing_addr is set, use it
            logging.debug(f"    Would send to: {to_addr}")
            to_addr = EmailSubmissionHistory.testing_addr
            data['name'] = 'Testing'
        
        msg['To'] = formataddr((data['name'], to_addr))
        msg['In-Reply-To'] = self.latest_header['message-id']
        msg['Subject'] = Header(self.latest_header['subject'], 'utf-8')
       
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
            if  data['language'] == 'zh':
                data['accuracy'] = f"您此次提交的结果正确率为{score_percentage:5.2f}%。"
            else:
                data['accuracy'] = f"The accuracy of your submission is {score_percentage:5.2f}%."
        
        base_dir = self.submission.assignment.course.base_dir
        template_renderer = EmailTemplateRenderer(base_dir/'templates')
        body = template_renderer.render_template(template_name, **data)
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        return to_addr, msg
