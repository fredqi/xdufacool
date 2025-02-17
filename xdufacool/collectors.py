from abc import ABC, abstractmethod
import logging
from pathlib import Path
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

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
from .homework_manager import parse_subject

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
    
    def __init__(self, assignment, mail_helper, local_dir, mail_label='"[Gmail]/All Mail"'):
        super().__init__(assignment)
        self.mail_helper = mail_helper
        self.mail_label = mail_label
        self.local_dir = Path(local_dir) / self.assignment.common_name()
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.submissions = {}
        
    def collect_submissions(self):
        """Collect submissions from email."""
        conditions = self._build_search_conditions()
        logging.debug(f"Search conditions: {conditions}")
        email_uids = self.mail_helper.search(self.mail_label, conditions)        
        logging.debug(f"  + Found {len(email_uids)} emails to check")
        
        for email_uid in email_uids:
            self._process_email(email_uid)
            
        return self.submissions
    
    def _build_search_conditions(self):
        """Build email search conditions."""
        conditions = []
        if self.assignment.common_name():
            conditions.append(f'SUBJECT "{self.assignment.common_name()}"')
        # conditions.append('Unseen')        
        return ' '.join(conditions)
    
    def _process_email(self, email_uid):
        """Process a single email."""
        header = self.mail_helper.fetch_header(email_uid)
        logging.debug(f"  + Processing {header['subject']} ({email_uid})")
        student_id, student_name = parse_subject(header['subject'])
        
        if not student_id:
            logging.warning(f'  ! Invalid subject format: {header["subject"]} {email_uid}')
            return
            
        if student_id not in self.submissions:
            student = Student(student_id, student_name)
            submission_date = self.mail_helper.get_datetime(header['date'])
            submission = self._create_submission(student, submission_date)
            self.submissions[student_id] = submission
            
        submission = self.submissions[student_id]
        self._save_attachments(email_uid, submission)
        
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
            
    def _save_attachments(self, email_uid, submission):
        """Save email attachments."""
        body, attachments = self.mail_helper.fetch_email(email_uid)
        for filename, data in attachments:
            file_path = self.local_dir / submission.student.student_id / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(data)