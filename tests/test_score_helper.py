# test_score_helper.py ---
#
# Filename: test_score_helper.py
# Author: Fred Qi
# Created: 2022-09-07 21:45:54(+0800)
#
# Last-Updated: 2022-09-12 17:04:08(+0800) [by Fred Qi]
#     Update #: 43
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
from xdufacool.score_helper import ScoreAnalysis


class TestScoreStat(TestCase):

    def test_grading(self):
        score_stat = ScoreStat('02', ["43", "65", "95", "77", "88", "100", "50"])

        intervals = score_stat.stat
        self.assertEqual(intervals[0].count, 2, "优秀学生应为2人")
        self.assertEqual(intervals[-1].count, 2, "不及格学生应为2人")
      

class TestScoreAnalysis(TestCase):

    def test_abilities(self):
        score_analysis = ScoreAnalysis()
        score_analysis.add_parts(['homeworks', 'final'],
                                 [["43", "65", "95", "77", "88", "100", "50"],
                                  ["63", "75", "95", "77", "88", "100", "80"]])
        # print(score_analysis)
        self.assertEqual(score_analysis.get_text('avg_ind42'), '15.74',
                         "Indicator 43 incorrect")
        self.assertEqual(score_analysis.get_text('avg_homeworks'), '74.00',
                         "Averaged homeworks incorrect")
        
# 
# test_score_helper.py ends here
