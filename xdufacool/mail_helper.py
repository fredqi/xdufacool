from __future__ import print_function

import datetime
import email
import imaplib
import smtplib
from email.header import decode_header
from email.parser import HeaderParser
from email.utils import parseaddr


class MailHelper:
    """A helper class for retrieve and sending emails."""

    _fields = ["SUBJECT", "FROM", "DATE", "TO", "MESSAGE-ID", "IN-REPLY-TO"]

    def __init__(self, imapserver, smtpserver=None):
        self.imapclient = imaplib.IMAP4_SSL(imapserver)
        self.smtpclient = None
        if isinstance(smtpserver, str):
            self.smtpclient = smtplib.SMTP_SSL(smtpserver)

    def login(self, emailuser, password):
        self.imapclient.login(emailuser, password)
        if self.smtpclient is not None:
            self.smtpclient.login(emailuser, password)

    def quit(self):
        self.imapclient.close()
        self.imapclient.logout()
        if self.smtpclient is not None:
            self.smtpclient.quit()

    def search(self, folder, condition):
        self.imapclient.select(folder)

        typ, data = self.imapclient.uid('search', None, condition)
        if 'OK' != typ:
            print(typ, data)

        items = data[0].split()
        logtxt = u'%d mails to be processed.' % len(items)
        print(logtxt)
        return items

    def fetch_header(self, email_uid):
        """Retrieve the header of an email specified by return id."""
        fetch_fields = "(RFC822.SIZE BODY.PEEK[HEADER.FIELDS (%s)])"
        status, data = self.imapclient.uid('fetch', email_uid,
                                           fetch_fields % " ".join(self._fields))
        if status != 'OK':
            print('Error retrieving headers.')
            return -1

        header = {}
        parser = HeaderParser()
        msg = parser.parsestr(data[0][1], True)
        for key, val in msg.items():
            if key in ['From', 'To']:
                # email addresses include two parts, (realname, email_addr)
                name, email_addr = parseaddr(val)
                header[key.lower()] = email_addr
                header[key.lower() + "name"] = MailHelper.iconv_header(name)
            else:
                header[key.lower()] = MailHelper.iconv_header(val)

        header['size'] = long(data[0][0].split()[2])

        return header

    def fetch_email(self, email_uid):
        """Parsing a given email to get title, body, and attachments."""

        cnt = 1
        body, attachments = '', list()
        typ, msg_data = self.imapclient.uid('fetch', email_uid, '(RFC822)')
        for respart in msg_data:
            if not isinstance(respart, tuple):
                continue

            msg = email.message_from_string(respart[1])
            # An email with attachments must be multipart.
            if msg.get_content_maintype() != 'multipart':
                continue

            for part in msg.walk():
                # Attachments provided  as a URL inside the email body
                # is and will not be supported.
                c_type = part.get_content_maintype()
                if c_type == 'multipart':
                    continue

                # An attachment part must have this section in its header
                c_disp = part.get('Content-Disposition')

                # Processing the body text.
                # On Linux, the text is converted to UTF-8.
                if c_type == 'text' and c_disp is None:
                    text = part.get_payload(decode=True)
                    encfmt = part.get_param('charset')
                    if 'UTF-8' != encfmt:
                        text = unicode(text, encfmt).encode('utf-8')
                    body += '\n' + text

                if c_disp is None:
                    continue

                # Download the content of the mail
                data = part.get_payload(decode=True)
                if not data:
                    continue

                # The file name is NOT provided, create one.
                # Is this really required?
                fn = part.get_filename()
                if not fn:
                    fn = 'part-%03d' % cnt
                    cnt += 1
                if fn.find('=?') == 0:
                    fn = MailHelper.iconv_header(fn)
                # print "filename:", fn
                attachments.append((fn, data))

        return body, attachments

    def send_email(self, from_addr, to_addr, msg):
        """Send a email."""
        if self.smtpclient is not None:
            # print from_addr, to_addr
            self.smtpclient.sendmail(from_addr,
                                     to_addr,
                                     msg.as_string())

    @staticmethod
    def iconv_header(header):
        """Convert the header content to UTF-8."""

        # On Windows, decode_header is also required,
        # because all header items are encoded in base64.
        text, enc = decode_header(header)[0]
        if not enc:
            return text.decode('utf-8')

        # Some email senders wrongly encode GB18030
        # character as GB2312, a pity.
        if 'GB2312' == enc.upper():
            enc = 'GB18030'
        if enc and 'UTF-8' != enc.upper():
            text = unicode(text, enc).encode('utf-8')

        return text.decode('utf-8')

    @staticmethod
    def get_datetime(date_str):
        """Get a datetime object by parsing the string in an email header."""
        dt_tuple = email.utils.parsedate_tz(date_str)
        ts_local = email.utils.mktime_tz(dt_tuple)
        tm_diff = datetime.timedelta(seconds=dt_tuple[-1])
        dt_utc = datetime.datetime.fromtimestamp(ts_local) - tm_diff
        return dt_utc

    @staticmethod
    def format_header(header, fields=None):
        """Format the header information."""
        lines = list()
        if fields is None:
            fields = header.keys()
        for item in fields:
            if item in header:
                value = header[item.lower()]
                s = u'{0:>12}: {1}'.format(item.decode('utf-8'), value)
                lines.append(s)
        return lines