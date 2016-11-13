#!/usr/bin/env python
# -*- coding: utf-8 -*-
## ----------------------------------------------------------------------
## START OF FILE
## ----------------------------------------------------------------------
## 
## Filename: homework_manager.py
## Author: Fred Qi
## Created: 2012-06-07 15:59:37(+0800)
## 
## ----------------------------------------------------------------------
### CHANGE LOG
## ----------------------------------------------------------------------
## Last-Updated: 2016-11-08 01:45:34(+0800) [by Fred Qi]
##     Update #: 1441
## ----------------------------------------------------------------------
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
from optparse import OptionParser

from xdufacool.mail_helper import MailHelper


def load_and_hash(filename):
    """Load a file from disk and calculate its SHA256 hash code."""
    the_file = open(filename, 'rb')
    data = the_file.read()
    sha256 = hashlib.sha256(data)
    return sha256.hexdigest(), data


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
        parse_subject.re_id = re.compile(r'(?P<stuid>[0-9]{11})')
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

        if update_info:
            self.latest_email_uid = email_uid
            self.info = dict(name=student_name)
            for key, value in header.iteritems():
                self.info[key] = value
            self.info['time'] = MailHelper.get_datetime(header['date'])

    def save(self, body, attachments, overwrite=False):
        """Update homework and save attachments to disk."""
        for fn, data in attachments:
            sha256 = hashlib.sha256(data).hexdigest()
            self.data[sha256] = (fn, data)

        stu_path = os.path.join(Homework.class_id, self.student_id)
        if not os.path.exists(stu_path):
            os.mkdir(stu_path)

        for key, value in self.data.iteritems():
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
        for sha, value in self.data.iteritems():
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
        field = "message-id"
        has_replied = False
        if field in self.info:
            has_replied = self.info[field] in self.replied
        return has_replied

    def display(self):
        """Display the content of the homework to be processed."""
        # fields = None
        fields = ["subject", "name", "from", "date", "message-id"]
        print("\n".join(MailHelper.format_header(self.info, fields)))


class HomeworkManager:
    """The class for processing homework submitted via mail."""

    def __init__(self, classid='1402015',
                 name="Fred Qi",
                 email_addr="fred.qi@ieee.org"):
        self.classid = classid  # Class ID
        self.homeworks = dict()
        self.mail_label = 'teaching'

        # Create a folder for the class
        if not os.path.exists(self.classid):
            os.mkdir(self.classid)


def parse_cmd():
    parser = OptionParser('Usage: %prog [options] classid')
    parser.add_option('-s', '--search-subject', dest='subject',
                      help='The keywords in mail subject used for search.')
    parser.add_option('-a', '--search-since', dest='since',
                      help='Search mails received since the given date.')
    parser.add_option('-b', '--search-before', dest='before',
                      help='Search mails received before the given date.')
    parser.add_option('-t', '--test-mode', dest='test',
                      action='store_true', default=False,
                      help='Analyze the header for the purpose of testing.')

    opts, args = parser.parse_args()

    if len(args) != 1:
        print('Wrong arguments')
        exit(-1)

    classid = args[0]

    conds = []
    if opts.subject:
        conds.append('SUBJECT "%s"' % opts.subject)
    if opts.since:
        conds.append('SINCE "%s"' % opts.since)
    if opts.before:
        conds.append('BEFORE "%s"' % opts.before)

    if 0 == len(conds):
        mcond = '(ALL SUBJECT "[PRML]")'
    else:
        mcond = '(%s)' % (' '.join(conds))

    if opts.test:
        print(mcond)

    return (classid, mcond, opts.test)


def check_homeworks():
    classid, mcond, test_mode = parse_cmd()
    if not os.path.exists(classid):
        os.mkdir(classid)
    logfn = os.path.join(classid, 'download.log')
    logfile = codecs.open(logfn, 'a', encoding='utf-8')

    Homework.initialize_static_variables("HW1602", classid,
                                         "fred.qi@ieee.org", "Fei Qi")
    if test_mode:
        mh = MailHelper('imap.gmail.com')
    else:
        mh = MailHelper('imap.gmail.com', 'smtp.gmail.com')

    print('Please input the password of', Homework.email_teacher)
    mh.login(Homework.email_teacher, getpass.getpass())

    mgr = HomeworkManager(classid)
    email_uids = mh.search(mgr.mail_label, mcond)
    for euid in email_uids:
        header = mh.fetch_header(euid)
        logtxt = u" ".join(["Processing", header['subject'],
                            "from", header['from']])
        print(logtxt)
        student_id, _ = parse_subject(header['subject'])
        if student_id not in mgr.homeworks:
            mgr.homeworks[student_id] = Homework(euid, header)
        else:
            mgr.homeworks[student_id].update(euid, header)

    idx_reply = 0
    cnt_total = len(mgr.homeworks)
    for _, hw in mgr.homeworks.iteritems():
        if not hw.is_confirmed():
            idx_reply += 1
            mail_size = hw.info['size'] * 1.0 / 1024
            logtxt = u"  Downloading the mail [{index}/{total}][{size:5.1f}KB]..."
            logtxt = logtxt.format(index=idx_reply, total=cnt_total, size=mail_size)
            print(logtxt)
            logfile.writelines(logtxt + '\n')
            body, attachments = mh.fetch_email(hw.latest_email_uid)
            hw.save(body, attachments)
            hw.display()
            if not test_mode:
                to_addr, msg = hw.create_confirmation()
                # print(to_addr)
                # mh.send_email(Homework.email_teacher, to_addr, msg)

    msg = "There are {replied}/{total} emails have been replied."
    print(msg.format(replied=idx_reply, total=cnt_total))

    mh.quit()

## ----------------------------------------------------------------------
### END OF FILE 
## ----------------------------------------------------------------------