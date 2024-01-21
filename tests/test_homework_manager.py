# -*- coding: utf-8 -*-
import datetime
import os
from unittest import TestCase

from xdufacool.homework_manager import Homework
from xdufacool.homework_manager import Submission
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
        subject = "PRML-HW23E03-21009100517-谢某甲"
        student_id_ref = "21009100517"
        name_ref = "谢某甲"
        student_id, name = parse_subject(subject)
        self.assertEqual(student_id, student_id_ref, "Student ID is wrong.")
        self.assertEqual(name, name_ref, "Name is wrong.")

    def test_parse_subject_STE(self):
        subject = "MLEN-HW23R-H00392690-吴某丙"
        student_id_ref = "H00392690"
        name_ref = "吴某丙"
        student_id, name = parse_subject(subject)
        self.assertEqual(student_id, student_id_ref, "Student ID is wrong.")
        self.assertEqual(name, name_ref, "Name is wrong.")

    def test_parse_subject_pregr(self):
        subject = "IMGNAV23-23171210356X-武某丁-MOTRv2"
        student_id_ref = "23171210356X"
        name_ref = "武某丁"
        student_id, name = parse_subject(subject)
        self.assertEqual(student_id, student_id_ref, "Student ID is wrong.")
        self.assertEqual(name, name_ref, "Name is wrong.")


class TestHomework(TestCase):
    def setUp(self):
        self.header = dict(toname="fred.qi",
                           name="周某",
                           fromname="甲子",
                           subject=" [PRML] HW1602-14020150099-周某",
                           to="fred.qi@ieee.org",
                           time=datetime.datetime(2016, 11, 12, 3, 29, 23),
                           date="Sat, 12 Nov 2016 11:29:23 +0800",
                           size=1465)
        self.header["from"] = "1786715287@qq.com"
        self.header["message-id"] = "<tencent_14F8ED440FB998C26AE759BB@qq.com>"

    def test_initialize(self):
        hw = Submission(1000, self.header)
        self.assertEqual(hw.student_id, "14020150099",
                         "Homework.student_id is wrong. " + hw.student_id)

    def test_check_local(self):
        hw = Submission(1000, self.header)
        hw.check_local("tests/1402015")
        sha01 = "ccd40fb582c2043cc117ff7e738c2ca6d88a29d477c8fec32811b238c4c8c198"
        self.assertIn(sha01, hw.data)
