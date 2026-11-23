import pytest

import ScheduleReplanner as replanner
from Constants import COURSE_NOT_FOUND, OK, REPLAN_FAILED

pytestmark = pytest.mark.f10


def Course(courseId, slots, credits=3, capacity=30):
    return {
        "course_id": courseId, "title": courseId, "credits": credits,
        "required": False, "teacher": "T", "classroom_id": "R1",
        "capacity": capacity, "enrolled_count": 0,
        "time_slots": [{"day": day, "period": period} for day, period in slots],
    }


def test_replan_finds_same_credit_free_nonconflicting_replacement():
    database = {
        "courses": [
            Course("CANCEL", [(1, "1")], 3),
            Course("KEEP", [(2, "1")], 3),
            Course("NEW", [(3, "1")], 3),
            Course("CONFLICT", [(2, "1")], 3),
        ],
        "students": [{"student_id": "S1", "enrolled_courses": ["CANCEL", "KEEP"]}],
        "classrooms": [], "campus_graph": {},
    }
    ok, code, plan = replanner.ReplanOnCourseCancellation(database, "S1", "CANCEL")
    assert (ok, code) == (True, OK)
    assert "NEW" in plan["replacement_courses"]
    assert "CONFLICT" not in plan["replacement_courses"]


def test_replan_returns_failed_when_no_replacement():
    database = {
        "courses": [Course("CANCEL", [(1, "1")], 4)],
        "students": [{"student_id": "S1", "enrolled_courses": ["CANCEL"]}],
        "classrooms": [], "campus_graph": {},
    }
    assert replanner.ReplanOnCourseCancellation(database, "S1", "CANCEL") == (
        False, REPLAN_FAILED, {}
    )


def test_replan_unknown_course():
    database = {"courses": [], "students": [], "classrooms": [], "campus_graph": {}}
    assert replanner.ReplanOnCourseCancellation(database, "S1", "NOPE") == (
        False, COURSE_NOT_FOUND, {}
    )
