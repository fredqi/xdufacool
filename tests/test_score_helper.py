# test_score_helper.py ---
#
# Filename: test_score_helper.py
# Author: Fred Qi
# Created: 2022-09-07 21:45:54(+0800)
#
# Last-Updated: 2022-09-07 23:20:46(+0800) [by Fred Qi]
#     Update #: 26
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
from xdufacool.score_helper import ScoreStat


class TestScoreStat(TestCase):

    def test_grading(self):
        score_stat = ScoreStat()
        score_stat.grading(["43", "65", "95", "77", "88", "100", "50"])

        intervals = score_stat.stat
        self.assertEqual(intervals[0].count, 2, "优秀学生应为2人")
        self.assertEqual(intervals[-1].count, 2, "不及格学生应为2人")
      

# 
# test_score_helper.py ends here
