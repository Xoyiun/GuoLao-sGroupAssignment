import pytest

import ScheduleOptimizer as optimizer
from Constants import INVALID_FIELD, NO_FEASIBLE_SCHEDULE, OK

pytestmark = pytest.mark.f7


def Course(courseId, slots, credits=3, capacity=30):
    return {
        "course_id": courseId, "title": courseId, "credits": credits,
        "required": False, "teacher": "T", "classroom_id": "R1",
        "capacity": capacity, "enrolled_count": 0,
        "time_slots": [{"day": day, "period": period} for day, period in slots],
    }


def Database():
    return {
        "courses": [
            Course("REQ", [(1, "1")], 3),
            Course("A", [(2, "1")], 3),
            Course("B", [(3, "1")], 2),
            Course("CLASH", [(1, "1")], 3),
        ],
        "students": [{
            "student_id": "S1", "name": "S", "department": "CS",
            "max_credits": 25, "enrolled_courses": [],
        }],
        "classrooms": [{"classroom_id": "R1", "capacity": 50, "equipment": []}],
        "campus_graph": {},
    }


def test_searches_feasible_plans_and_sorts_by_score():
    ok, code, plans = optimizer.SearchOptimalSchedules(Database(), "S1", {
        "min_credits": 5, "max_credits": 8,
        "required_courses": ["REQ"], "candidate_courses": ["A", "B", "CLASH"],
    })
    assert ok and code == OK
    assert plans
    assert plans == sorted(plans, key=lambda plan: (-plan["score"], plan["courses"]))


def test_search_rejects_credit_limit():
    assert optimizer.SearchOptimalSchedules(Database(), "S1", {
        "min_credits": 20, "max_credits": 20,
        "required_courses": ["REQ"], "candidate_courses": ["A", "B"],
    }) == (False, NO_FEASIBLE_SCHEDULE, [])


# ======================================================================
# T06–T08：搜尋結果依偏好分數排序（迭代 4 TDD 第 3 輪，先寫測試再實作）
# ======================================================================
def PreferenceDatabase(enrolled=()):
    """EARLY 星期一第 1–2 節、LATE 星期一第 5–6 節、E 星期三第 5 節，各 3 學分。"""
    database = Database()
    database["courses"] = [
        Course("EARLY", [(1, "1"), (1, "2")]),
        Course("LATE", [(1, "5"), (1, "6")]),
        Course("E", [(3, "5")]),
    ]
    database["students"][0]["enrolled_courses"] = list(enrolled)
    return database


def OneOfTwo(**extra):
    """EARLY、LATE 只能選一門（學分上下限都是 3）。"""
    return {"min_credits": 3, "max_credits": 3, "candidate_courses": ["EARLY", "LATE"], **extra}


def test_SearchRanksByPreferenceScore():
    """T06：預設避開早八 → LATE 第一；早八權重 0 → 同分依代號 EARLY 第一；EARLY 設為偏好課程 → EARLY 第一。"""
    ok, code, plans = optimizer.SearchOptimalSchedules(PreferenceDatabase(), "S1", OneOfTwo())
    assert (ok, code) == (True, OK)
    assert [plan["courses"] for plan in plans] == [["LATE"], ["EARLY"]]
    assert [plan["score"] for plan in plans] == [0.5, -1.0]
    assert plans[0]["metrics"]["early_periods"] == 0 and plans[1]["metrics"]["early_periods"] == 1

    _, _, plans = optimizer.SearchOptimalSchedules(
        PreferenceDatabase(), "S1", OneOfTwo(weights={"early_periods": 0}))
    assert [plan["courses"] for plan in plans] == [["EARLY"], ["LATE"]]

    _, _, plans = optimizer.SearchOptimalSchedules(
        PreferenceDatabase(), "S1", OneOfTwo(preferred_courses=["EARLY"]))
    assert plans[0]["courses"] == ["EARLY"] and plans[0]["metrics"]["preferred_ratio"] == 1.0


def test_SearchCountsEnrolledCoursesInMetrics():
    """T07：學生已選星期三的 E，方案只排星期一的課，到校天數仍是 2 天。"""
    _, _, plans = optimizer.SearchOptimalSchedules(PreferenceDatabase(enrolled=["E"]), "S1", OneOfTwo())
    assert all(plan["metrics"]["campus_days"] == 2 for plan in plans)
    assert all(plan["metrics"]["credits"] == 3 for plan in plans)  # 學分只算方案中新排入的課


@pytest.mark.parametrize("extra", [
    {"weights": {"lunch_break": 1}},
    {"weights": {"early_periods": -2}},
    {"preferred_courses": "EARLY"},
])
def test_SearchRejectsInvalidPreferences(extra):
    """T08：權重或偏好課程格式錯誤 → INVALID_FIELD。"""
    assert optimizer.SearchOptimalSchedules(PreferenceDatabase(), "S1", OneOfTwo(**extra)) == (
        False, INVALID_FIELD, [])
