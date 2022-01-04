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
# Last-Updated: 2022-01-04 18:22:24(+0800) [by Fred Qi]
#     Update #: 1892
# ----------------------------------------------------------------------
import codecs
import getpass
import hashlib
import os.path
import re
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from argparse import ArgumentParser
from configparser import ConfigParser
from configparser import ExtendedInterpolation

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
    def init_from_config(configfile):
        config = ConfigParser(interpolation=ExtendedInterpolation())
        config.read(configfile)
        Homework.name_teacher = config['teacher']['name']
        Homework.mail_template = config['email']['template']

    @staticmethod
    def initialize_static_variables(homework_id="HW0000",
                                    class_id="0" * 7,
                                    email_teacher="fred.qi@ieee.org",
                                    name_teacher="Fei Qi"):
        Homework.homework_id = homework_id
        Homework.class_id = class_id
        Homework.folder = homework_id
        Homework.email_teacher = email_teacher
        Homework.name_teacher = name_teacher

        Homework.mail_template = u"""亲爱的{name}({fromname})同学：

您通过邮件 {message-id} 提交的作业已经收到。

以下为您所提交的作业文件的SHA256值，用于确认所提交文件的内容一致性：
{checksum}
{comment}
此邮件为提交作业成功确认函，请保留。

祝学业进步、新年快乐！

齐飞
--------
西安电子科技大学人工智能学院
https://fredqi.me
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
        # print(student_id, student_name)
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

    # def __init__(self, class_id='1402015',
    #              name="Fred Qi",
    #              email_addr="fred.qi@ieee.org"):
    #     self.class_id = class_id  # Class ID
    #     self.homeworks = dict()
    #     self.mail_label = '"[Gmail]/All Mail"'

    #     # Create a folder for the class
    #     if not os.path.exists(self.class_id):
    #         os.mkdir(self.class_id)

    def __init__(self, configfile):
        """Initialize the class from the config file."""
        self.homeworks = dict()
        self.mail_label = '"[Gmail]/All Mail"'
        self.verbose = True
        
        config = ConfigParser(interpolation=ExtendedInterpolation())
        config.read(configfile)

        # Setup folder and search conditions for attachments
        self.download = config['homework'].getboolean('download')
        self.folder = config['homework']['folder']
        self.conditions = config['homework']['conditions']
        if not os.path.exists(self.folder):
            os.mkdir(self.folder)

        # Setup the mail_helper
        self.testing = config['email'].getboolean('testing')
        if self.testing:
            print(config['homework']['conditions'])
            self.mail_helper = MailHelper('imap.gmail.com')
        else:
            self.mail_helper = MailHelper('imap.gmail.com', 'smtp.gmail.com')
        email = config['email']['address']
        Homework.homework_id = config['homework']['homework-id']
        Homework.folder = config['homework']['folder']
        Homework.email_teacher = config['email']['address']
        Homework.name_teacher = config['teacher']['name']
        Homework.mail_template = config['email']['template']
        # print(Homework.mail_template)
        self.mail_helper.login(Homework.email_teacher, config['email']['password'])

    def check_headers(self):
        """Fetch email headers."""
        email_uids = self.mail_helper.search(self.mail_label, self.conditions)
        # if self.verbose:
        #     from tqdm import tqdm
        #     pbar = tqdm(total=len(email_uids))
        for euid in email_uids:
            # if self.verbose:
            #     pbar.set_description(euid)
            #     pbar.update()
            header = self.mail_helper.fetch_header(euid)
            student_id, _ = parse_subject(header['subject'])
            if student_id is None:
                continue
            if student_id not in self.homeworks:
                if header['from'] != Homework.email_teacher:
                    self.homeworks[student_id] = Homework(euid, header)
            else:
                email_uid_prev = self.homeworks[student_id].update(euid, header)
                if email_uid_prev is not None:
                    self.mail_helper.mark_as_read(email_uid_prev)

    def send_confirmation(self):
        """Send confirmation to unreplied emails."""
        # if self.verbose:
        #     from tqdm import tqdm
        #     pbar = tqdm(total=len(self.homeworks))
        for student_id, hw in self.homeworks.items():
            # if self.verbose:
            #     pbar.set_description(student_id)
            #     pbar.update()
            if not hw.is_confirmed():
                body, attachments = self.mail_helper.fetch_email(hw.latest_email_uid)
                hw.save(body, attachments)
                to_addr, msg = hw.create_confirmation()
                if not self.testing:
                    self.mail_helper.send_email(Homework.email_teacher, to_addr, msg)
            elif self.download:
                print(student_id)
                body, attachments = self.mail_helper.fetch_email(hw.latest_email_uid)
                hw.save(body, attachments)

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
    Homework.initialize_static_variables(subjects[-1], args.class_id,
                                         "fred.qi@ieee.org", "Fei Qi")
    
    return (args.class_id, mcond, args.test)


def check_homeworks(download=True):
    Homework.initialize_static_variables()
    # # class_id, mcond, test_mode = parse_cmd()
    # Homework.init_from_config("config.ini")
    # if not os.path.exists(class_id):
    #     os.mkdir(class_id)
    # logfn = os.path.join(class_id, 'download.log')
    # logfile = codecs.open(logfn, 'a', encoding='utf-8')

    # if test_mode:
    #     mh = MailHelper('imap.gmail.com')
    # else:
    #     mh = MailHelper('imap.gmail.com', 'smtp.gmail.com')

    # print('Please input the password of', Homework.email_teacher)
    # mh.login(Homework.email_teacher, getpass.getpass())

    # mgr = HomeworkManager(class_id)
    mgr = HomeworkManager('config.ini')
    mgr.check_headers()
    mgr.send_confirmation()
    mgr.quit()

    # email_uids = mh.search(mgr.mail_label, mcond)
    # for euid in email_uids:
    #     header = mh.fetch_header(euid)
    #     logtxt = " ".join(["Processing", header['subject'],
    #                        "from", header['from']])
    #     # print(logtxt)
    #     logfile.writelines(logtxt + '\n')
    #     student_id, _ = parse_subject(header['subject'])
    #     print(student_id, header['from'], header.get('in-reply-to', '<>'))
    #     if student_id is None:
    #         continue
    #     if student_id not in mgr.homeworks:
    #         if header['from'] != Homework.email_teacher:
    #             mgr.homeworks[student_id] = Homework(euid, header)
    #     else:
    #         email_uid_prev = mgr.homeworks[student_id].update(euid, header)
    #         if email_uid_prev is not None:
    #             mh.mark_as_read(email_uid_prev)

    # idx_reply = 0
    # cnt_total = len(mgr.homeworks)
    # for _, hw in mgr.homeworks.items():
    #     if download:
    #         idx_reply += 1
    #         # hw.display()
    #         mail_size = hw.info['size'] * 1.0 / 1024
    #         logtxt = u"  Downloading the mail [{index}/{total}][{size:5.1f}KB]..."
    #         logtxt = logtxt.format(index=idx_reply, total=cnt_total, size=mail_size)
    #         print(logtxt)
    #         logfile.writelines(logtxt + '\n')
    #         body, attachments = mh.fetch_email(hw.latest_email_uid)
    #         # print(hw.latest_email_uid, hw.info,
    #         #       hw.student_id, type(hw.student_id))
    #         hw.save(body, attachments)
    #         hw.display()
    #         if not hw.is_confirmed():
    #             to_addr, msg = hw.create_confirmation()
    #             # print(to_addr)                
    #             if not test_mode:
    #                 mh.send_email(Homework.email_teacher, to_addr, msg)

    # mh.quit()
  
    # msg = "There are {replied}/{total} emails have been replied."
    # print(msg.format(replied=idx_reply, total=cnt_total))

    # stu_ids = sorted(mgr.homeworks.keys())

    # text = [stu + ', 1\n' for stu in stu_ids]
    # textfile = open(Homework.homework_id + ".csv", 'w')
    # textfile.writelines(text)
    # textfile.close()


# ----------------------------------------------------------------------
# END OF FILE
# ----------------------------------------------------------------------
