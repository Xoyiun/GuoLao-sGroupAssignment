import pytest

import ScheduleOptimizer as optimizer
from Constants import NO_FEASIBLE_SCHEDULE, OK

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
