# test_metrics.py ---
#
# Filename: test_metrics.py
# Author: Fred Qi
# Created: 2022-06-06 11:19:45(+0800)
#
# Last-Updated: 2022-06-06 16:33:32(+0800) [by Fred Qi]
#     Update #: 99
# 

# Commentary:
#
#
# 

# Change Log:
#
#
#
from unittest import TestCase
from xdufacool.metrics import load_classification_result
from xdufacool.metrics import classification_accuracy
from xdufacool.metrics import ClassificationAccuracy
from xdufacool.metrics import LeaderBoardItem
from xdufacool.metrics import LeaderBoard


class TestAccuracy(TestCase):

    def setUp(self):
        self.gt = {'f5JapBNenR7tjkYxO1V4cHgL3dlTPCyA': 3,
                   'SukGlhoeUfjiqwIFcJLgxWdbO3sBQrzZ': 5,
                   'pKHWP5NGI6urf034B7nbqF1Y9URdesw2': 11}
        self.pred = {'f5JapBNenR7tjkYxO1V4cHgL3dlTPCyA': 3,
                     'SukGlhoeUfjiqwIFcJLgxWdbO3sBQrzZ': 6,
                     'pKHWP5NGI6urf034B7nbqF1Y9URdesw2': 11,
                     'pKHWP5NGI6urf444B7nbqF1Y9URdesw2': 10}
        self.accuracy = {'19200300098': 2.0/3,
                         '20200340003': 2.0/3}

    def test_load_results(self):
        results = load_classification_result('tests/data/test_list.txt')
        self.assertEqual(self.gt, results,
                         "Error loading classification results.")

    def test_classification_accuracy(self):
        accuracy = classification_accuracy(self.gt, self.pred)
        self.assertEqual(2.0/3, accuracy,
                         "Incorrect classification accuracy.")

    def test_ClassificationAccuracy(self):
        acc_metric = ClassificationAccuracy('tests/data/test_list.txt')
        accuracy = acc_metric.accuracy('tests/data/test_pred.txt')
        self.assertEqual(2.0/3, accuracy,
                         "Incorrect classification accuracy.")

    def test_eval_submissions(self):
        submissions = {'19200300098': 'tests/data/test_pred.txt',
                       '20200340003': 'tests/data/test_pred.txt'}
        acc_metric = ClassificationAccuracy('tests/data/test_list.txt')
        accuracy = acc_metric.eval_submissions(submissions)
        self.assertEqual(self.accuracy, accuracy,
                         "Error in batch evaluation of submissions.")


class TestLeaderBoard(TestCase):

    def setUp(self):
        self.lb_ref = []
        data = [['20200340003',0.66666666,'',1],
                ['19200300098',0.67777777,'',2]]
        for row in data:
            row_dict = {'student_id': row[0],
                        'accuracy': row[1],
                        'time_submit': row[2],
                        'count': row[3]}
            item = LeaderBoardItem(row_dict)
            self.lb_ref.append(item)

    def test_leader_board_item(self):
        row_dict = {'student_id': '19200300098',
                    'accuracy': 0.67777777,
                    'time_submit': '','count': 2}
        item = LeaderBoardItem(row_dict)
        self.assertEqual(item.student_id, '19200300098', "Error student ID.")
        self.assertEqual(item.accuracy, 0.67777777, "Error accuracy.")
        
    def test_load(self):
        leaderboard = LeaderBoard('tests/data/leaderboard.csv')
        self.assertEqual(leaderboard.leaderboard, self.lb_ref,
                         "Error loading leader board.")
        leaderboard.save()


# 
# test_metrics.py ends here
