"""F5 多條件課程篩選與可行性檢查模組 (Course Filter)。

本副程式負責依學生多維度條件進行課程過濾與可行性判定：
- 排除禁止時段
- 偏好星期篩選
- 必修課程衝突檢查

介面規範：
- 輸入參數皆有明確之型別與規格。
- 回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

from Constants import CONFLICTING_CRITERIA, INVALID_FIELD, MIN_CREDITS_UNMET, OK
import CourseDataManager as courseDataManager
from TimeSlotUtils import GetWeekday, TimeSlotsOverlap


def FilterCourses(database: dict, criteria: dict) -> tuple[bool, str, list[dict]]:
    """依多條件篩選候選課程。

    輸入：
        db: 標準資料庫字典
        criteria: 篩選條件字典：
            - required_ids: list[str] (指定/必選修課程代號清單)
            - blocked_slots: list[dict] (禁止上課時段清單 [{"day": int, "period": str}, ...])
            - preferred_days: list[int] (偏好的星期清單 [1, 3, 5])
            - has_seats: bool (是否僅保留有剩餘名額之課程)
    回傳：
        (ok, code, candidate_courses):
        - 成功：(True, OK, [course_dict, ...])
        - 條件矛盾（例如必修排在禁止時段）：(False, CONFLICTING_CRITERIA, [])
    """
    if not isinstance(criteria, dict):
        return False, INVALID_FIELD, []

    requiredIds = criteria.get("required_ids", [])
    if not isinstance(requiredIds, list) or not all(isinstance(item, str) for item in requiredIds):
        return False, INVALID_FIELD, []
    requiredIds = set(requiredIds)
    blocked = criteria.get("blocked_slots", [])
    preferredDays = set(criteria.get("preferred_days", []))
    hasSeats = criteria.get("has_seats")

    if not isinstance(blocked, list):
        return False, INVALID_FIELD, []
    ok, _ = courseDataManager.ValidateTimeSlots(blocked) if blocked else (True, OK)
    if not ok:
        return False, INVALID_FIELD, []
    if preferredDays and not preferredDays.issubset(set(range(1, 8))):
        return False, INVALID_FIELD, []
    if hasSeats not in (None, True, False):
        return False, INVALID_FIELD, []

    # 驗證必修課程是否落入不可上課時段
    for courseId in requiredIds:
        course = courseDataManager.FindCourse(database, courseId)
        if not course:
            continue
        if TimeSlotsOverlap(course.get("time_slots", []), blocked):
            return False, CONFLICTING_CRITERIA, []

    candidates = []
    requiredCreditIds = set(requiredIds)
    minCredits = criteria.get("min_credits")
    if minCredits is not None and (not isinstance(minCredits, int) or isinstance(minCredits, bool) or minCredits < 0):
        return False, INVALID_FIELD, []
    availableCreditIds = set()
    for course in database.get("courses", []):
        courseSlots = course.get("time_slots", [])
        if TimeSlotsOverlap(courseSlots, blocked):
            continue
        if preferredDays and not any(
            GetWeekday(timeSlot["day"]) in preferredDays for timeSlot in courseSlots
        ):
            continue
        if hasSeats is True and courseDataManager.RemainingSeats(course) <= 0:
            continue
        candidates.append(course)
        if course["course_id"] in requiredCreditIds:
            availableCreditIds.add(course["course_id"])

    if requiredCreditIds - availableCreditIds:
        return False, CONFLICTING_CRITERIA, []
    if minCredits is not None:
        requiredCredits = sum(
            course["credits"] for course in candidates
            if course["course_id"] in requiredCreditIds
        )
        availableCredits = sum(course["credits"] for course in candidates)
        if requiredCredits < minCredits and availableCredits < minCredits:
            return False, MIN_CREDITS_UNMET, []

    return True, OK, candidates
