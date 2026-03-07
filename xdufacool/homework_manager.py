# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------
# 
# Filename: homework_manager.py
# Author: Fred Qi
# Created: 2012-06-07 15:59:37(+0800)
# 
# ----------------------------------------------------------------------
# ## CHANGE LOG
# ----------------------------------------------------------------------
# Last-Updated: 2024-01-21 23:17:04(+0800) [by Fred Qi]
#     Update #: 2706
# ----------------------------------------------------------------------
import re
import sys
import os.path
import hashlib
import imaplib
import logging
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from argparse import ArgumentParser
from configparser import ConfigParser
from configparser import ExtendedInterpolation

from xdufacool.utils import setup_logging
from xdufacool.mail_helper import MailHelper
from xdufacool.metrics import ClassificationAccuracy
from xdufacool.metrics import LeaderBoardItem, LeaderBoard
from xdufacool.models import Course


def load_and_hash(filename):
    """Load a file from disk and calculate its SHA256 hash code."""
    with open(filename, 'rb') as the_file:
        data = the_file.read()
        sha256 = hashlib.sha256(data)
        return sha256.hexdigest(), data
    return None


def parse_subject(subject):
    """
    Check the text to retrieve the student ID.
    regexp for detecting student ID
    The format: <stuid> ::= <year><school><spec><num>
                <year>  ::= [0-9]{2}
                <school>::= [0-9]{2}
                <spec>  ::= [0-9]{3}
                <num>   ::= [0-9]{4}
    <school> = 02 means a student of School of Electronic Engineering
    """
    if not hasattr(parse_subject, 're_id'):
        # parse_subject.re_id = re.compile(r'(?P<stuid>[0-9xtXT]{9,12}|X{3,5})')
        parse_subject.re_id = re.compile(r'(?P<stuid>H?[0-9]{8,11}X?)', re.IGNORECASE)
    # if not hasattr(parse_subject, 'year'):
    #     parse_subject.year = re.compile(r'(?P<year>2020)')
    student_id, name = None, None
    m = parse_subject.re_id.search(subject)
    if m is not None:
        student_id = m.group('stuid')
        name = subject[m.end('stuid') + 1:].split('-')[0]
    # my = parse_subject.year.search(subject)
    # if m is not None and my is not None:
    #     if my.end('year') < m.end('stuid'):
    #         name = subject[my.end('year') + 1 : m.start('stuid') - 1]
    return student_id, name


class Homework():
    """A class to represent the homework from a student."""
    # file types by extentions
    exts_sources = None
    exts_docs = None

    name_teacher = None
    email_teacher = None
    mail_template = None

    @staticmethod
    def init_static(name, email, template):
        """Initialize static (shared) variables across all homework submissions."""
        exts_zip = ['.zip', '.tar.gz', '.tar', '.xz', '.7z', '.rar']
        exts = ['.c', '.cpp', '.m', '.py']
        Homework.exts_sources = set(exts + exts_zip)
        exts_zip = ['.zip', '.tar.gz', '.tar', '.xz', '.7z', '.rar']
        exts = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.odt', '.pages',
                '.htm', '.html', '.md', '.tex']
        Homework.exts_docs = set(exts + exts_zip)

        Homework.name_teacher = name
        Homework.email_teacher = email

        # template of the confirmation email
        # keys to reference variables:
        # name: name of the student parsed from email title
        # fromname: name specified in the email header
        # message-id: email unique id
        # checksum: SHA256 hash codes of attachments
        # comment: to reply incorrect submissions
        Homework.mail_template = template

    def __init__(self, assignment_data, batch=False):
        """Initialize homework with data from YAML."""
        self.assignment_id = assignment_data['assignment_id']
        self.subject = assignment_data.get('subject', '')
        self.due_date = assignment_data['due_date']
        self.folder = assignment_data['folder']
        self.descriptor = f'{self.subject}-{self.assignment_id}'

        if not os.path.exists(self.descriptor):
            os.makedirs(self.descriptor)

        mconds = []
        if self.descriptor:
            mconds.append(f'SUBJECT "{self.descriptor}"')
        elif self.subject:
            mconds.append(f'SUBJECT "{self.subject}"')
        if hasattr(self, 'date_after'):
            mconds.append(f'SINCE {self.date_after}')
        if not batch:
            mconds.append('Unseen')
        self.conditions = ' '.join(mconds)

        if hasattr(self, 'gt_class'):
            self.metric = ClassificationAccuracy(self.gt_class)

        if hasattr(self, 'leaderboard'):
            self.leaderboard = LeaderBoard(self.leaderboard)


