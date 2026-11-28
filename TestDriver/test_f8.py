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


# ======================================================================
# S03、S04：回溯法
# ======================================================================
def test_BacktrackingMatchesBruteForce():
    """S03：同一題目兩法的可行解集合完全相同。

    小題目的回溯法節點數（22，手算見演算法說明）反而比窮舉法（16）多：
    回溯法連中途的部分選法也算節點，限制不夠多時剪枝省不了多少。
    """
    result = searchCompare.BacktrackingSearch(SmallProblem())
    assert result["solutions"] == SMALL_SOLUTIONS
    assert result["nodes"] == 22
    assert result["completed"] is True


def test_BacktrackingPrunes():
    """S04：8 門各 3 學分、彼此不衝堂、學分 3–6（最多選 2 門）。

    窮舉法檢查 2⁸ = 256 個組合；回溯法只走「已選 ≤ 2 門」的狀態：
    Σ(i=0..8) [C(i,0) + C(i,1) + C(i,2)] = 129 個節點。可行解 C(8,1) + C(8,2) = 36 個。
    """
    database = Database([Course(f"K{index}", [(1 + index % 7, str(1 + index // 7))]) for index in range(8)])
    problem = Problem(database, candidate_courses=[f"K{index}" for index in range(8)], min_credits=3, max_credits=6)

    brute = searchCompare.BruteForceSearch(problem)
    back = searchCompare.BacktrackingSearch(problem)
    assert (brute["nodes"], back["nodes"]) == (256, 129)
    assert len(back["solutions"]) == 36
    assert back["solutions"] == brute["solutions"]


# ======================================================================
# S05–S07、S09：時間上限、比較報告、與 F7 一致、錯誤輸入
# ======================================================================
@pytest.mark.parametrize("search", ["BruteForceSearch", "BacktrackingSearch"])
def test_TimeLimitStopsAndReportsIncomplete(search):
    """S05：時間上限 0 秒 → 立即停止並回報未完成（規範：逾時須如實記錄未完成情況）。"""
    result = getattr(searchCompare, search)(SmallProblem(), timeLimit=0)
    assert result["completed"] is False
    assert result["nodes"] < 16


def test_CompareReportsBothAlgorithms():
    """S06：比較報告包含兩法的節點數、時間、可行解數與一致性。"""
    ok, code, report = searchCompare.CompareAlgorithms(SmallDatabase(), "S1", {
        "candidate_courses": ["A", "B", "C", "E"], "min_credits": 3, "max_credits": 6,
    })
    assert (ok, code) == (True, OK)
    assert report["candidate_count"] == 4
    assert {key: report["brute_force"][key] for key in ("nodes", "solutions", "completed")} == {
        "nodes": 16, "solutions": 8, "completed": True}
    assert {key: report["backtracking"][key] for key in ("nodes", "solutions", "completed")} == {
        "nodes": 22, "solutions": 8, "completed": True}
    assert report["brute_force"]["seconds"] >= 0 and report["backtracking"]["seconds"] >= 0
    assert report["consistent"] is True


def test_CompareWithTimeLimitCannotJudgeConsistency():
    """S05：有一方未完成時，一致性標為 None（無法判定），不能當成一致。"""
    _, _, report = searchCompare.CompareAlgorithms(SmallDatabase(), "S1", {
        "candidate_courses": ["A", "B", "C", "E"], "min_credits": 3, "max_credits": 6,
    }, timeLimit=0)
    assert report["brute_force"]["completed"] is False
    assert report["consistent"] is None


def test_F7AndF8AgreeOnFeasiblePlans():
    """S07：F7 最佳課表搜尋找到的方案，與 F8 兩種演算法的可行解完全相同（共用同一套條件）。"""
    preferences = {"candidate_courses": ["A", "B", "C", "E"], "min_credits": 3, "max_credits": 6}
    _, _, plans = optimizer.SearchOptimalSchedules(SmallDatabase(), "S1", preferences)
    f7 = sorted(tuple(sorted(plan["courses"])) for plan in plans)
    assert f7 == searchCompare.BruteForceSearch(SmallProblem())["solutions"] == SMALL_SOLUTIONS


@pytest.mark.parametrize("studentId, preferences", [
    ("NOPE", {}),
    ("S1", {"required_courses": ["NOPE"]}),
    ("S1", {"min_credits": -1}),
])
def test_CompareRejectsInvalidInput(studentId, preferences):
    """S09：學生或必修課不存在、學分格式錯誤 → INVALID_FIELD。"""
    assert searchCompare.CompareAlgorithms(SmallDatabase(), studentId, preferences) == (False, INVALID_FIELD, {})
