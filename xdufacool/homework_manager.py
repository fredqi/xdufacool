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
# Last-Updated: 2022-01-05 01:01:17(+0800) [by Fred Qi]
#     Update #: 2043
# ----------------------------------------------------------------------
import re
import os.path
import hashlib
import logging
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from argparse import ArgumentParser
from configparser import ConfigParser
from configparser import ExtendedInterpolation
from tqdm import tqdm

from xdufacool.mail_helper import MailHelper


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
        parse_subject.re_id = re.compile(r'(?P<stuid>[0-9xtXT]{9,12}|X{3,5})')
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
    homework_id = None
    class_id = None
    email_teacher = None
    name_teacher = None

    mail_template = None
    # file types by extentions
    exts_sources = None
    exts_docs = None

    @staticmethod
    def init_static(name_teacher, email_teacher,
                    homework_id="HW0000", class_id="0" * 7):
        Homework.homework_id = homework_id
        Homework.class_id = class_id
        Homework.folder = homework_id
        Homework.email_teacher = email_teacher
        Homework.name_teacher = name_teacher

        Homework.mail_template = u"""{name}({fromname})：
email {message-id}
SHA256 of attachments:
{checksum}
{comment}
<footer>
"""
        exts_zip = ['.zip', '.tar.gz', '.tar', '.xz', '.7z', '.rar']
        exts = ['.c', '.cpp', '.m', '.py']
        Homework.exts_sources = set(exts + exts_zip)
        exts_zip = ['.zip', '.tar.gz', '.tar', '.xz', '.7z', '.rar']
        exts = ['.pdf', '.doc', '.docx', '.odt', '.pages',
                '.htm', '.html', '.md', '.tex']
        Homework.exts_docs = set(exts + exts_zip)

    def __init__(self, email_uid, header):
        """Initialize a homework instance."""

        self.latest_email_uid = None  # latest uid of the email
        self.student_id = None
        self.info = dict()
        self.replied = set()
        self.body = None
        self.data = dict()
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
        if update_info:
            email_uid_prev = self.latest_email_uid
            self.latest_email_uid = email_uid
            self.info = dict(name=student_name)
            for key, value in header.items():
                self.info[key] = value
            self.info['time'] = MailHelper.get_datetime(header['date'])
        return email_uid_prev

    def save(self, body, attachments, overwrite=False):
        """Update homework and save attachments to disk."""
        stu_path = os.path.join(Homework.folder, self.student_id)
        if not os.path.exists(stu_path):
            os.mkdir(stu_path)

        for fn, data in attachments:
            sha256 = hashlib.sha256(data).hexdigest()
            self.data[sha256] = fn
            filename = os.path.join(stu_path, fn)
            if overwrite or not os.path.exists(filename):
                with open(filename, 'wb') as output_file:
                    output_file.write(data)
                # checksum, _ = load_and_hash(filename)
                # assert checksum == sha256

    def create_confirmation(self):
        """Create an email to reply for confirmation."""
        msg = MIMEMultipart()
        from_address = (Homework.name_teacher, Homework.email_teacher)
        msg['From'] = formataddr(from_address)
        to_addr = self.info['from']
        msg['To'] = formataddr((self.info['name'], to_addr))
        msg['In-Reply-To'] = self.info['message-id']
        msg['Subject'] = Header(self.info['subject'], 'utf-8')

        fields = ['name', 'fromname', 'message-id']
        data = {key: self.info[key] for key in fields}
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
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
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

    def __init__(self, configfile):
        """Initialize the class from the config file."""
        self.homeworks  = dict()
        self.verbose    = True
        self.mail_label = '"[Gmail]/All Mail"'
        
        config = ConfigParser(interpolation=ExtendedInterpolation())
        config.read(configfile)

        # Setup folder and search conditions for attachments
        self.download = config['homework'].getboolean('download')
        self.folder = config['homework']['folder']
        self.conditions = config['homework']['conditions']
        logging.debug(f"search conditions = {self.conditions}")
        if not os.path.exists(self.folder):
            os.mkdir(self.folder)

        # Setup the mail_helper
        email_sec = config['email']
        self.testing = email_sec.getboolean('testing')
        logging.debug(f"testing mode = {self.testing}")
        if self.testing:
            self.mail_helper = MailHelper(email_sec['imap_server'])
        else:
            self.mail_helper = MailHelper(email_sec['imap_server'],
                                          email_sec['smtp_server'])
        Homework.homework_id = config['homework']['homework-id']
        Homework.folder = config['homework']['folder']
        Homework.name_teacher = config['teacher']['name']
        Homework.email_teacher = email_sec['address']
        Homework.mail_template = email_sec['template']
        # print(Homework.mail_template)
        self.mail_helper.login(Homework.email_teacher, email_sec['password'])

    def check_headers(self):
        """Fetch email headers."""
        email_uids = self.mail_helper.search(self.mail_label, self.conditions)
        if self.verbose:
            pbar = tqdm(total=len(email_uids))
        logging.debug(f"{len(email_uids)} to be checked.")
        for euid in email_uids:
            header = self.mail_helper.fetch_header(euid)
            student_id, _ = parse_subject(header['subject'])
            if student_id is None:
                logging.warning(f'{euid} {header["subject"]}')
                continue            
            logging.info(f'{euid} {student_id}')
            if self.verbose:
                pbar.set_description(student_id)
                pbar.update()
            if student_id not in self.homeworks:
                if header['from'] != Homework.email_teacher:
                    self.homeworks[student_id] = Homework(euid, header)
                    # self.mail_helper.unflag(euid, ['Seen'])
            else:
                euid_prev = self.homeworks[student_id].update(euid, header)
                if euid_prev:
                    self.mail_helper.flag(euid_prev, ['Seen', 'Answered'])
                    logging.debug(f"Flagged {euid_prev} {student_id} as answered.")

    def send_confirmation(self):
        """Send confirmation to unreplied emails."""
        if self.verbose:
            pbar = tqdm(total=len(self.homeworks))
        logging.debug(f"{len(self.homeworks)} to be processed.")
        for student_id, hw in self.homeworks.items():
            if self.verbose:
                pbar.set_description(student_id)
                pbar.update()
            if not hw.is_confirmed():
                body, attachments = self.mail_helper.fetch_email(hw.latest_email_uid)
                hw.save(body, attachments)
                self.mail_helper.flag(hw.latest_email_uid, ['Seen'])
                logging.info(f"{student_id} downloaded.")
                to_addr, msg = hw.create_confirmation()
                if not self.testing:
                    self.mail_helper.send_email(Homework.email_teacher, to_addr, msg)
                    self.mail_helper.flag(hw.latest_email_uid, ['Answered'])
                    logging.info(f"{student_id} confirmed.")
            elif self.download:
                body, attachments = self.mail_helper.fetch_email(hw.latest_email_uid)
                hw.save(body, attachments)
                logging.info(f"{student_id} downloaded.")

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


def print_and_log(msg):
    logging.info(msg)
    print(msg)
    

def parse_config():
    desc = "To check and download homeworks from an IMAP server."
    parser = ArgumentParser(description=desc)
    parser.add_argument('config', metavar='config',
                        nargs='+', help="Config of homeworks.")
    args = parser.parse_args()
    return args.config


def check_homeworks():
    formatter = {'fmt': '%(asctime)s, %(levelname)-8s, %(message)s',
                 'datefmt': '%Y-%m-%d %H:%M:%S'}
    logging.basicConfig(filename='xdufacool.log',
                        format=formatter['fmt'],
                        datefmt=formatter['datefmt'],
                        level=logging.DEBUG)
    Homework.init_static("", "")

    for config in parse_config():
        if not os.path.exists(config):
            continue
        print_and_log('* Loading {config}...')
        mgr = HomeworkManager(config)

        print_and_log('* Checking email headers...')
        mgr.check_headers()
        
        print_and_log('* Sending confirmation emails...')
        mgr.send_confirmation()
        mgr.quit()

# ----------------------------------------------------------------------
# END OF FILE
# ----------------------------------------------------------------------
