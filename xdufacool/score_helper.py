# score_helper.py ---
#
# Filename: score_helper.py
# Author: Fred Qi
# Created: 2021-01-10 20:41:42(+0800)
#
# Last-Updated: 2021-03-06 22:32:26(+0800) [by Fred Qi]
#     Update #: 314
# 

# Commentary:
#
#
# 

# Change Log:
#
#
#
import os
import csv
import xlrd
import xlwt
import shutil
import click


def find_column_index(header, fields):
    """Find the corresponding column indices of given fields."""
    indices = []
    for txt in fields:
        for idx, col in enumerate(header):
            if col.find(txt) >= 0:
                indices.append(idx)
                break
    return indices


def load_xls(xlsfile):
    book = xlrd.open_workbook(xlsfile)
    sh = book.sheet_by_index(0)
    data = []
    for rx in range(sh.nrows):
        row = sh.row(rx)
        data.append([c.value for c in row])
    return data


def value_dict(data, sid_col, value_col):
    students = {}
    for row in data[1:]:
        sid, name = row[sid_col], row[value_col]
        students[sid] = name
    return students


def merge_students(source_a, source_b):
    results = dict(source_a)
    for key, val in source_b.items():
        results[key] = val
    return results


def student_form(students, sid_label, name_label):
    """Convert student dict to a table."""
    data = [[sid_label, name_label]]
    for key, value in students.items():
        data.append([key, value])
    return data


def merge_scores(scores, weights=None):
    s_keys = list(scores.keys())
    # headers = ["姓名", "学号"] + s_keys + ["加权平均分"]
    if weights is None:
        weights = {key: 1.0 for key in s_keys}
    w_sum = sum(list(weights.values()))
    
    students = []
    for key in s_keys:
        students += list(scores[key].keys())
    students = sorted(list(set(students)))
    
    data = {}
    errors = []
    for sid in students:
        avg = 0.0
        scs = {"学号": sid}
        for key in s_keys:
            try:
                sc = float(scores[key][sid])
            except ValueError as e:
                sc = 0.0
                errors.append([sid, key, scores[key][sid]])
            avg += weights[key] * sc
            scs[key] = sc
        avg /= w_sum
        scs["加权平均分"] = avg
        if avg < 60:
            errors.append([sid, avg])
        data[sid] = scs
    return data, errors


def score_dict_to_table(scores, fields):
    """Convert scores to a table."""
    form = [fields]
    for sid, values in scores.items():
        row = [values[fields[0]]]
        row += ["{v:g}".format(v=values[key]) for key in fields[1:]]
        form.append(row)
    return form


def fill_score_form(form, scores, sid_col=1):
    """Fill in the score form, whose first line is a header."""
    # Skipping the first row (header)
    for row in form[1:]:
        sid = row[sid_col]
        sc = scores[sid] if sid in scores else "0"
        # row[-1] = f"{sc:g}"
        row[-1] = sc


def write_csv(data, csvfile):
    """Save 2D list (data) to a csv file."""
    with open(csvfile, "w") as csv_stream:
        writer = csv.writer(csv_stream)
        writer.writerows(data)

        
def write_xls(form, xlspath, sheet_name="sheet"):
    """Write a form to xls file for uploading."""

    book = xlwt.Workbook()
    sheet = book.add_sheet(sheet_name)
    for r, row in enumerate(form):
        for c, value in enumerate(row):
            sheet.write(r, c, value)
    book.save(xlspath)


@click.group()
def xduscore():
    pass


@xduscore.command()
@click.argument('students', nargs=-1, type=click.Path(exists=True))
@click.option('-o', '--output', type=click.Path())
@click.option('--name-xdu', default='姓名(文本)', type=click.STRING)
@click.option('--sid-xdu', default='学号(文本)', type=click.STRING)
@click.option('--name-baidu', default='学生姓名', type=click.STRING)
@click.option('--sid-baidu', default='学生学号', type=click.STRING)
@click.option('--sheet-baidu', default='学生名单', type=click.STRING)
def merge(output, students, **kwargs):
    """Read lists of students downloaded from Xidian, merge them to create a unified list."""    
    students_all = {}
    fields = [kwargs["name_xdu"], kwargs["sid_xdu"]]
    for xlsfile in students:
        data = load_xls(xlsfile)
        name_col, sid_col = find_column_index(data[0], fields)
        stus = value_dict(data, sid_col, name_col)
        students_all = merge_students(students_all, stus)

    l_sid, l_name = kwargs["sid_baidu"], kwargs["name_baidu"]
    form = student_form(students_all, l_sid, l_name)
    # write_csv(form, output.replace(".xls", ".csv"))
    write_xls(form, output, kwargs["sheet_baidu"])


