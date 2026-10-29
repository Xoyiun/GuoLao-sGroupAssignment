"""F10 動態事件與課表重新規劃模組 (Dynamic Replanner)。

本副程式負責處理停課或活動異動時之最小異動排課：
- 停課時自動篩選相同學分之可用替代課程

介面規範：
- 輸入參數皆有明確之型別與規格。
- 回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

from Constants import COURSE_NOT_FOUND, OK, REPLAN_FAILED
import CourseDataManager as courseDataManager


def ReplanOnCourseCancellation(database: dict, studentId: str, canceledCourseId: str) -> tuple[bool, str, dict]:
    """針對課程停開進行最小異動替代排課。

    輸入：
        db: 標準資料庫字典
        student_id: 學號
        canceled_course_id: 停開的課程代號
    回傳：
        (ok, code, plan):
        - 成功：(True, OK, {
            "student_id": str,
            "removed_course": str,
            "replacement_courses": list[str],
            "net_credits_diff": int
          })
        - 課程不存在：(False, COURSE_NOT_FOUND, {})
        - 無合適替代：(False, REPLAN_FAILED, {})
    """
    course = courseDataManager.FindCourse(database, canceledCourseId)
    if not course:
        return False, COURSE_NOT_FOUND, {}

    student = courseDataManager.FindStudent(database, studentId)
    if not student:
        return False, COURSE_NOT_FOUND, {}

    creditsNeeded = course.get("credits", 0)

    candidates = [
        course["course_id"]
        for course in database.get("courses", [])
        if course["course_id"] != canceledCourseId
        and course["course_id"] not in student.get("enrolled_courses", [])
        and course.get("credits") == creditsNeeded
        and courseDataManager.RemainingSeats(course) > 0
    ]

    return True, OK, {
        "student_id": studentId,
        "removed_course": canceledCourseId,
        "replacement_courses": candidates[:3],
        "net_credits_diff": 0 if candidates else -creditsNeeded,
    }
