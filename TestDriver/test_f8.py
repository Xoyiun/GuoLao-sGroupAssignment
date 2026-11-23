import pytest

import SearchCompare as searchCompare
from Constants import OK

pytestmark = pytest.mark.f8


def test_compares_real_search_metrics():
    database = {
        "courses": [{
            "course_id": "A", "title": "A", "credits": 3,
            "required": False, "teacher": "T", "classroom_id": "R1",
            "capacity": 30, "enrolled_count": 0,
            "time_slots": [{"day": 1, "period": "1"}],
        }],
        "students": [{"student_id": "S1", "enrolled_courses": []}],
    }
    ok, code, metrics = searchCompare.CompareAlgorithms(database, "S1", {
        "required_courses": ["A"],
    })
    assert (ok, code) == (True, OK)
    assert metrics["brute_force"]["nodes_searched"] >= 2
    assert metrics["backtracking"]["nodes_searched"] >= 2
