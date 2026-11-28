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


def BruteForceSearch(problem, timeLimit=None):
    """窮舉法：逐一檢查候選課程的全部 2ⁿ 個子集合（每個子集合算一個節點）。

    輸入：ScheduleOptimizer.BuildSearchProblem 產生的 problem
    回傳：{"solutions": [排序後的可行解], "nodes": int, "seconds": float, "completed": bool}
    """
    start = time.perf_counter()
    candidates = problem["candidates"]
    solutions = []
    nodes = 0
    completed = True
    for mask in range(1 << len(candidates)):
        if timeLimit is not None and time.perf_counter() - start >= timeLimit:
            completed = False
            break
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
        "completed": completed,
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


def BacktrackingSearch(problem, timeLimit=None):
    """回溯法：依序決定每門候選「不選／選」，違反條件的分支提早放棄（每次走訪算一個節點）。

    剪枝：加入後違反 C1～C4 就不往下走；目前學分加上剩餘候選的學分仍達不到最低學分，也停止。
    回傳格式與 BruteForceSearch 相同。
    """
    start = time.perf_counter()
    candidates = problem["candidates"]
    suffix = SuffixCredits(candidates)
    solutions = []
    nodes = 0
    completed = True

    def Visit(index, selected, credits):
        nonlocal nodes, completed
        if not completed:
            return
        if timeLimit is not None and time.perf_counter() - start >= timeLimit:
            completed = False
            return
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
        "completed": completed,
    }


def CompareAlgorithms(database, studentId, preferences, timeLimit=None):
    ok, code, problem = scheduleOptimizer.BuildSearchProblem(database, studentId, preferences)
    if not ok:
        return False, code, {}
    report = {"candidate_count": len(problem["candidates"])}
    results = {}
    for name, search in (("brute_force", BruteForceSearch), ("backtracking", BacktrackingSearch)):
        result = search(problem, timeLimit)
        results[name] = result
        report[name] = {
            "nodes": result["nodes"],
            "seconds": result["seconds"],
            "solutions": len(result["solutions"]),
            "completed": result["completed"],
        }
    if results["brute_force"]["completed"] and results["backtracking"]["completed"]:
        report["consistent"] = results["brute_force"]["solutions"] == results["backtracking"]["solutions"]
    else:
        report["consistent"] = None
    return True, OK, report
