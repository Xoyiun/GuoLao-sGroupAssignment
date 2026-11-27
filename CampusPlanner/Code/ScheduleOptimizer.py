"""F7 多條件最佳課表搜尋模組 (Schedule Optimizer)。

本副程式負責依學生必修課、候選選修課與偏好搜尋排課組合：
- 搜尋滿足學分上下限與零衝堂之課表組合

介面規範：
- 輸入參數皆有明確之型別與規格。
- 回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

from Constants import INVALID_FIELD, NO_FEASIBLE_SCHEDULE, OK
import CourseDataManager as courseDataManager
from ConflictChecker import CheckEnrollmentConflicts
from TimeSlotUtils import GetWeekday, TimeSlotsOverlap


def CalculateScheduleMetrics(planCourses, enrolledCourses=(), preferredCourses=()):
    """計算一個方案的偏好指標。"""
    occupied = {}
    for course in list(planCourses) + list(enrolledCourses):
        for slot in course.get("time_slots", []):
            occupied.setdefault(GetWeekday(slot["day"]), set()).add(slot["period"])

    periods = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c")
    gapPeriods = 0
    earlyPeriods = 0
    halfDayBlocks = 0
    for dayPeriods in occupied.values():
        indexes = sorted(periods.index(period) for period in dayPeriods)
        gapPeriods += (indexes[-1] - indexes[0] + 1) - len(indexes)
        if "1" in dayPeriods:
            earlyPeriods += 1
        if dayPeriods & {"1", "2", "3", "4"}:
            halfDayBlocks += 1
        if dayPeriods & {"5", "6", "7", "8", "9"}:
            halfDayBlocks += 1
        if dayPeriods & {"a", "b", "c"}:
            halfDayBlocks += 1

    planIds = {course["course_id"] for course in planCourses}
    preferred = list(preferredCourses)
    if preferred:
        preferredRatio = sum(1 for courseId in preferred if courseId in planIds) / len(preferred)
    else:
        preferredRatio = 0

    return {
        "credits": sum(course["credits"] for course in planCourses),
        "campus_days": len(occupied),
        "gap_periods": gapPeriods,
        "early_periods": earlyPeriods,
        "half_day_blocks": halfDayBlocks,
        "preferred_ratio": preferredRatio,
    }


def SearchOptimalSchedules(database: dict, studentId: str, preferences: dict) -> tuple[bool, str, list[dict]]:
    """依偏好條件搜尋最佳可行課表組合。

    輸入：
        db: 標準資料庫字典
        student_id: 學號
        preferences: 偏好字典：
            - min_credits: int (最低學分)
            - max_credits: int (最高學分)
            - required_courses: list[str] (指定必排課程清單)
            - candidate_courses: list[str] (候選選修課程清單)
    回傳：
        (ok, code, schedule_plans):
        - 成功：(True, OK, [{"courses": [cid, ...], "total_credits": int, "score": float}, ...])
        - 無可行課表：(False, NO_FEASIBLE_SCHEDULE, [])
    """
    if not isinstance(preferences, dict):
        return False, INVALID_FIELD, []

    student = courseDataManager.FindStudent(database, studentId)
    if not student:
        return False, INVALID_FIELD, []

    minCredits = preferences.get("min_credits", 9)
    maxCredits = preferences.get("max_credits", student.get("max_credits", 25))
    required = preferences.get("required_courses", [])

    candidateIds = preferences.get("candidate_courses", [])
    blocked = preferences.get("blocked_slots", [])
    if not isinstance(required, list) or not isinstance(candidateIds, list):
        return False, INVALID_FIELD, []
    if not isinstance(minCredits, int) or isinstance(minCredits, bool) or minCredits < 0:
        return False, INVALID_FIELD, []
    if not isinstance(maxCredits, int) or isinstance(maxCredits, bool) or maxCredits < 0:
        return False, INVALID_FIELD, []

    requiredCourses = [courseDataManager.FindCourse(database, courseId) for courseId in required]
    if any(course is None for course in requiredCourses):
        return False, INVALID_FIELD, []
    candidateCourses = []
    for courseId in candidateIds:
        course = courseDataManager.FindCourse(database, courseId)
        if course is not None:
            candidateCourses.append(course)

    plans = []
    deduplicated = []
    seen = set(required)
    for course in candidateCourses:
        if course["course_id"] not in seen:
            seen.add(course["course_id"])
            deduplicated.append(course)
    candidateCourses = deduplicated
    for mask in range(1 << len(candidateCourses)):
        selected = list(requiredCourses)
        selected.extend(
            candidateCourses[index]
            for index in range(len(candidateCourses))
            if mask & (1 << index)
        )
        ids = [course["course_id"] for course in selected]
        if len(set(ids)) != len(ids):
            continue
        total = sum(course["credits"] for course in selected)
        if total < minCredits or total > maxCredits:
            continue
        if any(TimeSlotsOverlap(course.get("time_slots", []), blocked) for course in selected):
            continue
        if any(courseDataManager.RemainingSeats(course) <= 0 for course in selected
               if course["course_id"] not in student.get("enrolled_courses", [])):
            continue
        conflict = False
        enrolledCourses = [
            courseDataManager.FindCourse(database, courseId)
            for courseId in student.get("enrolled_courses", [])
        ]
        for selectedCourse in selected:
            for enrolledCourse in enrolledCourses:
                if enrolledCourse is not None and TimeSlotsOverlap(
                    selectedCourse.get("time_slots", []),
                    enrolledCourse.get("time_slots", []),
                ):
                    conflict = True
                    break
        for index, first in enumerate(selected):
            for second in selected[index + 1:]:
                if TimeSlotsOverlap(first.get("time_slots", []), second.get("time_slots", [])):
                    conflict = True
                    break
            if conflict:
                break
        if conflict:
            continue
        plans.append({
            "courses": ids,
            "total_credits": total,
            "score": float(total),
        })
    if not plans:
        return False, NO_FEASIBLE_SCHEDULE, []
    plans.sort(key=lambda plan: (-plan["score"], plan["courses"]))
    return True, OK, plans
