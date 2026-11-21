"""F2 多層次衝堂與選課檢查模組 (Conflict Checker)。

本副程式負責驗證學生選課時的各項限制與衝堂條件：
- 學生課表時段衝堂
- 教室時段衝堂
- 校園活動時段衝突
- 學分上限檢查
- 課程剩餘人數限制

介面規範：
- 輸入參數皆有明確之型別與欄位規格。
- 回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

from Constants import (
    ACTIVITY_CONFLICT,
    COURSE_FULL,
    CREDIT_LIMIT_EXCEEDED,
    NOT_FOUND,
    OK,
    ROOM_CONFLICT,
    TIME_CONFLICT,
)
import CourseDataManager as courseDataManager
from TimeSlotUtils import TimeSlotsOverlap


def CheckTimeConflict(firstTimeSlots: list[dict], secondTimeSlots: list[dict]) -> tuple[bool, str, list[dict]]:
    """檢查兩個時段清單是否重疊。

    輸入：
        slots_a: 時段字典清單 [{"day": int, "period": str}, ...]
        slots_b: 時段字典清單 [{"day": int, "period": str}, ...]
    回傳：
        (ok, code, overlapping_slots)
        - 無衝堂：(True, OK, [])
        - 衝堂：(False, TIME_CONFLICT, [{"day": ..., "period": ...}, ...])
    """
    overlappingSlots = sorted(
        TimeSlotsOverlap(firstTimeSlots, secondTimeSlots),
        key=lambda timeSlot: (timeSlot.get("day", 0), timeSlot.get("period", "")),
    )
    if overlappingSlots:
        return False, TIME_CONFLICT, overlappingSlots
    return True, OK, []


def CheckClassroomConflict(database: dict, classroomId: str, timeSlots: list[dict],
                             excludeCourseId: str | None = None) -> tuple[bool, str]:
    """檢查指定教室在指定時段是否已被其他課程或活動佔用。

    輸入：
        db: 標準資料庫字典
        classroom_id: 教室代號
        time_slots: 欲排定之時段清單 [{"day": int, "period": str}, ...]
        exclude_course_id: 排除比對之課程代號（修改課程時可用）
    回傳：
        (ok, code):
        - 無衝突：(True, OK)
        - 衝堂：(False, ROOM_CONFLICT)
    """
    for course in database.get("courses", []):
        if course.get("course_id") == excludeCourseId:
            continue
        if course.get("classroom_id") == classroomId:
            if TimeSlotsOverlap(timeSlots, course.get("time_slots", [])):
                return False, ROOM_CONFLICT

    for activity in database.get("activities", []):
        if activity.get("classroom_id") == classroomId:
            if TimeSlotsOverlap(timeSlots, activity.get("time_slots", [])):
                return False, ROOM_CONFLICT

    return True, OK


def CheckEnrollmentConflicts(database: dict, studentId: str, courseId: str) -> tuple[bool, str, list[dict]]:
    """完整檢查學生加選指定課程的所有衝堂與限制（持續檢查不提早中斷）。

    輸入：
        db: 標準資料庫字典
        student_id: 欲加選之學號
        course_id: 欲加選之課程代號
    回傳：
        (ok, code, conflict_details)
        - 全無衝突：(True, OK, [])
        - 存在衝突：(False, 主要錯誤碼, [{"type": 衝突錯誤代碼, "detail": ...}, ...])
    """
    student = courseDataManager.FindStudent(database, studentId)
    if not student:
        return False, NOT_FOUND, [{"type": NOT_FOUND, "target": "student", "id": studentId}]

    course = courseDataManager.FindCourse(database, courseId)
    if not course:
        return False, NOT_FOUND, [{"type": NOT_FOUND, "target": "course", "id": courseId}]

    conflicts = []

    # 1. 人數上限檢查
    if courseDataManager.RemainingSeats(course) <= 0:
        conflicts.append({"type": COURSE_FULL, "course_id": courseId})

    # 2. 學分上限檢查
    currentCredits = sum(
        courseDataManager.FindCourse(database, courseId)["credits"]
        for courseId in student.get("enrolled_courses", [])
        if courseDataManager.FindCourse(database, courseId)
    )
    if currentCredits + course["credits"] > student["max_credits"]:
        conflicts.append({
            "type": CREDIT_LIMIT_EXCEEDED,
            "current_credits": currentCredits,
            "course_credits": course["credits"],
            "max_credits": student["max_credits"],
        })

    # 3. 學生已選課程時段衝堂
    courseSlots = course.get("time_slots", [])
    for enrolledCid in student.get("enrolled_courses", []):
        enrolledC = courseDataManager.FindCourse(database, enrolledCid)
        if not enrolledC:
            continue
        ok, _, overlappingSlots = CheckTimeConflict(courseSlots, enrolledC.get("time_slots", []))
        if not ok:
            isActivity = enrolledC.get("course_type") == "event"
            conflicts.append({
                "type": ACTIVITY_CONFLICT if isActivity else TIME_CONFLICT,
                "conflict_with_activity" if isActivity else "conflict_with_course": enrolledCid,
                "slots": overlappingSlots,
            })

    # 4. 學生已報名活動時間衝突
    enrolledActivities = student.get("enrolled_activities", [])
    for activity in database.get("activities", []):
        if activity.get("activity_id") in enrolledActivities:
            ok, _, overlappingSlots = CheckTimeConflict(courseSlots, activity.get("time_slots", []))
            if not ok:
                conflicts.append({
                    "type": ACTIVITY_CONFLICT,
                    "conflict_with_activity": activity["activity_id"],
                    "slots": overlappingSlots,
                })

    if conflicts:
        return False, conflicts[0]["type"], conflicts
    return True, OK, []
