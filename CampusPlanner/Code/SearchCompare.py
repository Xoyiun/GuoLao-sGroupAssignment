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
import ScheduleOptimizer as scheduleOptimizer
from TimeSlotUtils import TimeSlotsOverlap


def SolutionKey(selected):
    """可行解的表示法：排序後的課程代號，方便兩種演算法比較是否一致。"""
    return tuple(sorted(course["course_id"] for course in selected))


def BruteForceSearch(problem):
    """窮舉法：逐一檢查候選課程的全部 2ⁿ 個子集合（每個子集合算一個節點）。

    輸入：ScheduleOptimizer.BuildSearchProblem 產生的 problem
    回傳：{"solutions": [排序後的可行解], "nodes": int, "seconds": float, "completed": bool}
    """
    start = time.perf_counter()
    candidates = problem["candidates"]
    solutions = []
    nodes = 0
    for mask in range(1 << len(candidates)):
        nodes += 1
        selected = problem["required"] + [
            candidates[index] for index in range(len(candidates)) if mask & (1 << index)
        ]
        if scheduleOptimizer.IsFeasibleSelection(problem, selected):
            solutions.append(SolutionKey(selected))
    return {
        "solutions": sorted(solutions),
        "nodes": nodes,
        "seconds": time.perf_counter() - start,
        "completed": True,
    }


def SuffixCredits(candidates):
    """suffix[i] = 第 i 門之後（含）所有候選的學分總和，用來估計「最多還能拿到幾學分」。"""
    suffix = [0] * (len(candidates) + 1)
    for index in range(len(candidates) - 1, -1, -1):
        suffix[index] = suffix[index + 1] + candidates[index]["credits"]
    return suffix


def CanAddCourse(problem, selected, credits, course):
    """把 course 加入目前選法後，是否仍符合可在搜尋途中檢查的條件 C1～C4（見演算法說明第三節）。"""
    if credits + course["credits"] > problem["max_credits"]:                      # C1 學分上限
        return False
    if TimeSlotsOverlap(course.get("time_slots", []), problem["blocked"]):        # C3 禁止時段
        return False
    if courseDataManager.RemainingSeats(course) <= 0:                             # C4 額滿
        return False
    return not any(                                                               # C2 衝堂
        TimeSlotsOverlap(course.get("time_slots", []), other.get("time_slots", []))
        for other in selected + problem["enrolled"]
    )


def BacktrackingSearch(problem):
    """回溯法：依序決定每門候選「不選／選」，違反條件的分支提早放棄（每次走訪算一個節點）。

    剪枝：加入後違反 C1～C4 就不往下走；目前學分加上剩餘候選的學分仍達不到最低學分，也停止。
    回傳格式與 BruteForceSearch 相同。
    """
    start = time.perf_counter()
    candidates = problem["candidates"]
    suffix = SuffixCredits(candidates)
    solutions = []
    nodes = 0

    def Visit(index, selected, credits):
        nonlocal nodes
        nodes += 1
        if credits + suffix[index] < problem["min_credits"]:                      # C5 剪枝
            return
        if index == len(candidates):
            if scheduleOptimizer.IsFeasibleSelection(problem, selected):            # 再用 F7 的完整條件確認
                solutions.append(SolutionKey(selected))
            return
        Visit(index + 1, selected, credits)                                       # 不選第 index 門
        course = candidates[index]
        if CanAddCourse(problem, selected, credits, course):
            Visit(index + 1, selected + [course], credits + course["credits"])    # 選第 index 門

    # 必修課先逐一加入；必修課本身就違反條件時沒有任何可行解
    required, requiredCredits = [], 0
    for course in problem["required"]:
        if not CanAddCourse(problem, required, requiredCredits, course):
            break
        required.append(course)
        requiredCredits += course["credits"]
    else:
        Visit(0, required, requiredCredits)
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
