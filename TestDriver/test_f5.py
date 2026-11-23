import pytest

import CourseFilter as courseFilter
from Constants import CONFLICTING_CRITERIA, MIN_CREDITS_UNMET, OK

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
