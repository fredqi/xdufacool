# -*- coding: utf-8 -*-
import datetime
import os
from unittest import TestCase

from xdufacool.homework_manager import Homework
from xdufacool.homework_manager import HomeworkManager
from xdufacool.homework_manager import load_and_hash
from xdufacool.homework_manager import parse_subject


class TestFunctions(TestCase):
    def test_load_and_hash(self):
        fn = "tests/1402015/14020150099/homework.py"
        sha256_gt = "ccd40fb582c2043cc117ff7e738c2ca6d88a29d477c8fec32811b238c4c8c198"
        sha256, _ = load_and_hash(fn)
        msg = "File has not been correctly loaded and hashed."
        msg += "\nExpected: " + sha256_gt
        msg += "\nActual: " + sha256
        self.assertEqual(sha256, sha256_gt, msg=msg)

    def test_parse_subject(self):
        subject = "[PRML] HW1602-14020150058-周贤军"
        student_id_ref = "14020150058"
        name_ref = "周贤军"
        student_id, name = parse_subject(subject)
        self.assertEqual(student_id, student_id_ref, "Student ID is wrong.")
        self.assertEqual(name, name_ref, "Name is wrong.")

        student_id, _ = parse_subject("[PRML] HW1602-1402015005-周贤军")
        self.assertEqual(student_id, "1402015005", msg="Student ID is wrong.")


class TestHomework(TestCase):
    def setUp(self):
        self.header = dict(toname="fred.qi",
                           name="周晨",
                           fromname="戏子",
                           subject=" [PRML] HW1602-14020150099-周晨",
                           to="fred.qi@ieee.org",
                           time=datetime.datetime(2016, 11, 12, 3, 29, 23),
                           date="Sat, 12 Nov 2016 11:29:23 +0800",
                           size=1465)
        self.header["from"] = "1786715287@qq.com"
        self.header["message-id"] = "<tencent_14F8ED440FB998C26AE759BB@qq.com>"

    def test_initialize(self):
        hw = Homework(1000, self.header)
        self.assertEqual(hw.student_id, "14020150099",
                         "Homework.student_id is wrong. " + hw.student_id)

    def test_check_local(self):
        hw = Homework(1000, self.header)
        hw.check_local("tests/1402015")
        sha01 = "ccd40fb582c2043cc117ff7e738c2ca6d88a29d477c8fec32811b238c4c8c198"
        self.assertIn(sha01, hw.data)
