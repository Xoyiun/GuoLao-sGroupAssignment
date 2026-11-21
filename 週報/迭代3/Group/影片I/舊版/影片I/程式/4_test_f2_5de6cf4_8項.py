"""F2 多層次衝堂與選課檢查 的自動化測試。

每個測試自己組一份小資料庫，衝突情境一目了然，不受種子資料變動影響。
執行：python -m pytest -m f2 -v
"""

import datetime

import pytest

import ConflictChecker as conflictChecker
from Constants import (
    ACTIVITY_CONFLICT,
    ALREADY_ENROLLED,
    COURSE_FULL,
    CREDIT_LIMIT_EXCEEDED,
    NOT_FOUND,
    OK,
    ROOM_CONFLICT,
    TIME_CONFLICT,
)
from TimeSlotUtils import LOCAL_TIME_ZONE

pytestmark = pytest.mark.f2


def Course(courseId, slots, classroomId="R1", credits=3, capacity=30, enrolledCount=0, courseType=None):
    """組一門課；slots 寫成 [(星期, 節次), ...]。"""
    course = {
        "course_id": courseId,
        "title": courseId,
        "credits": credits,
        "required": False,
        "teacher": "T",
        "classroom_id": classroomId,
        "capacity": capacity,
        "enrolled_count": enrolledCount,
        "time_slots": [{"day": day, "period": period} for day, period in slots],
    }
    if courseType:
        course["course_type"] = courseType
    return course


def Database(courses, enrolled=(), maxCredits=25):
    """學生 S1 已選 enrolled 裡的課程。"""
    return {
        "classrooms": [{"classroom_id": "R1", "capacity": 50}, {"classroom_id": "R2", "capacity": 50}],
        "courses": courses,
        "students": [{
            "student_id": "S1", "name": "測試生", "department": "資工系",
            "max_credits": maxCredits, "enrolled_courses": list(enrolled),
        }],
        "campus_graph": {"nodes": [], "edges": []},
    }


def test_NoConflictPasses():
    database = Database([Course("A", [(1, "1")]), Course("NEW", [(2, "1")], classroomId="R2")], enrolled=["A"])
    assert conflictChecker.CheckEnrollmentConflicts(database, "S1", "NEW") == (True, OK, [])


def test_AllConflictsListedAndSortedByDayAndPeriod():
    """學生衝堂、教室衝堂、額滿、學分超過同時發生 → 全部列出，時段衝突依星期、節次排序，限制排最後。"""
    database = Database(
        [
            Course("THU", [(4, "5")], classroomId="R2", credits=10),
            Course("TUE", [(2, "3"), (2, "4")], classroomId="R2", credits=10),
            Course("ROOM", [(1, "a")], classroomId="R1"),           # 學生沒選，但跟 NEW 搶同一間教室
            Course("NEW", [(4, "5"), (2, "4"), (2, "3"), (1, "a")], classroomId="R1",
                   credits=6, capacity=30, enrolledCount=30),
        ],
        enrolled=["THU", "TUE"],
    )
    ok, code, conflicts = conflictChecker.CheckEnrollmentConflicts(database, "S1", "NEW")

    assert not ok and code == ROOM_CONFLICT
    assert [conflict["type"] for conflict in conflicts] == [
        ROOM_CONFLICT, TIME_CONFLICT, TIME_CONFLICT, COURSE_FULL, CREDIT_LIMIT_EXCEEDED,
    ]
    assert conflicts[0]["conflict_with_course"] == "ROOM"
    assert conflicts[1]["conflict_with_course"] == "TUE"
    assert conflicts[1]["slots"] == [{"day": 2, "period": "3"}, {"day": 2, "period": "4"}]
    assert conflicts[2]["conflict_with_course"] == "THU"
    assert conflicts[4]["current_credits"] == 20 and conflicts[4]["max_credits"] == 25


def test_PeriodsLettersSortAfterNine():
    """同一天的節次 9 要排在 a 前面（不是照字串大小）。"""
    database = Database(
        [Course("A", [(3, "a")], classroomId="R2"), Course("B", [(3, "9")], classroomId="R2"),
         Course("NEW", [(3, "a"), (3, "9")])],
        enrolled=["A", "B"],
    )
    _, _, conflicts = conflictChecker.CheckEnrollmentConflicts(database, "S1", "NEW")
    assert [conflict["conflict_with_course"] for conflict in conflicts] == ["B", "A"]


def test_ActivityOnDateConflictsWithWeeklyCourse():
    """學生報名的活動（event 課程，日期時段）落在新課程同一星期、同一節 → 活動衝突。"""
    tuesday = int(datetime.datetime(2026, 10, 6, tzinfo=LOCAL_TIME_ZONE).timestamp())  # 星期二
    database = Database(
        [Course("ACT", [(tuesday, "5")], classroomId="R2", credits=0, courseType="event"),
         Course("NEW", [(2, "5")])],
        enrolled=["ACT"],
    )
    ok, code, conflicts = conflictChecker.CheckEnrollmentConflicts(database, "S1", "NEW")
    assert not ok and code == ACTIVITY_CONFLICT
    assert conflicts[0]["conflict_with_activity"] == "ACT"


def test_AlreadyEnrolledIsRejected():
    """重複加選已選的課 → ALREADY_ENROLLED，不會誤報成跟自己衝堂。"""
    database = Database([Course("A", [(1, "1")])], enrolled=["A"])
    assert conflictChecker.CheckEnrollmentConflicts(database, "S1", "A") == (
        False, ALREADY_ENROLLED, [{"type": ALREADY_ENROLLED, "course_id": "A"}]
    )


@pytest.mark.parametrize("studentId, courseId, target", [("NOPE", "A", "student"), ("S1", "NOPE", "course")])
def test_UnknownStudentOrCourse(studentId, courseId, target):
    database = Database([Course("A", [(1, "1")])])
    ok, code, conflicts = conflictChecker.CheckEnrollmentConflicts(database, studentId, courseId)
    assert (ok, code, conflicts[0]["target"]) == (False, NOT_FOUND, target)


def test_ClassroomConflictIgnoresTheCourseItself():
    """修改課程時排除自己，不會被自己的時段擋住。"""
    database = Database([Course("A", [(1, "1")])])
    slots = [{"day": 1, "period": "1"}]
    assert conflictChecker.CheckClassroomConflict(database, "R1", slots, excludeCourseId="A") == (True, OK)
    assert conflictChecker.CheckClassroomConflict(database, "R1", slots) == (False, ROOM_CONFLICT)
