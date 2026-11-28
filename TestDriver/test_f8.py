"""F8 搜尋演算法比較的自動化測試（迭代 5A 以 TDD 開發：先寫這些測試，再實作）。

對應需求：週報/迭代5A/Group/F8演算法說明.md 第六節 S01–S09。
執行：python -m pytest -m f8 -v
"""

import pytest

import ScheduleOptimizer as optimizer
import SearchCompare as searchCompare
from Constants import INVALID_FIELD, OK

pytestmark = pytest.mark.f8


def Course(courseId, slots, credits=3, capacity=30, enrolledCount=0):
    return {
        "course_id": courseId, "title": courseId, "credits": credits,
        "required": False, "teacher": "T", "classroom_id": "R1",
        "capacity": capacity, "enrolled_count": enrolledCount,
        "time_slots": [{"day": day, "period": period} for day, period in slots],
    }


def Database(courses, enrolled=()):
    return {
        "courses": courses,
        "students": [{"student_id": "S1", "name": "S", "department": "CS",
                      "max_credits": 25, "enrolled_courses": list(enrolled)}],
    }


def Problem(database, **preferences):
    ok, code, problem = optimizer.BuildSearchProblem(database, "S1", preferences)
    assert (ok, code) == (True, OK)
    return problem


def SmallDatabase():
    """A、B 同在星期一第 1 節（互相衝堂）；A、B、E 各 3 學分，C 2 學分。"""
    return Database([
        Course("A", [(1, "1")]), Course("B", [(1, "1")]),
        Course("C", [(2, "1")], credits=2), Course("E", [(4, "1")]),
    ])


def SmallProblem():
    return Problem(SmallDatabase(), candidate_courses=["A", "B", "C", "E"], min_credits=3, max_credits=6)


# 手算：學分 3–6、A 與 B 不可同時選 → 8 個可行解
SMALL_SOLUTIONS = [
    ("A",), ("A", "C"), ("A", "E"), ("B",), ("B", "C"), ("B", "E"), ("C", "E"), ("E",),
]


# ======================================================================
# S01、S02：窮舉法
# ======================================================================
def test_BruteForceFindsEveryFeasibleSelection():
    """S01：4 門候選 → 檢查 2⁴ = 16 個組合，找到手算的 8 個可行解。"""
    result = searchCompare.BruteForceSearch(SmallProblem())
    assert result["solutions"] == SMALL_SOLUTIONS
    assert result["nodes"] == 16
    assert result["completed"] is True
    assert result["seconds"] >= 0


def test_BruteForceRespectsAllConstraints():
    """S02：與已選課程衝堂、禁止時段、額滿的課都不會出現在任何可行解中。"""
    database = Database([
        Course("X", [(5, "1")]),                         # 學生已選
        Course("CLASH", [(5, "1")]),                     # 與已選的 X 衝堂
        Course("BLOCK", [(6, "1")]),                     # 落在禁止時段
        Course("FULL", [(7, "1")], capacity=1, enrolledCount=1),
        Course("OK1", [(1, "5")]), Course("OK2", [(2, "5")]),
    ], enrolled=["X"])
    problem = Problem(database, candidate_courses=["CLASH", "BLOCK", "FULL", "OK1", "OK2"],
                      min_credits=3, max_credits=6, blocked_slots=[{"day": 6, "period": "1"}])
    result = searchCompare.BruteForceSearch(problem)
    assert result["solutions"] == [("OK1",), ("OK1", "OK2"), ("OK2",)]
    assert result["nodes"] == 32
