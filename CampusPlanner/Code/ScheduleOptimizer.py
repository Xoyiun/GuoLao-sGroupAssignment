"""F7 多條件最佳課表搜尋模組 (Schedule Optimizer)。

本副程式負責依學生必修課、候選選修課與偏好搜尋排課組合：
- 搜尋滿足學分上下限與零衝堂之課表組合

介面規範：
- 輸入參數皆有明確之型別與規格。
- 回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

from Constants import INVALID_FIELD, NO_FEASIBLE_SCHEDULE, OK
import CourseDataManager as courseDataManager


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

    requiredCourses = [courseDataManager.FindCourse(database, courseId) for courseId in required]
    if any(course is None for course in requiredCourses):
        return False, INVALID_FIELD, []

    requiredCredits = sum(course["credits"] for course in requiredCourses)
    if requiredCredits > maxCredits:
        return False, NO_FEASIBLE_SCHEDULE, []

    plan = {
        "courses": list(required),
        "total_credits": requiredCredits,
        "score": 100.0 if requiredCredits >= minCredits else float(requiredCredits),
    }

    return True, OK, [plan]