class Submission():
    def __init__(self, email_uid, header):
        """Initialize a homework instance."""

        self.latest_email_uid = None  # latest uid of the email
        self.student_id = None
        self.filenames = []
        self.info = dict()
        self.replied = set()
        self.body = None
        self.data = dict()
        self.emails = list()
        self.responses = list()
        self.accs = list()
        # Update the homework instance
        self.update(email_uid, header)

    def check_local(self, folder):
        hw_folder = os.path.join(folder, self.student_id)
        for filename in os.listdir(hw_folder):
            pathname = os.path.join(hw_folder, filename)
            if os.path.isfile(pathname):
                code, data = load_and_hash(pathname)
                self.data[code] = filename

    def update(self, email_uid, header):
        """
        To update the information of a homework to avoid:
        - Duplicated submission.
        - Downloaded and confirmed emails.
        """
        student_id, student_name = parse_subject(header['subject'])
        if self.student_id is None:
            self.student_id = student_id
        elif student_id != self.student_id:
            return
        # In case this is a confirmation email
        if header['from'] == Homework.email_teacher:
            if 'in-reply-to' in header:
                self.replied.add(header['in-reply-to'])
            self.responses.append(email_uid)
            return

        update_info = False
        if self.latest_email_uid is not None:
            # check email time
            time_prev = self.info['time']
            time_curr = MailHelper.get_datetime(header['date'])
            tm_diff = time_curr - time_prev
            # newer mail received
            if tm_diff.total_seconds() > 0:
                update_info = True
        else:
            # no mail has been processed
            update_info = True

        email_uid_prev = email_uid
        self.emails.append(email_uid)
        if update_info:
            email_uid_prev = self.latest_email_uid
            self.latest_email_uid = email_uid
            self.info = dict(name=student_name)
            for key, value in header.items():
                self.info[key] = value
            self.info['time'] = MailHelper.get_datetime(header['date'])
        return email_uid_prev

    def save(self, body, attachments, homework, overwrite=False):
        """Update homework and save attachments to disk."""
        stu_path = os.path.join(homework.descriptor, self.student_id)
        if not os.path.exists(stu_path):
            os.mkdir(stu_path)

        for fn, data in attachments:
            sha256 = hashlib.sha256(data).hexdigest()
            self.data[sha256] = fn
            filename = os.path.join(stu_path, fn)
            if overwrite or not os.path.exists(filename):
                with open(filename, 'wb') as output_file:
                    output_file.write(data)
                    self.filenames.append(filename)
                # checksum, _ = load_and_hash(filename)
                # assert checksum == sha256

    def eval_submission(self, metric, leaderboard):
        if self.filenames:
            try:
                acc = metric.accuracy(self.filenames[0])
                self.info['accuracy'] = f"您此次提交的结果正确率为{acc*100:5.2f}%。"                
                item = LeaderBoardItem({'student_id': self.student_id,
                                        'accuracy': acc,
                                        'time_submit': '',
                                        'count': 1})
                leaderboard.update(item)
                self.accs.append(acc)
            except UnicodeDecodeError as err:
                self.info['accuracy'] = f"您所提交的结果文件存在问题\n {type(err)}: {err}。"
                logging.error(f"{type(err)}: {err}")
            except ValueError as err:
                messages = ["您所提交的结果文件存在问题",
                            f"{type(err)}: {err}。",
                            "Hint: Header line is not required."]
                self.info['accuracy'] = "\n".join(messages)
                logging.error(f"{type(err)}: {err}")

            self.info['leaderboard'] = "当前榜单如下：\n" + leaderboard.display()
            

    def create_confirmation(self):
        """Create an email to reply for confirmation."""
        msg = MIMEMultipart()
        from_address = (Homework.name_teacher, Homework.email_teacher)
        msg['From'] = formataddr(from_address)
        to_addr = self.info['from']
        logging.debug(f"to_addr: {to_addr}")
        msg['To'] = formataddr((self.info['name'], to_addr))
        msg['In-Reply-To'] = self.info['message-id']
        msg['Subject'] = Header(self.info['subject'], 'utf-8')

        fields = ['name', 'fromname', 'message-id']
        data = {key: self.info[key] for key in fields}

        if 'accuracy' in self.info and 'leaderboard' in self.info:
            data['accuracy'] = self.info['accuracy']
            data['leaderboard'] = self.info['leaderboard']

        exts, checksum = set(), list()
        for sha, fn in self.data.items():
            checksum.append(sha + ' ' + fn)
            _, ext = os.path.splitext(fn)
            exts.add(ext.lower())

        data['checksum'] = '\n'.join(checksum)

        has_source = len(exts & Homework.exts_sources) > 0
        has_doc = len(exts & Homework.exts_docs) > 0
        data['comment'] = '\n'
        if not has_doc:
            data['comment'] += u"\n！ 缺少作业附件。\n"

        body = Homework.mail_template.format(**data)
        logging.debug(f"body: {body}")
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        logging.debug(f"msg: {msg}")
        return to_addr, msg

    def is_confirmed(self):
        """Check whether the confirmation email has been sent."""
        return self.info['message-id'] in self.replied

    def display(self):
        """Display the content of the homework to be processed."""
        fields = ["subject", "name", "from", "date", "message-id"]
        print("\n".join(MailHelper.format_header(self.info, fields)))


