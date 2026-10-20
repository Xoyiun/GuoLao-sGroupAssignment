"""F4 校園活動與教室配置模組 (Venue & Activity Manager)。

本副程式負責處理活動新增與場地自動媒合：
- 依設備、容量及時段篩選可用教室
- 新增活動並預約佔用教室時段

介面規範：
- 輸入參數皆有明確之型別與規格。
- 回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

import copy

from Constants import (
    CLASSROOM_NOT_FOUND,
    DUPLICATE_ID,
    INVALID_FIELD,
    NO_AVAILABLE_ROOM,
    OK,
)
import CourseDataManager as courseDataManager
from TimeSlotUtils import TimeSlotsOverlap


def FindAvailableClassrooms(database: dict, timeSlots: list[dict], minCapacity: int = 1,
                              requiredEquipment: list[str] | None = None) -> tuple[bool, str, list[dict]]:
    """篩選滿足容量、設備需求且在指定時段無衝突之可用教室。

    輸入：
        db: 標準資料庫字典
        time_slots: 欲佔用的時段清單 [{"day": int, "period": str}, ...]
        min_capacity: 最低容量需求（整數 >= 1）
        required_equipment: 必要設備清單（例如 ["projector"]）
    回傳：
        (ok, code, available_classrooms):
        - 成功：(True, OK, [classroom_dict, ...])
        - 無合適教室：(False, NO_AVAILABLE_ROOM, [])
    """
    ok, code = courseDataManager.ValidateTimeSlots(timeSlots)
    if not ok:
        return False, code, []

    requiredEquipment = set(requiredEquipment or [])
    occupiedRooms = set()

    for course in database.get("courses", []):
        if TimeSlotsOverlap(timeSlots, course.get("time_slots", [])):
            occupiedRooms.add(course.get("classroom_id"))

    for activity in database.get("activities", []):
        if TimeSlotsOverlap(timeSlots, activity.get("time_slots", [])):
            occupiedRooms.add(activity.get("classroom_id"))

    candidates = []
    for room in database.get("classrooms", []):
        if room["classroom_id"] in occupiedRooms:
            continue
        if room.get("capacity", 0) < minCapacity:
            continue
        classroomEquipment = set(room.get("equipment", []))
        if not requiredEquipment.issubset(classroomEquipment):
            continue
        candidates.append(room)

    if not candidates:
        return False, NO_AVAILABLE_ROOM, []
    return True, OK, candidates


def AddActivity(database: dict, activity: dict) -> tuple[bool, str]:
    """新增活動（自動驗證教室與時段衝突）。

    輸入：
        db: 標準資料庫字典
        activity: 活動字典，包含 activity_id, title, classroom_id, time_slots 等欄位
    回傳：
        (ok, code):
        - 成功：(True, OK)
        - 失敗：(False, 錯誤碼)
    """
    if not isinstance(activity, dict):
        return False, INVALID_FIELD
    activityId = activity.get("activity_id")
    if not activityId:
        return False, INVALID_FIELD
    if (
        courseDataManager.FindCourse(database, activityId) is not None
        or any(
            existingActivity.get("activity_id") == activityId
            for existingActivity in database.get("activities", [])
        )
    ):
        return False, DUPLICATE_ID

    classroomId = activity.get("classroom_id")
    room = courseDataManager.FindClassroom(database, classroomId)
    if not room:
        return False, CLASSROOM_NOT_FOUND

    slots = activity.get("time_slots", [])
    ok, code = courseDataManager.ValidateTimeSlots(slots)
    if not ok:
        return False, code

    okAvail, codeAvail, available = FindAvailableClassrooms(database, slots)
    if not okAvail or not any(classroom["classroom_id"] == classroomId for classroom in available):
        return False, NO_AVAILABLE_ROOM

    newCourse = {
        "course_id": activityId,
        "title": activity.get("title"),
        "credits": 0,
        "required": False,
        "teacher": activity.get("teacher", "NPC"),
        "classroom_id": classroomId,
        "capacity": activity.get("capacity", room["capacity"]),
        "time_slots": copy.deepcopy(slots),
        "enrolled_count": activity.get("enrolled_count", 0),
        "course_type": "event",
    }
    database.setdefault("courses", []).append(newCourse)
    return True, OK
