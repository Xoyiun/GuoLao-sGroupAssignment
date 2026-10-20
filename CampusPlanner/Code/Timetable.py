"""F3 個人課表產生與空閒時段查詢模組 (Timetable & Free Slots)。

本副程式負責處理個人課表之矩陣排程與連續空閒時段之計算：
- 學生每週 7x12 課表矩陣產生
- 連續空閒時段搜尋

介面規範：
- 輸入參數皆有明確之型別與規格。
- 回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

from Constants import NOT_FOUND, OK, VALID_DAYS, VALID_PERIODS
import CourseDataManager as courseDataManager
from TimeSlotUtils import GetWeekday


def GenerateWeeklyTimetable(database: dict, studentId: str) -> tuple[bool, str, dict]:
    """產生指定學生的每週 7x12 課表矩陣與統計資料。

    輸入：
        db: 標準資料庫字典
        student_id: 學號
    回傳：
        (ok, code, timetable_data):
        - 成功：(True, OK, {
            "student_id": str,
            "matrix": {day: {period: slot_dict_or_None}},
            "total_credits": int,
            "busy_slots": int,
            "free_slots": int
          })
        - 學生不存在：(False, NOT_FOUND, {})
    """
    student = courseDataManager.FindStudent(database, studentId)
    if not student:
        return False, NOT_FOUND, {}

    matrix = {day: {period: None for period in VALID_PERIODS} for day in VALID_DAYS}
    totalCredits = 0

    for courseId in student.get("enrolled_courses", []):
        course = courseDataManager.FindCourse(database, courseId)
        if not course:
            continue
        totalCredits += course.get("credits", 0)
        for slot in course.get("time_slots", []):
            day, period = GetWeekday(slot.get("day")), slot.get("period")
            if day in matrix and period in matrix[day]:
                slotType = "activity" if course.get("course_type") == "event" else "course"
                matrix[day][period] = {"type": slotType, "id": courseId, "title": course.get("title")}

    enrolledActs = set(student.get("enrolled_activities", []))
    for activity in database.get("activities", []):
        if activity.get("activity_id") in enrolledActs:
            for slot in activity.get("time_slots", []):
                day, period = GetWeekday(slot.get("day")), slot.get("period")
                if day in matrix and period in matrix[day]:
                    matrix[day][period] = {"type": "activity", "id": activity["activity_id"], "title": activity.get("title")}

    busyCount = sum(1 for day in matrix for period in matrix[day] if matrix[day][period] is not None)
    totalSlots = len(VALID_DAYS) * len(VALID_PERIODS)

    data = {
        "student_id": studentId,
        "matrix": matrix,
        "total_credits": totalCredits,
        "busy_slots": busyCount,
        "free_slots": totalSlots - busyCount,
    }
    return True, OK, data


def FindFreeTimeSlots(database: dict, studentId: str, targetDay: int | None = None,
                         minConsecutive: int = 1) -> tuple[bool, str, list[dict]]:
    """查詢學生在指定星期（或全週）內無課且無活動之連續空閒時段。

    輸入：
        db: 標準資料庫字典
        student_id: 學號
        target_day: 指定星期 (1-7)，None 代表不限星期
        min_consecutive: 至少連續的節數
    回傳：
        (ok, code, free_slots_list):
        - 成功：(True, OK, [{"day": int, "periods": list[str], "length": int}, ...])
        - 失敗：(False, 錯誤碼, [])
    """
    ok, code, data = GenerateWeeklyTimetable(database, studentId)
    if not ok:
        return False, code, []

    matrix = data["matrix"]
    targetDays = [targetDay] if targetDay in VALID_DAYS else list(VALID_DAYS)
    freeBlocks = []

    for day in targetDays:
        currentBlock = []
        for period in VALID_PERIODS:
            if matrix[day][period] is None:
                currentBlock.append(period)
            else:
                if len(currentBlock) >= minConsecutive:
                    freeBlocks.append({"day": day, "periods": list(currentBlock), "length": len(currentBlock)})
                currentBlock = []
        if len(currentBlock) >= minConsecutive:
            freeBlocks.append({"day": day, "periods": list(currentBlock), "length": len(currentBlock)})

    return True, OK, freeBlocks
