import copy

import pytest

import CourseFilter as courseFilter
from Constants import (
    CONFLICTING_CRITERIA, COURSE_FULL, INVALID_FIELD, MIN_CREDITS_UNMET, NOT_FOUND, OK,
)

pytestmark = pytest.mark.f5


def Course(courseId, slots, credits=3, capacity=30, enrolled=0):
    return {
        "course_id": courseId, "title": courseId, "credits": credits,
        "required": False, "teacher": "T", "classroom_id": "R1",
        "capacity": capacity, "enrolled_count": enrolled,
        "time_slots": [{"day": day, "period": period} for day, period in slots],
    }


def Database(courses):
    return {
        "courses": courses,
        "students": [],
        "classrooms": [{"classroom_id": "R1", "capacity": 50, "equipment": []}],
        "campus_graph": {},
    }


def test_filter_by_blocked_slots_preferred_days_and_seats():
    database = Database([
        Course("A", [(1, "1")]),
        Course("B", [(3, "2")], capacity=1, enrolled=1),
        Course("C", [(3, "3")]),
    ])
    ok, code, courses = courseFilter.FilterCourses(database, {
        "blocked_slots": [{"day": 1, "period": "1"}],
        "preferred_days": [3],
        "has_seats": True,
    })
    assert (ok, code) == (True, OK)
    assert [course["course_id"] for course in courses] == ["C"]


def test_required_course_in_blocked_slot_is_conflict():
    database = Database([Course("A", [(1, "1")])])
    assert courseFilter.FilterCourses(database, {
        "required_ids": ["A"],
        "blocked_slots": [{"day": 1, "period": "1"}],
    }) == (False, CONFLICTING_CRITERIA, [])


def test_minimum_credits_unmet():
    database = Database([Course("A", [(1, "1")], credits=2)])
    assert courseFilter.FilterCourses(database, {"min_credits": 3}) == (
        False, MIN_CREDITS_UNMET, []
    )


# ======================================================================
# 可行性檢查 CheckCourseFeasibility：五種以上的選課情境
# ======================================================================
def Check(courses, **criteria):
    return courseFilter.CheckCourseFeasibility(Database(courses), criteria)


def Ids(report):
    return [course["course_id"] for course in report["candidates"]]


def Types(report):
    return [problem["type"] for problem in report["problems"]]


def test_FeasiblePlanReportsCandidatesAndExclusionReasons():
    """情境一：條件可行 → 列出候選課程，並說明每門被排除的課違反哪些條件。"""
    ok, code, report = Check(
        [Course("REQ", [(1, "1")]), Course("A", [(3, "2")]), Course("FULL", [(3, "3")], capacity=1, enrolled=1),
         Course("BAD", [(2, "1")], capacity=1, enrolled=1)],
        required_ids=["REQ"], blocked_slots=[{"day": 2, "period": "1"}], preferred_days=[3],
        min_credits=6, max_credits=6,
    )
    assert (ok, code) == (True, OK)
    assert Ids(report) == ["REQ", "A"]  # 必修不受偏好星期限制
    assert report["excluded"] == [
        ("FULL", ["full"]),
        ("BAD", ["blocked", "not_preferred_day", "full"]),
    ]
    assert report["reachable_credits"] == 6 and report["problems"] == []


def test_WishedCoursesLimitCandidatesButKeepRequired():
    """情境二：只從希望修習的課程與必修挑選；查無此課的代號要回報。"""
    courses = [Course("REQ", [(1, "1")]), Course("WISH", [(2, "1")]), Course("OTHER", [(3, "1")])]
    ok, _, report = Check(courses, required_ids=["REQ"], wished_ids=["WISH"])
    assert ok and Ids(report) == ["REQ", "WISH"]
    ok, code, report = Check(courses, wished_ids=["NOPE"], required_ids=["GONE"])
    assert (ok, code) == (False, NOT_FOUND)
    assert [problem["course_id"] for problem in report["problems"] if problem["type"] == NOT_FOUND] == ["GONE", "NOPE"]


def test_ContradictoryCriteriaAreAllListed():
    """情境三：條件互相矛盾 → 一次列出全部原因，不會遇到第一個就停。"""
    ok, code, report = Check(
        [Course("R1", [(1, "1")], credits=3), Course("R2", [(1, "1")], credits=3)],
        required_ids=["R1", "R2"], blocked_slots=[{"day": 1, "period": "1"}], min_credits=9, max_credits=5,
    )
    assert not ok and code == CONFLICTING_CRITERIA
    assert [problem["reason"] for problem in report["problems"] if problem["type"] == CONFLICTING_CRITERIA] == [
        "credit_range", "required_blocked", "required_blocked", "required_overlap", "required_credits",
    ]


