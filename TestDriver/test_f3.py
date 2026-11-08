"""F3 個人課表產生與空閒時段查詢 的自動化測試。

作業規範 F3 驗收條件：以星期一至星期日及 12 個節次建立課表矩陣，並測試
「連續三節空堂」、「跨日查詢」及「同一天多門課程」的情況。
每個測試自己組一份小資料庫，情境一目了然。執行：python -m pytest -m f3 -v
"""

import datetime

import pytest

import Timetable as timetable
from TimeSlotUtils import LOCAL_TIME_ZONE

pytestmark = pytest.mark.f3


def Course(courseId, slots, credits=3, courseType=None):
    """組一門課；slots 寫成 [(星期或日期時間戳, 節次), ...]。"""
    course = {
        "course_id": courseId,
        "title": courseId,
        "credits": credits,
        "time_slots": [{"day": day, "period": period} for day, period in slots],
    }
    if courseType:
        course["course_type"] = courseType
    return course


def Database(courses, enrolled):
    return {"courses": courses, "students": [{"student_id": "S1", "enrolled_courses": list(enrolled)}]}


@pytest.fixture(name="weekTable")
def WeekTable():
    """星期一：A 第 1–2 節、B 第 5 節（同一天多門課）；星期三：A 第 3 節（同一門課一週多次）。"""
    database = Database(
        [Course("A", [(1, "1"), (1, "2"), (3, "3")], credits=3), Course("B", [(1, "5")], credits=2),
         Course("C", [(2, "1")])],  # C 沒有被選，不能出現在課表上
        enrolled=["A", "B"],
    )
    return database, timetable.build_timetable(database, "S1")


def test_MatrixIsSevenDaysByTwelvePeriods(weekTable):
    _, table = weekTable
    assert len(table) == 7 and all(len(row) == 12 for row in table)


def test_SameDayMultipleCoursesAndRepeatedCourse(weekTable):
    """同一天多門課都排進去；同一門課每週多次，每個時段都要出現；沒選的課不出現。"""
    _, table = weekTable
    assert table[0][:5] == ["A", "A", None, None, "B"]
    assert timetable.find_course_in_timetable(table, "A") == [(1, "1"), (1, "2"), (3, "3")]
    assert timetable.find_course_in_timetable(table, "C") == []


def test_ConsecutiveThreeFreePeriods(weekTable):
    """星期一第 1–9 節中，第 3–4 節只有兩節空堂、第 6–9 節有四節 → 至少三節只找到後者。"""
    _, table = weekTable
    assert timetable.find_free_slots(table, 1, "1", "9", 3) == [("6", "9")]
    assert timetable.find_free_slots(table, 1, "1", "9", 2) == [("3", "4"), ("6", "9")]


def test_CrossDayQuery(weekTable):
    """跨日查詢：星期一第 6 節到星期三第 4 節，至少三節；每天分開計算，不跨越午夜。"""
    _, table = weekTable
    assert timetable.find_free_slots_between(table, 1, "6", 3, "4", 3) == [
        (1, "6", "c"), (2, "1", "c"),
    ]
    assert timetable.find_free_slots_between(table, 1, "6", 3, "4", 2) == [
        (1, "6", "c"), (2, "1", "c"), (3, "1", "2"),
    ]


def test_CrossDayQueryRejectsReversedRange(weekTable):
    _, table = weekTable
    with pytest.raises(ValueError):
        timetable.find_free_slots_between(table, 3, "1", 1, "c")


def test_SummaryCountsDailyPeriodsCreditsAndGaps(weekTable):
    """每日上課節數、每週總學分、空堂數（星期一第 3、4 節夾在兩堂課中間 = 2）。"""
    database, table = weekTable
    summary = timetable.summarize_timetable(table, database, "S1")
    assert summary["daily_period_counts"] == [3, 0, 1, 0, 0, 0, 0]
    assert summary["total_credits"] == 5
    assert summary["gap_period_count"] == 2
    assert summary["free_period_count"] == 84 - 4


def test_QueryByDayPeriodAndCourse(weekTable):
    _, table = weekTable
    assert timetable.query_timetable(table, day=1) == [(1, "1", "A"), (1, "2", "A"), (1, "5", "B")]
    assert timetable.query_timetable(table, period="3") == [(3, "3", "A")]
    assert timetable.query_timetable(table, course_id="B") == [(1, "5", "B")]


def test_EnrolledActivityAppearsOnItsWeekday():
    """學生報名的活動（event 課程、日期時段）要排在對應星期，且不計入學分（D13）。"""
    tuesday = int(datetime.datetime(2026, 10, 6, tzinfo=LOCAL_TIME_ZONE).timestamp())
    database = Database(
        [Course("A", [(1, "1")]), Course("ACT", [(tuesday, "5")], credits=0, courseType="event")],
        enrolled=["A", "ACT"],
    )
    table = timetable.build_timetable(database, "S1")
    assert table[1][4] == "ACT"
    assert timetable.summarize_timetable(table, database, "S1")["total_credits"] == 3


def test_UnknownStudentReturnsNone():
    assert timetable.build_timetable(Database([], []), "NOPE") is None
