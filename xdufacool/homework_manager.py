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
# Last-Updated: 2018-06-30 19:17:36(+0800) [by Fred Qi]
#     Update #: 1588
# ----------------------------------------------------------------------
from __future__ import print_function

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
        parse_subject.re_id = re.compile(r'(?P<stuid>[0-9]{9,11}|X{3,5})')
    student_id, name = None, None
    m = parse_subject.re_id.search(subject)
    if m is not None:
        student_id = m.group('stuid')
        if m.end('stuid') + 1 < len(subject):
            name = subject[m.end('stuid') + 1:]
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
    def initialize_static_variables(homework_id="HW0000",
                                    class_id="0" * 7,
                                    email_teacher="fred.qi@ieee.org",
                                    name_teacher="Fei Qi"):
        Homework.homework_id = homework_id
        Homework.class_id = class_id
        Homework.email_teacher = email_teacher
        Homework.name_teacher = name_teacher

        Homework.mail_template = u"""亲爱的{name}({fromname})同学：

你通过邮件 {message-id} 提交的作业已经收到。

以下为你所提交的文件的SHA256值，用于确认所提交文件的内容一致性：
{checksum}
{comment}
此邮件为提交作业成功确认函，请保留。

齐飞
--------
西安电子科技大学电子工程学院
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
        for fn, data in attachments:
            sha256 = hashlib.sha256(data).hexdigest()
            self.data[sha256] = (fn, data)

        # print(Homework.class_id, self.student_id)
        stu_path = os.path.join(Homework.class_id, self.student_id)
        # print(stu_path)
        if not os.path.exists(stu_path):
            os.mkdir(stu_path)

        for key, value in self.data.items():
            assert isinstance(value, tuple)
            assert 2 == len(value)
            fn, data = value
            filename = os.path.join(stu_path, fn)
            if overwrite or not os.path.exists(filename):
                with open(filename, 'wb') as output_file:
                    output_file.write(data)

    def create_confirmation(self):
        """Create an email to reply for confirmation."""
        msg = MIMEMultipart()
        from_address = (Homework.name_teacher, Homework.email_teacher)
        msg['From'] = formataddr(from_address)
        # to_addr = 'fred.qi@gmail.com'  # for DEBUG
        to_addr = self.info['from']
        msg['To'] = formataddr((self.info['name'], to_addr))
        msg['In-Reply-To'] = self.info['message-id']
        msg['Subject'] = Header(self.info['subject'], 'utf-8')

        fields = ['name', 'fromname', 'message-id']
        data = {key: self.info[key] for key in fields}
        exts, checksum = set(), list()
        for sha, value in self.data.items():
            fn, _ = value
            checksum.append(sha + ' ' + fn)
            _, ext = os.path.splitext(fn)
            exts.add(ext.lower())

        data['checksum'] = '\n'.join(checksum)

        has_source = len(exts & Homework.exts_sources) > 0
        has_doc = len(exts & Homework.exts_docs) > 0
        data['comment'] = '\n'
        if not has_source:
            data['comment'] += u"\n！ 缺少程序代码文件。\n"
        if not has_doc:
            data['comment'] += u"\n！ 缺少书面报告。\n"

        body = Homework.mail_template.format(**data)
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        # print(self.info['name'], self.info['from'], self.info['subject'])
        # print(body)
        return to_addr, msg

    def is_confirmed(self):
        """Check whether the confirmation email has been sent."""
        return self.info['message-id'] in self.replied

    def display(self):
        """Display the content of the homework to be processed."""
        # fields = None
        fields = ["subject", "name", "from", "date", "message-id"]
        print("\n".join(MailHelper.format_header(self.info, fields)))


class HomeworkManager:
    """The class for processing homework submitted via mail."""

    def __init__(self, class_id='1402015',
                 name="Fred Qi",
                 email_addr="fred.qi@ieee.org"):
        self.class_id = class_id  # Class ID
        self.homeworks = dict()
        self.mail_label = 'work/teaching'

        # Create a folder for the class
        if not os.path.exists(self.class_id):
            os.mkdir(self.class_id)


def parse_cmd():
    desc = "To check and download homeworks from an IMAP server."
    parser = ArgumentParser(description=desc)
    parser.add_argument('-s', '--search-subject', dest='subject',
                        required=True,
                        help='The keywords in mail subject used for search.')
    parser.add_argument('-a', '--search-since', dest='since',
                        help='Search mails received since the given date.')
    parser.add_argument('-b', '--search-before', dest='before',
                        help='Search mails received before the given date.')
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
    class_id, mcond, test_mode = parse_cmd()
    if not os.path.exists(class_id):
        os.mkdir(class_id)
    logfn = os.path.join(class_id, 'download.log')
    logfile = codecs.open(logfn, 'a', encoding='utf-8')

    if test_mode:
        mh = MailHelper('imap.gmail.com')
    else:
        mh = MailHelper('imap.gmail.com', 'smtp.gmail.com')

    print('Please input the password of', Homework.email_teacher)
    mh.login(Homework.email_teacher, getpass.getpass())

    mgr = HomeworkManager(class_id)
    # print(mgr.mail_label, mcond)
    email_uids = mh.search(mgr.mail_label, mcond)
    for euid in email_uids:
        header = mh.fetch_header(euid)
        logtxt = " ".join(["Processing", header['subject'],
                           "from", header['from']])
        print(logtxt)
        student_id, _ = parse_subject(header['subject'])
        if student_id not in mgr.homeworks:
            if header['from'] != Homework.email_teacher:
                mgr.homeworks[student_id] = Homework(euid, header)
        else:
            email_uid_prev = mgr.homeworks[student_id].update(euid, header)
            # print(email_uid_prev, student_id)
            if email_uid_prev is not None:
                mh.mark_as_read(email_uid_prev)

    idx_reply = 0
    cnt_total = len(mgr.homeworks)
    for _, hw in mgr.homeworks.items():
        if download:
            idx_reply += 1
            # hw.display()
            mail_size = hw.info['size'] * 1.0 / 1024
            logtxt = u"  Downloading the mail [{index}/{total}][{size:5.1f}KB]..."
            logtxt = logtxt.format(index=idx_reply, total=cnt_total, size=mail_size)
            print(logtxt)
            logfile.writelines(logtxt + '\n')
            body, attachments = mh.fetch_email(hw.latest_email_uid)
            # print(hw.latest_email_uid, hw.info,
            #       hw.student_id, type(hw.student_id))
            hw.save(body, attachments)
            hw.display()
            if not (test_mode or hw.is_confirmed()):
                to_addr, msg = hw.create_confirmation()
                # print(to_addr)
                mh.send_email(Homework.email_teacher, to_addr, msg)

    mh.quit()

    msg = "There are {replied}/{total} emails have been replied."
    print(msg.format(replied=idx_reply, total=cnt_total))

    stu_ids = sorted(mgr.homeworks.keys())

    text = [stu + ', 1\n' for stu in stu_ids]
    textfile = open(Homework.homework_id + ".csv", 'w')
    textfile.writelines(text)
    textfile.close()


# ----------------------------------------------------------------------
# END OF FILE
# ----------------------------------------------------------------------
