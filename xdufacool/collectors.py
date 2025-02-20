import logging
import hashlib
import random
from pathlib import Path
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from abc import ABC, abstractmethod
from tqdm import tqdm

from .homework_manager import parse_subject
from .mail_helper import MailHelper
from .models import (
    Student, 
    Submission, 
    CodingSubmission, 
    ReportSubmission, 
    ChallengeSubmission,
    CodingAssignment,
    ReportAssignment, 
    ChallengeAssignment
)

class SubmissionCollector(ABC):
    """Abstract base class for submission collectors."""
    
    def __init__(self, assignment):
        self.assignment = assignment
        
    @abstractmethod
    def collect_submissions(self):
        """Collect submissions and return a dictionary of student_id: Submission."""
        pass

class LocalSubmissionCollector(SubmissionCollector):
    """Collects submissions from local filesystem."""
    
    def __init__(self, assignment, base_dir):
        super().__init__(assignment)
        self.base_dir = Path(base_dir)
        if not self.base_dir.exists():
            raise ValueError(f"Directory not found: {self.base_dir}")
        
    def collect_submissions(self):
        submission_dir = self.base_dir / self.assignment.common_name()
        logging.info(f"Collecting submissions from {submission_dir} ...")
        
        if not submission_dir.exists():
            logging.error(f"Error: Directory {submission_dir} does not exist.")
            return None
            
        file_paths = list(submission_dir.rglob(f"{self.assignment.common_name()}*"))
        file_paths.sort(key=lambda x: (x.suffix.lower() != '.pdf', x))
        
        for file_path in file_paths:
            relative_path = file_path.relative_to(submission_dir)
            if not file_path.is_file():
                continue
                
            student_id, student_name = file_path.stem.split('-')[-2:]
            if student_id not in self.assignment.submissions:
                student = Student(student_id, student_name)
                submission_date = datetime.fromtimestamp(file_path.stat().st_mtime)
                submission = self._create_submission(student, submission_date)
                self.assignment.add_submission(submission)
            
            submission = self.assignment.submissions[student_id]
            self._process_submission_file(submission, file_path, relative_path, submission_dir)
    
    def _create_submission(self, student, submission_date):
        """Create appropriate submission instance based on assignment type."""
        if isinstance(self.assignment, CodingAssignment):
            return CodingSubmission(self.assignment, student, submission_date)
        elif isinstance(self.assignment, ReportAssignment):
            return ReportSubmission(self.assignment, student, submission_date)
        elif isinstance(self.assignment, ChallengeAssignment):
            return ChallengeSubmission(self.assignment, student, submission_date)
        else:
            logging.error(f"Unknown assignment type: {type(self.assignment)}")
            return None

    def _process_submission_file(self, submission, file_path, relative_path, submission_dir):
        """Process a submission file based on its extension."""
        file_ext = file_path.suffix.lower()
        
        if file_ext in self.assignment.accepted_extensions['compressed']:
            submission.generate_report(relative_path, submission_dir)
        elif file_ext in self.assignment.accepted_extensions['document']:
            submission.add_report(submission_dir, relative_path)
        elif file_ext in self.assignment.alternative_extensions['document']:
            logging.warning(f"To convert: {relative_path}")
        elif file_ext in self.assignment.alternative_extensions['compressed']:
            logging.warning(f"To decompress manually: {relative_path}")
        else:
            logging.warning(f"Ignore: {relative_path}")