class HomeworkManager:
    """The class for processing homework submitted via mail."""

    def __init__(self, course, check_config):
        """Initialize the class from the Course object."""
        self.course = course
        self.homeworks = {}
        self.submissions = dict()
        self.verbose = True
        self.mail_label = '"[Gmail]/All Mail"'

        teacher = list(self.course.teachers.values())[0]
        Homework.init_static(teacher.name, check_config.get('email', ""),
                             check_config.get('email_template', ""))
        
        # Setup the mail_helper
        self.testing = check_config.get('testing', False)
        self.batch = check_config.get('batch', False)
        self.download = check_config.get('download', 'latest')
        options = {'testing': self.testing,
                   'batch': self.batch,
                   'download': self.download}
        logging.debug(f"  - options: {options}")

        for assignment_id, assignment_data in self.course.assignments.items():
            hw_data = {"assignment_id": assignment_id,
                       "subject": assignment_data.course.abbreviation,
                       "due_date": assignment_data.due_date,
                       "folder": check_config.get('base_dir', "")}
            self.homeworks[assignment_id] = Homework(hw_data, batch=self.batch)

        proxy = check_config.get('proxy', None)
        if proxy:
            proxy = proxy.split(':')
            proxy = proxy[0], int(proxy[1])

        imap_server = check_config.get('imap_server', "imap.gmail.com")
        smtp_server = check_config.get('smtp_server', "smtp.gmail.com")

        if self.testing:
            self.mail_helper = MailHelper(imap_server, proxy=proxy)
        else:
            self.mail_helper = MailHelper(imap_server, smtp_server, proxy=proxy)

        self.mail_helper.login(Homework.email_teacher, check_config.get('email_password', ""))
        logging.info(f"  Logged in as {Homework.email_teacher}.")

    def check_headers(self, homework):
        """Fetch email headers."""
        logging.debug(f"  Search {homework.conditions}")
        uids_email = self.mail_helper.search(self.mail_label, homework.conditions)
        logging.debug(f"    {len(uids_email)} emails to be checked.")
        submissions = self.submissions.get(homework.descriptor, {})
        uids_pending = []
        for euid in uids_email:
            header = self.mail_helper.fetch_header(euid)
            student_id, _ = parse_subject(header['subject'])
            if student_id is None:
                logging.warning(f'  {euid} {header["subject"]} {header["date"]}')
                continue            
            if Homework.email_teacher == header['from'] or student_id in submissions:
                uids_pending.append((euid, student_id, header))
                continue
            logging.debug(f'  {euid} {header["subject"]}')
            submissions[student_id] = Submission(euid, header)
        for euid, student_id, header in uids_pending:
            logging.debug(f'  {euid} {header["subject"]}')
            if student_id not in submissions:
                continue
            logging.debug(f'  - update records of {student_id}...')
            euid_prev = submissions[student_id].update(euid, header)
            if euid_prev:                
                self.mail_helper.flag(euid_prev, ['Seen', 'Answered'])
                logging.debug(f"  - flagged {euid_prev} as answered.")
        self.submissions[homework.descriptor] = submissions

    def send_confirmation(self, homework):
        """Send confirmation to unreplied emails."""
        # TODO: batch mode attachments download
        submissions = self.submissions.get(homework.descriptor, {})        
        queue_to_reply = []
        for student_id, hw in submissions.items():
            if not hw.is_confirmed():
                queue_to_reply.append((student_id, hw))
            else:
                for euid in hw.emails + hw.responses:
                    self.mail_helper.flag(euid, ['Seen'])                    
        logging.debug(f"    {len(queue_to_reply)} emails to be replied.")

        for student_id, hw in queue_to_reply:
            download_list = []
            if 'latest' == self.download:
                download_list += [hw.latest_email_uid]
            elif 'all' == self.download:
                download_list += hw.emails
            print(download_list)
            
            for euid in download_list:
                logging.debug(f"  {euid} {hw.info['subject']} ({hw.info['size'].strip()}) download started.")
                if not self.testing:
                    body, attachments = self.mail_helper.fetch_email(euid)
                    hw.save(body, attachments, homework, overwrite=True)
                    logging.debug(f"  {euid} {hw.info['subject']} download finished.")
                else:
                    logging.debug(f"  {euid} {hw.info['subject']} download to be finished.")

            if hasattr(homework, 'metric') and not self.testing:
                hw.eval_submission(homework.metric, homework.leaderboard)
                if hw.accs:
                    print(hw.student_id, max(hw.accs), len(hw.accs), len(hw.emails), sep=',')

            to_addr, msg = hw.create_confirmation()
            if not self.testing:
                self.mail_helper.send_email(Homework.email_teacher, to_addr, msg)
                self.mail_helper.flag(hw.latest_email_uid, ['Seen'])
                logging.debug(f"  {hw.latest_email_uid} {hw.info['subject']} confirmation sent.")
            else:
                logging.debug(f"  {hw.latest_email_uid} {hw.info['subject']} to be confirmed.")

    def quit(self):
        self.mail_helper.quit()

  
