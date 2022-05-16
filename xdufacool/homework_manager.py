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
# Last-Updated: 2022-05-16 10:43:00(+0800) [by Fred Qi]
#     Update #: 2386
# ----------------------------------------------------------------------
import re
import sys
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

from xdufacool.utils import setup_logging
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
        exts = ['.pdf', '.doc', '.docx', '.odt', '.pages',
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

    def __init__(self, batch=False, **kwargs):
        """Initialize homework with a given dict."""
        for key, value in kwargs.items():
            setattr(self, key, value)

        
        if not hasattr(self, 'descriptor'):
            desc = f'{self.subject}-{self.homework_id}'
            self.descriptor = desc
        if not os.path.exists(self.descriptor):
            os.mkdir(self.descriptor)

        if not hasattr(self, 'conditions'):
            mconds = []
            if hasattr(self, 'descriptor'):
                mconds.append(f'SUBJECT "{self.descriptor}"')
            elif hasattr(self, 'subject'):
                mconds.append(f'SUBJECT "{self.subject}"')
            if hasattr(self, 'date_after'):
                mconds.append(f'SINCE {self.date_after}')
            if not batch:
                mconds.append(f'TO {Homework.email_teacher} Unanswered')
            self.conditions = ' '.join(mconds)


class Submission():
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
        self.homeworks = {}
        self.submissions  = dict()
        self.verbose    = True
        self.mail_label = '"[Gmail]/All Mail"'
        
        config = ConfigParser(interpolation=ExtendedInterpolation())
        config.read(configfile)

        cfg_general, cfg_email = config['general'], config['email']
        Homework.init_static(config['teacher']['name'],
                             cfg_email['address'], cfg_email['template'])
        for hw_key in cfg_general['homeworks'].split(','):
            hw_key = hw_key.strip()
            cfg_homework = config[f"homework_{hw_key}"]
            self.homeworks[hw_key] = Homework(**cfg_homework)
        # Setup the mail_helper
        self.testing = cfg_general.getboolean('testing')
        logging.debug(f"  testing mode = {self.testing}")
        proxy = None
        if 'proxy_ip' in cfg_general:
            proxy = cfg_general['proxy_ip'], cfg_general.getint('proxy_port')
        imap_server, smtp_server = cfg_email['imap_server'], cfg_email['smtp_server']
        if self.testing:
            self.mail_helper = MailHelper(imap_server, proxy=proxy)
        else:
            self.mail_helper = MailHelper(imap_server, smtp_server,
                                          proxy=proxy)
        self.mail_helper.login(Homework.email_teacher, cfg_email['password'])

    def check_headers(self, homework):
        """Fetch email headers."""
        logging.debug(f"  Search {homework.conditions}")
        email_uids = self.mail_helper.search(self.mail_label, homework.conditions)
        logging.debug(f"    {len(email_uids)} emails to be checked.")
        submissions = self.submissions.get(homework.descriptor, {})
        for euid in email_uids:
            header = self.mail_helper.fetch_header(euid)
            student_id, _ = parse_subject(header['subject'])
            if student_id is None:
                logging.warning(f'  {euid} {header["subject"]} {header["date"]}')
                continue            
            logging.debug(f'  {euid} {header["subject"]}')
            if student_id not in submissions:
                if header['from'] != Homework.email_teacher:
                    submissions[student_id] = Submission(euid, header)
            else:
                euid_prev = submissions[student_id].update(euid, header)
                if euid_prev:
                    self.mail_helper.flag(euid_prev, ['Seen', 'Answered'])
                    logging.debug(f"  Flagged {euid_prev} {student_id} as answered.")
        self.submissions[homework.descriptor] = submissions

    def send_confirmation(self, homework):
        """Send confirmation to unreplied emails."""
        submissions = self.submissions.get(homework.descriptor, {})
        logging.debug(f"    {len(submissions)} confirmations to be sent.")
        for student_id, hw in submissions.items():
            if homework.download:
                body, attachments = self.mail_helper.fetch_email(hw.latest_email_uid)
                hw.save(body, attachments, homework)
                logging.debug(f"  {hw.info['subject']} downloaded.")
            if not hw.is_confirmed():
                self.mail_helper.flag(hw.latest_email_uid, ['Unseen', 'Unanswered'])
                if not self.testing:
                    to_addr, msg = hw.create_confirmation()
                    self.mail_helper.send_email(Homework.email_teacher, to_addr, msg)
                    self.mail_helper.flag(hw.latest_email_uid, ['Seen', 'Answered'])
                    logging.debug(f"  {hw.info['subject']} emails confirmed.")

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
    except TimeoutError as error:
        logging.error(f"TimeoutError: {error.strerror} when connecting to email server.")
        sys.exit(error.errno)
    except AttributeError as error:
        logging.error(f"AttributeError: {error}.")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.error("KeyboardInterrupt: Interrupted by user from keyword.")
        sys.exit(1)
        
    try:
        for hw_key, homework in mgr.homeworks.items():
            logging.info(f'* [{homework.descriptor}] Checking email headers...')
            mgr.check_headers(homework)
            logging.info(f'* [{homework.descriptor}] Sending confirmation emails...')
            mgr.send_confirmation(homework)
    except KeyboardInterrupt as error:
        logging.error(f"{type(error)}: {error.strerror}")
    except ConnectionResetError as error:
        logging.error(f"{error}: {type(error)}")
    except Exception as error:
        logging.error(f"{type(error)}: {error}")

    logging.info('* Logout email servers...')
    mgr.quit()

# ----------------------------------------------------------------------
# END OF FILE
# ----------------------------------------------------------------------
