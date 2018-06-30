# -*- encoding: utf-8 -*-
# collect_local.py ---
#
# Filename: collect_local.py
# Author: Fred Qi
# Created: 2017-01-03 20:35:44(+0800)
#
# Last-Updated: 2017-01-08 19:24:52(+0800) [by Fred Qi]
#     Update #: 473
#

# Commentary:
#
#
#

# Change Log:
#
#
#

from __future__ import print_function

import re
import os
import sys
import glob
import shutil
from zipfile import ZipFile
import subprocess as subproc

import csv


def temporal_func():
    classid = sys.argv[1]

    folders = glob.glob(classid + '-*')

    for fld in folders:
        if not os.path.isdir(fld):
            continue
        print(fld)
        subfolders = os.listdir(fld)
        for stu in subfolders:
            if os.path.isdir(stu):
                stu_id = stu
                print(stu_id)


def move_file():
    """Move files out of sub-directories in the current working directory."""
    # print("\n".join(os.listdir(filepath)))
    # folders = [os.path.join(filepath, fld) for fld in os.listdir(filepath)]
    # print(filepath + ":\n  " + "\n  ".join(folders))
    folders = filter(os.path.isdir, os.listdir(u"."))
    # print("Sub-folders: ", u"\n".join(folders))
    for folder in folders:
        files = [os.path.join(folder, fn) for fn in os.listdir(folder)]
        files = filter(os.path.isfile, files)
        for fn in files:
            _, filename = os.path.split(fn)
            shutil.move(fn, filename)
        assert 0 == len(os.listdir(folder))


def extract_rar(filename):
    """Filename include path."""
    cwd = os.getcwd()
    filepath, filename = os.path.split(filename)
    print(filepath, filename)
    os.chdir(filepath)
    subproc.call(["7z", "x", "-y", filename], stdout=subproc.PIPE)
    move_file()
    os.chdir(cwd)


def extract_zip(filename):
    """Filename include path."""
    code_pages = [u"ascii", u"utf-8", u"GB18030", u"GBK", u"GB2312", u"hz"]
    cwd = os.getcwdu()
    filepath, filename = os.path.split(filename)
    os.chdir(filepath)
    zip_obj = ZipFile(filename, 'r')
    names = zip_obj.namelist()
    print(filepath, filename)
    for name in names:
        if name[-1] == "/" or os.path.isdir(name):
            print("  Skipping: ", name)
            continue
        if name.find("__MACOSX") >= 0:
            print("  Skipping: ", name)
            continue
        succeed = False
        name_sys = name
        for coding in code_pages:
            try:
                name_sys = name.decode(coding)
                succeed = True
            except:
                succeed = False
            if succeed:
                break
        _, name_sys = os.path.split(name_sys)
        the_file = zip_obj.open(name, 'r')
        contents = the_file.read()
        the_file.close()
        the_file = open(name_sys, 'w')
        the_file.write(contents)
        the_file.close()
    zip_obj.close()
    # move_file()
    os.chdir(cwd)


def check_local_homeworks(folders, scores):
    """Check local homeworks."""
    re_id = re.compile(r'(?P<stuid>[0-9]{10,11})')
    for folder, sc in zip(folders, scores):
        files = glob.glob(folder + "/*/*.py")
        files += glob.glob(folder + "/*/*.ipynb")
        homeworks = dict()
        for filename in files:
            m = re_id.search(filename)
            if m is not None:
                stu_id = m.group('stuid')
                homeworks[stu_id] = [sc]
        write_dict_to_csv(folder + ".csv", homeworks)


def find_duplication(homework):
    """Find duplications in submitted homework."""
    re_id = re.compile(r'(?P<stuid>[0-9]{10,11})')
    dup_check = dict()
    with open(homework, 'r') as data:
        lines = data.readlines()
        for ln in lines:
            dt = ln.split()
            csum, right = dt[0], dt[1]
            if csum not in dup_check:
                dup_check[csum] = list()
            m = re_id.search(right)
            if m is not None:
                stu_id = m.group('stuid')
                dup_check[csum].append(stu_id)
    dup_check = filter(lambda k, v: len(v) > 1, dup_check.items())
    dup_check = [(key, sorted(val)) for key, val in dup_check]
    return dup_check


def display_dup(dup_result):
    """Display the duplication check results."""
    lines = [k + ": " + ", ".join(v) for k, v in dup_result]
    return lines


def load_csv_to_dict(filename):
    """Load a CSV file into a dict with the first column as the key."""
    row_len = list()
    result = dict()
    with open(filename, 'r') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            key = row[0].strip()
            values = [v.strip() for v in row[1:]]
            result[key] = values
            row_len.append(len(values))
    return result, max(row_len)


def write_dict_to_csv(filename, data):
    """Write a dictionary to a CSV file with the key as the first column."""
    with open(filename, 'w') as csvfile:
        writer = csv.writer(csvfile)
        keys = sorted(data.keys())
        for key in keys:
            value = data[key]
            row = [str(key)] + [str(v) for v in value]
            writer.writerow(row)


def merge_csv(csv_files):
    """Merge CSV files based on keywords."""
    results = dict()
    data_all = list()
    keys = set()
    for filename in csv_files:
        data, row_len = load_csv_to_dict(filename)
        keys |= set(data.keys())
        data_all.append((data, row_len))
    for key in keys:
        values = list()
        for value, row_len in data_all:
            fill = ["0"]*row_len
            dt = value[key] if key in value else fill
            values.extend(dt)
        results[key] = values
    return results


if __name__ == "__main__":
    # rar_files = glob.glob(u"HW1603/*/*.rar")
    # for fn in rar_files:
    #     extract_rar(fn)
    # zip_files = glob.glob(u"HW1603/*/*.zip")
    # for fn in zip_files:
    #     extract_zip(fn)
    homeworks = ["HW1601", "HW1602", "HW1603"]
    for hw in homeworks:
        ret = find_duplication(hw + ".md5")
        lines = display_dup(ret)
        print(hw, "with", len(lines), "duplications:")
        print("\n".join(lines))
    check_local_homeworks(homeworks, [30, 30, 40])
    csv_files = [u"EE5184-2016.csv",
                 u"HW1601.csv", u"HW1602.csv", u"HW1603.csv"]
    merged = merge_csv(csv_files)
    write_dict_to_csv("EE5184-2016-all.csv", merged)
#
# collect_local.py ends here