def parse_cmd():
    desc = "To check and download homeworks from an IMAP server."
    parser = ArgumentParser(description=desc)
    parser.add_argument('-s', '--search-subject', dest='subject',
                        required=True,
                        help='The keywords in mail subject used for search.')
    parser.add_argument('-a', '--search-since', dest='since',
                        help='Search mails received since the given date (Day-Mon-YEAR).')
    parser.add_argument('-b', '--search-before', dest='before',
                        help='Search mails received before the given date (Day-Mon-YEAR).')
    parser.add_argument('-m', '--email', dest='email', help='Email address of the teacher.')
    parser.add_argument('-n', '--name', dest='name', help='Name of the teacher.')
    parser.add_argument('-t', '--test-mode', dest='test',
                        action='store_true', default=False,
                        help='Analyze the header for the purpose of testing.')
    parser.add_argument('class_id', metavar='class_id', type=str,
                        help="ID of the class.")
    args = parser.parse_args()

    conds = []
    if args.subject is not None:
        conds.append('SUBJECT "%s"' % args.subject)
    if args.since is not None:
        conds.append('SINCE "%s"' % args.since)
    if args.before is not None:
        conds.append('BEFORE "%s"' % args.before)

    if 0 == len(conds):
        mcond = '(ALL SUBJECT "[PRML]")'
    else:
        mcond = '(%s)' % (' '.join(conds))

    if args.test:
        print(mcond)

    subjects = args.subject.split()
    Homework.init_static(args.name, args.email, subjects[-1], args.class_id)
    
    return (args.class_id, mcond, args.test)


def parse_config():
    desc = "To check and download homeworks from an IMAP server."
    parser = ArgumentParser(description=desc)
    parser.add_argument('config', metavar='config', type=str,
                        help="Config of homeworks.")
    args = parser.parse_args()
    return args.config


def check_homeworks():
    setup_logging('xdufacool.log', logging.DEBUG)

    config = parse_config()
    if not os.path.exists(config):
        logging.error(f"  {config} does not exist.")
        sys.exit(1)
        
    try:
        logging.info(f'* Loading {config}...')
        mgr = HomeworkManager(config)
        for hw_key, homework in mgr.homeworks.items():
            logging.info(f'* [{homework.descriptor}] Checking email headers...')
            mgr.check_headers(homework)
            logging.info(f'* [{homework.descriptor}] Sending confirmation emails...')
            # mgr.send_confirmation(homework)
            # if hasattr(homework, 'leaderboard'):
            # homework.leaderboard.save()
    except KeyboardInterrupt as error:
        logging.error("! KeyboardInterrupt: Interrupted by user from keyword.")
        sys.exit(1)
    except TimeoutError as error:
        logging.error(f"! TimeoutError: {error.strerror} when connecting to email server.")
        sys.exit(error.errno)
    except AttributeError as error:
        logging.error(f"! AttributeError: {error}.")
        sys.exit(1)
    except ConnectionResetError as error:
        logging.error(f"{type(error)}: {error}")
    except imaplib.IMAP4.error as err:
        msg = err.args[0].decode()
        logging.error(f"! Log in failed with: {msg}.")
        sys.exit(1)
    except Exception as error:
        logging.error(f"! {type(error)}: {error}")

    logging.info('* Logout email servers...')
    mgr.quit()

# ----------------------------------------------------------------------
# END OF FILE
# ----------------------------------------------------------------------
