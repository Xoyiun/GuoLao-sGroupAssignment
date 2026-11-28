"""F8 搜尋演算法比較模組 (Search Comparison)。

本副程式負責評測與比較不同課表搜尋演算法之效能：
- 窮舉法 (Brute-Force)
- 回溯法 (Backtracking)

介面規範：
- 輸入參數皆有明確之型別與規格。
- 回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

import time
from itertools import combinations
import copy
from Constants import INVALID_FIELD, OK
import CourseDataManager as courseDataManager
from TimeSlotUtils import TimeSlotsOverlap


def BruteForceSearch(problem):
    import ScheduleOptimizer

    start = time.perf_counter()
    candidates = problem["candidates"]
    solutions = []
    nodes = 0
    for mask in range(1 << len(candidates)):
        nodes += 1
        chosen = [candidates[index] for index in range(len(candidates)) if mask & (1 << index)]
        if ScheduleOptimizer.IsFeasibleSelection(problem, problem["required"] + chosen):
            solutions.append(tuple(sorted(course["course_id"] for course in problem["required"] + chosen)))
    return {
        "solutions": sorted(solutions),
        "nodes": nodes,
        "seconds": time.perf_counter() - start,
        "completed": True,
    }


def CompareAlgorithms(database: dict, studentId: str, preferences: dict) -> tuple[bool, str, dict]:
    """評測並比較兩種演算法在相同資料上的搜尋耗時與走訪節點數。

    輸入：
        db: 標準資料庫字典
        student_id: 學號
        preferences: 搜尋偏好字典
    回傳：
        (ok, code, metrics):
        - 成功：(True, OK, {
            "brute_force": {"time_seconds": float, "nodes_searched": int},
            "backtracking": {"time_seconds": float, "nodes_searched": int},
            "winner": str
          })
        - 失敗：(False, INVALID_FIELD, {})
    """
    if not isinstance(preferences, dict):
        return False, INVALID_FIELD, {}

    student = courseDataManager.FindStudent(database, studentId)
    if not student:
        return False, INVALID_FIELD, {}
    required = preferences.get("required_courses", [])
    candidates = preferences.get("candidate_courses", [])
    if not isinstance(required, list) or not isinstance(candidates, list):
        return False, INVALID_FIELD, {}
    ids = list(dict.fromkeys(required + candidates))
    courses = [courseDataManager.FindCourse(database, courseId) for courseId in ids]
    if any(course is None for course in courses):
        return False, INVALID_FIELD, {}
    minCredits = preferences.get("min_credits", 9)
    maxCredits = preferences.get("max_credits", student.get("max_credits", 25))
    blocked = preferences.get("blocked_slots", [])

    def feasible(selected):
        selectedIds = [course["course_id"] for course in selected]
        if set(required).issubset(set(selectedIds)) is False:
            return False
        total = sum(course["credits"] for course in selected)
        if total < minCredits or total > maxCredits:
            return False
        if any(TimeSlotsOverlap(course["time_slots"], blocked) for course in selected):
            return False
        for index, course in enumerate(selected):
            if courseDataManager.RemainingSeats(course) <= 0:
                if course["course_id"] not in student["enrolled_courses"]:
                    return False
            for other in selected[index + 1:]:
                if TimeSlotsOverlap(course["time_slots"], other["time_slots"]):
                    return False
        return True

    bruteNodes = 0
    start = time.perf_counter()
    for size in range(len(courses) + 1):
        for selected in combinations(courses, size):
            bruteNodes += 1
            feasible(selected)
    bruteTime = max(time.perf_counter() - start, 0.000001)

    backNodes = 0
    start = time.perf_counter()
    def visit(index, selected):
        nonlocal backNodes
        backNodes += 1
        if index == len(courses):
            feasible(selected)
            return
        visit(index + 1, selected)
        visit(index + 1, selected + [courses[index]])
    visit(0, [])
    backTime = max(time.perf_counter() - start, 0.000001)

    metrics = {
        "brute_force": {"time_seconds": round(bruteTime, 9), "nodes_searched": bruteNodes},
        "backtracking": {"time_seconds": round(backTime, 9), "nodes_searched": backNodes},
        "winner": "backtracking" if backNodes < bruteNodes else "brute_force",
    }
    return True, OK, metrics
