# metrics.py ---
#
# Filename: metrics.py
# Author: Fred Qi
# Created: 2022-06-06 11:10:28(+0800)
#
# Last-Updated: 2022-06-06 19:29:32(+0800) [by Fred Qi]
#     Update #: 304
# 

# Commentary:
#
#
# 

# Change Log:
#
#
# 

import csv
import bisect
from os import path


def load_classification_result(datafile):
    """Load blank/tab separated result files."""
    results = {}
    with open(datafile) as istream:
        data = istream.readlines()
        for ln in data:
            ln = ln.strip()
            if not ln:
                continue
            filename, label = ln.split()
            pathname, _ = path.splitext(filename)
            basename = path.basename(pathname)
            # print(ln, label, len(f'{label}'), sep=',')
            results[basename] = int(label)
    return results


def classification_accuracy(y_true, y_pred):
    n_total = float(len(y_true))
    n_correct = 0
    for key, value in y_true.items():
        if key not in y_pred:
            continue
        if value == y_pred[key]:
            n_correct += 1
    return n_correct/n_total    


class ClassificationAccuracy(object):

    def __init__(self, gt_file):
        self.y_true = load_classification_result(gt_file)

    def accuracy(self, submission):
        y_pred = load_classification_result(submission)
        return classification_accuracy(self.y_true, y_pred)

    def eval_submissions(self, submissions):
        accuracy = {}
        for key, submission in submissions.items():
            if not path.isfile(submission):
                continue
            accuracy[key] = self.accuracy(submission)
        return accuracy


class LeaderBoardItem(object):
    def __init__(self, item):
        self.student_id = item['student_id']
        self.accuracy = float(item['accuracy'])
        self.time_submit = item['time_submit']
        self.count = int(item['count'])

    def __lt__(self, other):
        return self.accuracy < other.accuracy

    def __eq__(self, other):
        eq_id = self.student_id == other.student_id
        eq_acc = self.accuracy == other.accuracy
        # eq_time = self.time_submit == other.time_submit
        # eq_count = self.count == other.count
        return eq_id and eq_acc

    def __repr__(self):
        return f"{self.student_id} ACC {self.accuracy*100:5.2f}%"

    def __str__(self):
        return f"{self.student_id} {self.accuracy*100:5.2f}%"


class LeaderBoard(object):

    def __init__(self, filename):
        self.students = {}
        self.leaderboard = []
        self._filename = filename
        self._fields = ['student_id', 'accuracy', 'time_submit', 'count']
        self.load()

    def update(self, item):
        stu_id = item.student_id
        acc = self.students.get(stu_id, 0)
        if item.accuracy > acc:
            self.students[stu_id] = item.accuracy
            if acc > 0:
                for idx in range(len(self.leaderboard)):
                    if self.leaderboard[idx].student_id == stu_id:
                        break
                self.leaderboard.pop(idx)
            bisect.insort_left(self.leaderboard, item)
            

    def load(self):
        with open(self._filename) as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=self._fields)
            header = next(reader)
            for row in reader:
                self.update(LeaderBoardItem(row))

    def save(self):
        with open(self._filename, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self._fields)
            writer.writeheader()
            for row in reversed(self.leaderboard):
                writer.writerow(row.__dict__)

    def display(self, topK=20):
        items = reversed(self.leaderboard[-topK:])
        lines = []
        for idx, item in enumerate(items):
            if item.accuracy < 0.80:
                break
            lines.append(str(item) + f" {idx+1:2d}")
        return "\n".join(lines)

# 
# metrics.py ends here