def test_FullRequiredCourseIsInfeasibleUnlessAlreadyEnrolled():
    """情境四：必修額滿 → 不可行；但學生本來就選了這門課則不受影響。"""
    courses = [Course("REQ", [(1, "1")], capacity=1, enrolled=1)]
    ok, code, report = Check(courses, required_ids=["REQ"])
    assert (ok, code) == (False, COURSE_FULL) and report["problems"][0]["course_id"] == "REQ"
    assert Check(courses, required_ids=["REQ"], enrolled_ids=["REQ"])[0]


def test_MinimumCreditsUnreachableReportsBestTotal():
    """情境五：候選合計只有 9 學分 → 回報最多能選幾學分。"""
    ok, code, report = Check([Course(name, [(day, "1")]) for day, name in enumerate("ABC", start=1)], min_credits=12)
    assert (ok, code) == (False, MIN_CREDITS_UNMET)
    assert report["problems"] == [{"type": MIN_CREDITS_UNMET, "min_credits": 12, "reachable_credits": 9}]


def test_EnoughTotalButOverlappingCoursesStillUnmet():
    """情境六：四門 3 學分合計 12，但兩門互相衝堂 → 最多 9，保留候選清單並指出無法達成。"""
    ok, code, report = Check(
        [Course("A", [(1, "1")]), Course("B", [(1, "1")]), Course("C", [(2, "1")]), Course("D", [(3, "1")])],
        min_credits=12,
    )
    assert (ok, code) == (False, MIN_CREDITS_UNMET)
    assert Ids(report) == ["A", "B", "C", "D"] and report["reachable_credits"] == 9


def test_CreditBoundariesAndUnreachableExactRange():
    """邊界：剛好等於上下限可行；每門 3 學分湊不出 4～5 學分。"""
    courses = [Course("A", [(1, "1")]), Course("B", [(2, "1")])]
    assert Check(courses, min_credits=6, max_credits=6)[0]
    ok, code, report = Check(courses, min_credits=4, max_credits=5)
    assert (ok, code, report["reachable_credits"]) == (False, MIN_CREDITS_UNMET, 3)


def test_NonRequiredOverlappingRequiredCannotCountTowardCredits():
    """必修一定要選，跟必修衝堂的課不能拿來湊學分。"""
    ok, _, report = Check([Course("REQ", [(1, "1")]), Course("A", [(1, "1")])], required_ids=["REQ"], min_credits=6)
    assert not ok and report["reachable_credits"] == 3


def test_ActivitiesAreNotCandidates():
    event = Course("ACT", [(1, "1")])
    event["course_type"] = "event"
    assert Ids(Check([event, Course("A", [(2, "1")])])[2]) == ["A"]
    assert Types(Check([event], required_ids=["ACT"])[2]) == [NOT_FOUND]


@pytest.mark.parametrize("criteria", [
    {"min_credits": -1}, {"max_credits": "9"}, {"min_credits": True}, {"wished_ids": "A"}, {"required_ids": [1]},
    {"preferred_days": [8]}, {"preferred_days": 3}, {"preferred_days": [[1]]}, {"enrolled_ids": None},
    {"blocked_slots": [{"day": 8, "period": "1"}]}, {"blocked_slots": "1-1"},
])
def test_InvalidCriteriaAreRejected(criteria):
    ok, code, report = courseFilter.CheckCourseFeasibility(Database([]), criteria)
    assert (ok, code, report["candidates"]) == (False, INVALID_FIELD, [])


def test_CheckDoesNotChangeDatabaseAndHandlesManyCourses():
    """檢查不修改資料；24 門課（每節兩門互相衝堂）也要能很快得到結果。"""
    courses = [Course(f"C{index}", [(index // 2 % 7 + 1, str(index // 14 + 1))]) for index in range(24)]
    database = Database(courses)
    before = copy.deepcopy(database)
    ok, code, report = courseFilter.CheckCourseFeasibility(database, {"min_credits": 99})
    assert (ok, code, report["reachable_credits"]) == (False, MIN_CREDITS_UNMET, 36)
    assert database == before