@xduscore.command()
@click.argument("scores", nargs=-1, type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path())
@click.option("-w", "--weights", multiple=True, type=click.FLOAT)
@click.option("-t", "--tasks", multiple=True, type=click.STRING)
@click.option('--name-baidu', default='姓名', type=click.STRING)
@click.option('--sid-baidu', default='学号', type=click.STRING)
@click.option('--score-baidu', default='评分(0-100)', type=click.STRING)
def collect(scores, weights, tasks, output, **kwargs):
    """Collected scores downloaded from AI studio and save to output."""
    assert len(tasks) == len(weights)
    assert len(scores) == len(weights)

    scores_all, students = {}, {}
    fields = [kwargs["sid_baidu"], kwargs["score_baidu"], kwargs["name_baidu"]]
    for xlsfile, task in zip(scores, tasks):
        data = load_xls(xlsfile)
        sid_col, score_col, name_col = find_column_index(data[0], fields)
        score_task = value_dict(data, sid_col, score_col)
        scores_all[task] = score_task
        
        stus = value_dict(data, sid_col, name_col)
        students = merge_students(students, stus)

    weights_dict = {t: w for t, w in zip(tasks, weights)}
    data, errors = merge_scores(scores_all, weights_dict)
    fields = [kwargs["sid_baidu"]] + list(tasks) + ["加权平均分"]
    form = score_dict_to_table(data, fields)
    fmt = output.split(".")[-1]
    if "csv" == fmt:
        write_csv(form, output)
    elif "xls" == fmt:
        write_xls(form, output)

        
@xduscore.command()
@click.argument("forms", nargs=-1, type=click.Path(exists=True))
@click.option("-s", "--score", type=click.Path())
@click.option("-f", "--field", default="加权平均分", type=click.STRING)
@click.option('--sid-xdu', default='学号', type=click.STRING)
def fill(forms, score, field, **kwargs):
    """Fill forms for uploading to Xidian."""
    scores = load_xls(score)
    fields = [kwargs["sid_xdu"], field]
    sid_col, score_col = find_column_index(scores[0], fields)
    scores_dict = value_dict(scores, sid_col, score_col)

    for xlsfile in forms:
        score_form = load_xls(xlsfile)        
        sid_col, = find_column_index(score_form[0], [kwargs["sid_xdu"]])
        fill_score_form(score_form, scores_dict, sid_col)
        write_xls(score_form, xlsfile)


@xduscore.command()
@click.argument("classes", nargs=-1, type=click.Path(exists=True))
@click.option("-k", "--homework", nargs=1, type=click.Path(exists=True))
@click.option('--sid-xdu', default='学号(文本)', type=click.STRING)
def organize(classes, homework, **kwargs):
    """Organize homeworks donwloaded from baidu for archival."""
    fields = [kwargs["sid_xdu"]]
    student_classes = {}
    for cls in classes:
        class_name = cls.split(".")[0]
        if not os.path.exists(class_name):
            os.mkdir(class_name)
        hw_path = os.path.join(class_name, homework)
        if not os.path.exists(hw_path):
            os.mkdir(hw_path)
        data = load_xls(cls)
        sid_col, = find_column_index(data[0], fields)
        for row in data[1:]:
            sid = row[sid_col]
            student_classes[sid] = class_name

    for path, _, files in os.walk(homework):
        for name in files:
            if ".pdf" == name[-4:].lower():
                the_sid = name.split(".")[0].split("-")[-1]
                if the_sid in student_classes:
                    the_cls = student_classes[the_sid]
                    hw_src = os.path.join(path, name)
                    hw_dst = os.path.join(the_cls, homework, name)
                    # print(f"Copying {hw_src} to {hw_dst}...")
                    shutil.copyfile(hw_src, hw_dst)
                else:
                    print(f"Cannot find the class for student {the_sid}.")
               

# 
# score_helper.py ends here
