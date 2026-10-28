"""F2 多層次衝堂與選課檢查模組 (Conflict Checker)。

本副程式負責驗證學生選課時的各項限制與衝堂條件：
- 學生課表時段衝堂
- 教室時段衝堂
- 校園活動時段衝突（活動以 event 課程存放，學生報名的活動也在 enrolled_courses 中）
- 學分上限檢查
- 課程剩餘人數限制

介面規範：
- 輸入參數皆有明確之型別與欄位規格。
- 回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

from Constants import (
    ACTIVITY_CONFLICT,
    ALREADY_ENROLLED,
    COURSE_FULL,
    CREDIT_LIMIT_EXCEEDED,
    NOT_FOUND,
    OK,
    ROOM_CONFLICT,
    TIME_CONFLICT,
    VALID_PERIODS,
)
import CourseDataManager as courseDataManager
from TimeSlotUtils import GetWeekday, TimeSlotsOverlap


def SlotSortKey(timeSlot: dict) -> tuple[int, int]:
    """依星期、節次排序用；活動的日期時段換算成星期，節次依 1–9、a、b、c 的順序。"""
    period = timeSlot.get("period")
    periodOrder = VALID_PERIODS.index(period) if period in VALID_PERIODS else len(VALID_PERIODS)
    return GetWeekday(timeSlot.get("day", 0)), periodOrder


def CheckTimeConflict(firstTimeSlots: list[dict], secondTimeSlots: list[dict]) -> tuple[bool, str, list[dict]]:
    """檢查兩個時段清單是否重疊。

    輸入：
        firstTimeSlots: 時段字典清單 [{"day": int, "period": str}, ...]
        secondTimeSlots: 時段字典清單 [{"day": int, "period": str}, ...]
    回傳：
        (ok, code, overlappingSlots)
        - 無衝堂：(True, OK, [])
        - 衝堂：(False, TIME_CONFLICT, [{"day": ..., "period": ...}, ...])，依星期、節次排序
    """
    overlappingSlots = sorted(TimeSlotsOverlap(firstTimeSlots, secondTimeSlots), key=SlotSortKey)
    if overlappingSlots:
        return False, TIME_CONFLICT, overlappingSlots
    return True, OK, []


def FindClassroomConflicts(database: dict, classroomId: str, timeSlots: list[dict],
                           excludeCourseId: str | None = None) -> list[tuple[str, list[dict]]]:
    """列出在指定教室、指定時段已排定的所有課程與活動。

    回傳：[(課程代號, 重疊時段清單), ...]；沒有衝突時為空清單。
    """
    conflicts = []
    for course in database.get("courses", []):
        if course.get("course_id") == excludeCourseId or course.get("classroom_id") != classroomId:
            continue
        ok, _, overlappingSlots = CheckTimeConflict(timeSlots, course.get("time_slots", []))
        if not ok:
            conflicts.append((course["course_id"], overlappingSlots))
    return conflicts


def CheckClassroomConflict(database: dict, classroomId: str, timeSlots: list[dict],
                           excludeCourseId: str | None = None) -> tuple[bool, str]:
    """檢查指定教室在指定時段是否已被其他課程或活動佔用。

    輸入：
        database: 標準資料庫字典
        classroomId: 教室代號
        timeSlots: 欲排定之時段清單 [{"day": int, "period": str}, ...]
        excludeCourseId: 排除比對之課程代號（修改課程時可用）
    回傳：
        (ok, code):
        - 無衝突：(True, OK)
        - 衝堂：(False, ROOM_CONFLICT)
    """
    if FindClassroomConflicts(database, classroomId, timeSlots, excludeCourseId):
        return False, ROOM_CONFLICT
    return True, OK


def CheckEnrollmentConflicts(database: dict, studentId: str, courseId: str) -> tuple[bool, str, list[dict]]:
    """完整檢查學生加選指定課程的所有衝堂與限制（全部檢查完才回傳，不會遇到第一個錯誤就停）。

    輸入：
        database: 標準資料庫字典
        studentId: 欲加選之學號
        courseId: 欲加選之課程代號
    回傳：
        (ok, code, conflicts)
        - 全無衝突：(True, OK, [])
        - 學生或課程不存在：(False, NOT_FOUND, [...])
        - 已經選過這門課：(False, ALREADY_ENROLLED, [...])
        - 存在衝突：(False, 第一項衝突的錯誤碼, [{"type": 錯誤碼, ...}, ...])
          時段相關衝突（學生衝堂、活動衝突、教室衝堂）在前，依星期、節次排序；
          名額與學分限制排在最後。
    """
    student = courseDataManager.FindStudent(database, studentId)
    if not student:
        return False, NOT_FOUND, [{"type": NOT_FOUND, "target": "student", "id": studentId}]

    course = courseDataManager.FindCourse(database, courseId)
    if not course:
        return False, NOT_FOUND, [{"type": NOT_FOUND, "target": "course", "id": courseId}]

    enrolledCourses = [
        enrolledCourse
        for enrolledCourse in (
            courseDataManager.FindCourse(database, enrolledId)
            for enrolledId in student.get("enrolled_courses", [])
        )
        if enrolledCourse
    ]
    if any(enrolledCourse["course_id"] == courseId for enrolledCourse in enrolledCourses):
        return False, ALREADY_ENROLLED, [{"type": ALREADY_ENROLLED, "course_id": courseId}]

    courseSlots = course.get("time_slots", [])
    slotConflicts = []

    # 1. 學生已選課程與已報名活動的時段衝突
    for enrolledCourse in enrolledCourses:
        ok, _, overlappingSlots = CheckTimeConflict(courseSlots, enrolledCourse.get("time_slots", []))
        if not ok:
            isActivity = enrolledCourse.get("course_type") == "event"
            slotConflicts.append({
                "type": ACTIVITY_CONFLICT if isActivity else TIME_CONFLICT,
                "conflict_with_activity" if isActivity else "conflict_with_course": enrolledCourse["course_id"],
                "slots": overlappingSlots,
            })

    # 2. 這門課的教室在同時段被其他課程或活動佔用
    for otherCourseId, overlappingSlots in FindClassroomConflicts(
        database, course.get("classroom_id"), courseSlots, excludeCourseId=courseId
    ):
        slotConflicts.append({
            "type": ROOM_CONFLICT,
            "classroom_id": course.get("classroom_id"),
            "conflict_with_course": otherCourseId,
            "slots": overlappingSlots,
        })

    slotConflicts.sort(key=lambda conflict: SlotSortKey(conflict["slots"][0]))
    limitConflicts = []

    # 3. 人數上限
    if courseDataManager.RemainingSeats(course) <= 0:
        limitConflicts.append({"type": COURSE_FULL, "course_id": courseId})

    # 4. 學分上限
    currentCredits = sum(enrolledCourse["credits"] for enrolledCourse in enrolledCourses)
    if currentCredits + course["credits"] > student["max_credits"]:
        limitConflicts.append({
            "type": CREDIT_LIMIT_EXCEEDED,
            "current_credits": currentCredits,
            "course_credits": course["credits"],
            "max_credits": student["max_credits"],
        })

    conflicts = slotConflicts + limitConflicts
    if conflicts:
        return False, conflicts[0]["type"], conflicts
    return True, OK, []
