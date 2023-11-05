import re
import datetime
import socks
import socket
import email
import imaplib
import smtplib
from email.header import decode_header
from email.parser import HeaderParser
from email.utils import parseaddr


class MailHelper:
    """A helper class for retrieve and sending emails."""

    _fields = ["SUBJECT", "FROM", "DATE", "TO", "MESSAGE-ID", "IN-REPLY-TO"]

    def __init__(self, imapserver, smtpserver=None, proxy=None):
        self._flags = set(["Seen", "Answered", "Flagged"])
        # mail size is following RFC822.SIZE
        self.re_size = re.compile(r'RFC822.SIZE (\d+)', re.IGNORECASE)
        if proxy:
            proxy_ip, proxy_port = proxy
            socks.setdefaultproxy(socks.SOCKS5, proxy_ip, proxy_port)
            socket.socket = socks.socksocket

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
        # print(self.imapclient.list())

        typ, data = self.imapclient.uid('search', None, condition)
        if 'OK' != typ:
            print(typ, data)

        # print(len(data), type(data), type(data[0]))
        items = [str(dt, 'utf-8') for dt in data[0].split()]
        # logtxt = u'%d mails to be processed.' % len(items)
        # print(logtxt)
        return items

    def fetch_header(self, email_uid):
        """Retrieve the header of an email specified by return id."""
        fetch_fields = "(RFC822.SIZE BODY.PEEK[HEADER.FIELDS (%s)])"
        # print(fetch_fields, self._fields, email_uid)
        status, data = self.imapclient.uid('fetch', email_uid,
                                           fetch_fields % " ".join(self._fields))
        if status != 'OK':
            print('Error retrieving headers.')
            return -1

        header = {}
        parser = HeaderParser()
        msg = parser.parsestr(str(data[0][1], 'utf-8'), True)
        for key, val in msg.items():
            if key in ['From', 'To']:
                # email addresses include two parts, (realname, email_addr)
                name, email_addr = parseaddr(val)
                header[key.lower()] = email_addr
                header[key.lower() + "name"] = MailHelper.iconv_header(name)
            else:
                header[key.lower()] = MailHelper.iconv_header(val)
        
        size_matcher = self.re_size.search(str(data[0][0], 'utf-8'))
        if size_matcher:
            size = int(size_matcher.group(1))
            header['size'] = f"{size/1024:6.3g} KB" if size < 1e6 else f"{size/1024/1024:6.3g} MB"
        # for key, val in header.items():
        #     print(key, type(val), val)

        return header

    def fetch_email(self, email_uid):
        """Parsing a given email to get title, body, and attachments."""

        cnt = 1
        body, attachments = '', list()
        typ, msg_data = self.imapclient.uid('fetch', email_uid, '(RFC822)')
        for respart in msg_data:
            if not isinstance(respart, tuple):
                continue
            # print(respart)
            # respart_content = str(respart[1], 'utf-8')
            msg = email.message_from_bytes(respart[1])
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
                    # if 'UTF-8' != encfmt:
                    # text = unicode(text, encfmt).encode('utf-8')
                    if encfmt.upper() in ['GB2312', 'GBK']:
                        encfmt = 'GB18030'
                    text = text.decode(encfmt)
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
                # print "filename: mail_helper.py
                attachments.append((fn, data))

        return body, attachments

    def mark_as_read(self, email_uid):
        """Mark an email as read."""
        self.imapclient.uid("STORE", email_uid, "+FLAGS", "(\\Seen)")

    def flag(self, email_uid, flags):
        """Mark an email as read."""
        flags = list(set(flags) & self._flags)
        if flags:
            flag_str = " ".join([f"\\{flag}" for flag in flags])
            self.imapclient.uid("STORE", email_uid, "+FLAGS", f"({flag_str})")

    def unflag(self, email_uid, flags):
        """Mark an email as read."""
        flags = list(set(flags) & self._flags)
        if flags:
            flag_str = " ".join([f"\\{flag}" for flag in flags])
            self.imapclient.uid("STORE", email_uid, "-FLAGS", f"({flag_str})")

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
            return text # .decode('utf-8')

        # Some email senders wrongly encode GB18030
        # character as GB2312, a pity.
        if 'GB2312' == enc.upper():
            enc = 'GB18030'
        if enc:
            # text = unicode(text, enc).encode('utf-8')
            text = text.decode(enc.upper())
        return text # .decode('utf-8')

    @staticmethod
    def get_datetime(date_str):
        """Get a datetime object by parsing the string in an email header."""
        dt_parsed = email.utils.parsedate_to_datetime(date_str)
        return dt_parsed

    @staticmethod
    def format_header(header, fields=None):
        """Format the header information."""
        lines = list()
        if fields is None:
            fields = header.keys()
        for item in fields:
            if item in header:
                value = header[item.lower()]
                s = u'{0:>12}: {1}'.format(item, value)
                lines.append(s)
        return lines