class EmailSubmissionCollector(SubmissionCollector):
    """Collects submissions from email."""
    
    def __init__(self, assignment, config):
        """Initialize collector with assignment and config dictionary."""
        super().__init__(assignment)
        self.config = config
        self.local_dir = Path(config.get('local_dir', '.')) / self.assignment.common_name()
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.email_histories = {}  # student_id -> EmailSubmissionHistory
        
        # Get teacher info from first teacher in course
        teacher = list(assignment.course.teachers.values())[0]
        self.teacher_name = teacher.name
        
        self.teacher_email = config.get('email', '')
        self.email_template = config.get('email_template', '')
        self.mail_label = config.get('mail_label', '"[Gmail]/All Mail"')
        self.batch_mode = config.get('batch', False)

        self.mail_helper = None

        self.testing_addr = None
        if config.get('testing', False):
            self.testing_addr = config.get('testing_addr', 'fred.qi@gmail.com')
            EmailSubmissionHistory.testing_addr = self.testing_addr
        
    def connect(self, connect_smtp=False):
        """Establish connection to mail server."""
        if self.mail_helper:
            return
            
        # Setup proxy if configured
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
                               self.config.get('email_password', ''),
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
        
        # Process all headers to build submission histories
        for email_uid in tqdm(email_uids, desc="Processing email headers"):
            self._process_email_header(email_uid)
    
        student_ids = list(self.email_histories.keys())
        if self.testing_addr and len(student_ids) > 5:
            student_ids = random.sample(student_ids, 5)
            logging.info(f"* Testing mode: Processing only {len(student_ids)} submissions")
        
        # Download attachments only from latest submissions
        for student_id in tqdm(student_ids, desc="* Saving attachments"):
            history = self.email_histories[student_id]
            if history.latest_email_uid:
                self._save_attachments(history.latest_email_uid, student_id, history)
        self.disconnect()
        return self.assignment.submissions
    
    def _process_email_header(self, email_uid):
        """Process email header to build submission history."""
        header = self.mail_helper.fetch_header(email_uid)
        logging.debug(f"  - Processing {header['subject']} ({email_uid})")
        student_id, student_name = parse_subject(header['subject'])
        
        if not student_id:
            logging.warning(f'  ! Invalid subject format: {header["subject"]} ({email_uid})')
            return
            
        # Create or get submission and history
        if student_id not in self.assignment.submissions:
            student = Student(student_id, student_name)
            submission_date = self.mail_helper.get_datetime(header['date'])
            submission = self._create_submission(student, submission_date)
            self.assignment.add_submission(submission)
            self.email_histories[student_id] = EmailSubmissionHistory(submission)
            
        history = self.email_histories[student_id]
        prev_uid = history.update_from_email(email_uid, header, self.teacher_email)
        
        # Mark previous email as seen if this is newer
        if prev_uid:
            self.mail_helper.flag(prev_uid, ['Seen', 'Answered'])
            
    def _build_search_conditions(self):
        """Build email search conditions based on configuration."""
        conditions = []
        
        # Add subject search condition
        if self.assignment.common_name():
            conditions.append(f'SUBJECT "{self.assignment.common_name()}"')
            
        # Add date condition if course has start date
        if hasattr(self.assignment.course, 'start_date'):
            # Convert datetime to IMAP date format (DD-MMM-YYYY)
            imap_date = self.assignment.course.start_date.strftime("%d-%b-%Y")
            conditions.append(f'SINCE "{imap_date}"')
            
        # In non-batch mode, only check unseen emails
        if not self.batch_mode:
            conditions.append('UNSEEN')
            
        search_condition = '(' + ' '.join(conditions) + ')'
        logging.debug(f"Search condition: {search_condition}")
        return search_condition
    
    def _create_submission(self, student, submission_date):
        """Create appropriate submission instance."""
        if isinstance(self.assignment, CodingAssignment):
            return CodingSubmission(self.assignment, student, submission_date)
        elif isinstance(self.assignment, ReportAssignment):
            return ReportSubmission(self.assignment, student, submission_date)
        elif isinstance(self.assignment, ChallengeAssignment):
            return ChallengeSubmission(self.assignment, student, submission_date)
        else:
            logging.error(f"Unknown assignment type: {type(self.assignment)}")
            return None
            
    def _save_attachments(self, email_uid, student_id, history):
        """Save email attachments with checksums."""
        body, attachments = self.mail_helper.fetch_email(email_uid)
        
        for filename, data in attachments:
            # Calculate checksum and track it
            sha256 = history.add_attachment(filename, data)
            file_path = self.local_dir / student_id / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            logging.info(f"  + Saving {filename} for {student_id} ({email_uid})")
            with open(file_path, 'wb') as f:
                f.write(data)
                
    def send_confirmations(self):
        """Send confirmation emails for unconfirmed submissions."""
        student_ids = list(self.email_histories.keys())
        
        if self.testing_addr and len(student_ids) > 5:
            student_ids = random.sample(student_ids, 5)
            logging.info(f"* Testing mode: Sending confirmations for {len(student_ids)} submissions")
            
        self.connect(connect_smtp=True)
        for student_id in tqdm(student_ids, desc="Sending confirmations"):
            history = self.email_histories[student_id]
            if not history.is_confirmed() or self.testing_addr:
                logging.debug(f"  - Creating confirmation for {student_id}")
                to_addr, msg = history.create_confirmation_email(
                    self.teacher_name, 
                    self.teacher_email,
                    self.email_template
                )
                
                if msg:
                    logging.debug(f"  - Sending confirmation to {to_addr}")
                    self.mail_helper.send_email(self.teacher_email, to_addr, msg)
                    self.mail_helper.flag(history.latest_email_uid, ['Seen'])
        self.disconnect()

class EmailSubmissionHistory:
    """Tracks email submission history and handles confirmation emails."""
    
    # File extension sets
    EXTS_DOCS = {'.pdf', '.doc', '.docx'}
    EXTS_SOURCES = {'.py', '.ipynb', '.m', '.mat'}
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
                
    def create_confirmation_email(self, teacher_name, teacher_email, template):
        """Create confirmation email for latest submission."""
        if not self.latest_header:
            return None, None
            
        data = {
            'name': self.submission.student.name,
            'fromname': self.latest_header.get('from', ''),
            'message-id': self.latest_header['message-id'],
            'checksum': '\n'.join(f'{sha} {fn}' 
                                 for sha, fn in self.file_checksums.items())
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

        
        # Check submitted file types
        exts = {Path(fn).suffix.lower() for fn in self.file_checksums.values()}
        has_doc = bool(exts & self.EXTS_DOCS)
        has_source = bool(exts & self.EXTS_SOURCES)
        
        # Add comments about missing files
        data['comment'] = '\n'
        if not has_doc:
            data['comment'] += "\n！ 缺少作业附件。\n"
        # if not has_source and self.submission.assignment.requires_source:
        #     data['comment'] += "\n！ 缺少源代码文件。\n"
            
        if hasattr(self.submission, 'score'):
            data['accuracy'] = f"您此次提交的结果正确率为{self.submission.score*100:5.2f}%。"
            
        body = template.format(**data)
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        return to_addr, msg