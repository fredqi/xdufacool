# -*- coding: utf-8 -*-
from unittest import TestCase

from xdufacool.mail_helper import MailHelper
import datetime

class TestMailHelper(TestCase):
    def test_iconv_header(self):
        hd_str = "=?utf-8?b?IFtQUk1MXSBIVzE2MDItMTQwMjAxNTAwOTgt546L5ZSQ6I6J?="
        text = MailHelper.iconv_header(hd_str)
        text_ref = u" [PRML] HW1602-14020150098-王唐莉"
        self.assertEqual(text, text_ref,
                         msg="\nExpected: " + text_ref + "\n  Actual: " + text)

    def test_get_datetime(self):
        date_str = "Sat, 12 Nov 2016 11:29:23 +0800"
        dt = MailHelper.get_datetime(date_str)
        dt_ref = datetime.datetime(2016, 11, 12, 3, 29, 23,
                                   tzinfo=datetime.timezone.utc)
        self.assertEqual(dt, dt_ref)

    def test_format_header(self):
        header = dict(toname=u"fred.qi",
                      name=u"周晨",
                      fromname=u"戏子",
                      subject=u" [PRML] HW1602-14020150099-周晨",
                      to=u"fred.qi@ieee.org",
                      time=datetime.datetime(2016, 11, 12, 3, 29, 23),
                      date="Sat, 12 Nov 2016 11:29:23 +0800",
                      size=1465)
        header["from"] = "1786715287@qq.com"
        header["message-id"] = "<tencent_14F8ED440FB998C26AE759BB@qq.com>"

        fields = ["name", "subject", "time", "date", "message-id", "size"]
        text = MailHelper.format_header(header, fields)
        text_ref= u"""        name: 周晨
     subject:  [PRML] HW1602-14020150099-周晨
        time: 2016-11-12 03:29:23
        date: Sat, 12 Nov 2016 11:29:23 +0800
  message-id: <tencent_14F8ED440FB998C26AE759BB@qq.com>
        size: 1465"""
        for line, line_ref in zip(text, text_ref.split("\n")):
            msg = "Expected: " + line_ref + "\nActual: " + line
            self.assertEqual(line, line_ref, msg=msg)
