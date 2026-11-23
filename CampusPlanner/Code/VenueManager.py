"""F4 校園活動與教室配置模組 (Venue & Activity Manager)。

本副程式負責處理活動新增與場地自動媒合：
- 依設備、容量及時段篩選可用教室
- 新增活動並預約佔用教室時段

介面規範：
- 輸入參數皆有明確之型別與規格。
- 回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

import copy
from datetime import datetime, time as datetimeTime

from Constants import (
    CAPACITY_EXCEEDS_ROOM,
    CLASSROOM_NOT_FOUND,
    DUPLICATE_ID,
    INVALID_CAPACITY,
    INVALID_FIELD,
    NO_AVAILABLE_ROOM,
    OK,
    ROOM_CONFLICT,
)
import CourseDataManager as courseDataManager
from TimeSlotUtils import TimeSlotsOverlap
from Constants import ACTIVITY_NOT_FOUND, INVALID_TIME_SLOTS
from TimeSlotUtils import LOCAL_TIME_ZONE


PERIOD_TIMES = (
    ("1", datetimeTime(8, 10), datetimeTime(9, 0)),
    ("2", datetimeTime(9, 10), datetimeTime(10, 0)),
    ("3", datetimeTime(10, 10), datetimeTime(11, 0)),
    ("4", datetimeTime(11, 10), datetimeTime(12, 0)),
    ("5", datetimeTime(13, 10), datetimeTime(14, 0)),
    ("6", datetimeTime(14, 10), datetimeTime(15, 0)),
    ("7", datetimeTime(15, 10), datetimeTime(16, 0)),
    ("8", datetimeTime(16, 10), datetimeTime(17, 0)),
    ("9", datetimeTime(17, 10), datetimeTime(18, 0)),
    ("a", datetimeTime(18, 30), datetimeTime(19, 20)),
    ("b", datetimeTime(19, 25), datetimeTime(20, 15)),
    ("c", datetimeTime(20, 20), datetimeTime(21, 10)),
)


def TimeRangeToSlots(dateTimestamp: int, startTime: str, endTime: str) -> tuple[bool, str, list[dict]]:
    """Convert a Taipei-local date and clock range to the system's period slots."""
    try:
        if not isinstance(dateTimestamp, int) or isinstance(dateTimestamp, bool):
            raise ValueError
        date = datetime.fromtimestamp(dateTimestamp, LOCAL_TIME_ZONE)
        start = datetime.strptime(startTime, "%H:%M").time()
        end = datetime.strptime(endTime, "%H:%M").time()
    except (TypeError, ValueError, OSError, OverflowError):
        return False, INVALID_TIME_SLOTS, []
    if start >= end:
        return False, INVALID_TIME_SLOTS, []

    midnight = datetime(date.year, date.month, date.day, tzinfo=LOCAL_TIME_ZONE)
    dayTimestamp = int(midnight.timestamp())
    slots = [
        {"day": dayTimestamp, "period": period}
        for period, periodStart, periodEnd in PERIOD_TIMES
        if start < periodEnd and end > periodStart
    ]
    if not slots:
        return False, INVALID_TIME_SLOTS, []
    return True, OK, slots


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

    if not courseDataManager.IsInteger(minCapacity) or minCapacity < 1:
        return False, INVALID_CAPACITY, []
    if requiredEquipment is None:
        requiredEquipment = []
    if not isinstance(requiredEquipment, list) or not all(
        isinstance(item, str) and item.strip() for item in requiredEquipment
    ):
        return False, INVALID_FIELD, []

    requiredEquipment = set(requiredEquipment)
    occupiedRooms = set()

    for course in database.get("courses", []):  # 活動以 event 課程存放，一併計入
        if TimeSlotsOverlap(timeSlots, course.get("time_slots", [])):
            occupiedRooms.add(course.get("classroom_id"))

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
    candidates.sort(key=lambda room: (room.get("capacity", 0), room.get("classroom_id", "")))
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
    title = activity.get("title")
    if not courseDataManager.IsNonemptyString(activityId) or not courseDataManager.IsNonemptyString(title):
        return False, INVALID_FIELD
    if courseDataManager.FindCourse(database, activityId) is not None:
        return False, DUPLICATE_ID

    classroomId = activity.get("classroom_id")
    room = courseDataManager.FindClassroom(database, classroomId) if classroomId else None
    if classroomId and not room:
        return False, CLASSROOM_NOT_FOUND

    capacity = activity.get("capacity")
    if capacity is None:
        capacity = room["capacity"] if room else 1
    if not courseDataManager.IsInteger(capacity) or capacity < 1:
        return False, INVALID_CAPACITY
    if room is not None and capacity > room["capacity"]:
        return False, CAPACITY_EXCEEDS_ROOM

    requiredEquipment = activity.get("required_equipment", [])
    if not isinstance(requiredEquipment, list) or not all(
        isinstance(item, str) and item.strip() for item in requiredEquipment
    ):
        return False, INVALID_FIELD
    if room is not None and not set(requiredEquipment).issubset(set(room.get("equipment", []))):
        return False, NO_AVAILABLE_ROOM

    slots = activity.get("time_slots", [])
    ok, code = courseDataManager.ValidateTimeSlots(slots)
    if not ok:
        return False, code

    okAvail, codeAvail, available = FindAvailableClassrooms(
        database, slots, minCapacity=capacity, requiredEquipment=requiredEquipment
    )
    if not okAvail:
        occupied = any(
            course.get("classroom_id") == classroomId
            and TimeSlotsOverlap(slots, course.get("time_slots", []))
            for course in database.get("courses", [])
        ) if classroomId else False
        return False, ROOM_CONFLICT if occupied else codeAvail

    if classroomId is None:
        classroomId = available[0]["classroom_id"]
    elif not any(classroom["classroom_id"] == classroomId for classroom in available):
        occupied = any(
            course.get("classroom_id") == classroomId
            and TimeSlotsOverlap(slots, course.get("time_slots", []))
            for course in database.get("courses", [])
        )
        return False, ROOM_CONFLICT if occupied else NO_AVAILABLE_ROOM

    newCourse = {
        "course_id": activityId,
        "title": title,
        "credits": 0,
        "required": False,
        "teacher": activity.get("teacher", "NPC"),
        "classroom_id": classroomId,
        "capacity": capacity,
        "time_slots": copy.deepcopy(slots),
        "enrolled_count": activity.get("enrolled_count", 0),
        "course_type": "event",
        "activity_type": activity.get("activity_type", ""),
        "required_equipment": copy.deepcopy(requiredEquipment),
    }
    database.setdefault("courses", []).append(newCourse)
    return True, OK


def ExplainUnavailable(database: dict, timeSlots: list[dict], minCapacity: int,
                       requiredEquipment: list[str]) -> list[dict]:
    """Return concrete reasons when no classroom satisfies all activity requirements."""
    reasons = []
    capacityRooms = [
        room for room in database.get("classrooms", [])
        if room.get("capacity", 0) >= minCapacity
    ]
    if not capacityRooms:
        reasons.append({
            "reason": "INSUFFICIENT_CAPACITY",
            "required_capacity": minCapacity,
            "candidates": [],
        })

    equipmentRooms = [
        room for room in capacityRooms
        if set(requiredEquipment).issubset(set(room.get("equipment", [])))
    ]
    missingEquipment = [
        item for item in requiredEquipment
        if not any(item in room.get("equipment", []) for room in capacityRooms)
    ]
    if missingEquipment:
        reasons.append({
            "reason": "MISSING_EQUIPMENT",
            "equipment": missingEquipment,
            "candidates": [room["classroom_id"] for room in capacityRooms],
        })

    occupiedIds = []
    for room in equipmentRooms:
        occupied = any(
            course.get("classroom_id") == room["classroom_id"]
            and TimeSlotsOverlap(timeSlots, course.get("time_slots", []))
            for course in database.get("courses", [])
        )
        if occupied:
            occupiedIds.append(room["classroom_id"])
    if occupiedIds:
        reasons.append({
            "reason": "ROOM_CONFLICT",
            "room_ids": occupiedIds,
            "time_slots": copy.deepcopy(timeSlots),
        })
    if not reasons:
        reasons.append({"reason": "NO_AVAILABLE_ROOM", "candidates": []})
    return reasons


def QueryActivities(database: dict, activityId=None, date=None, activityType=None,
                    hasSeats=None) -> list[dict]:
    """Filter stored event courses with AND semantics."""
    results = []
    for course in database.get("courses", []):
        if course.get("course_type") != "event":
            continue
        if activityId is not None and course["course_id"] != activityId:
            continue
        if activityType is not None and course.get("activity_type") != activityType:
            continue
        if date is not None and not any(slot["day"] == date for slot in course.get("time_slots", [])):
            continue
        if hasSeats is True and courseDataManager.RemainingSeats(course) <= 0:
            continue
        if hasSeats is False and courseDataManager.RemainingSeats(course) > 0:
            continue
        results.append(course)
    return results


def UpdateActivity(database: dict, activityId: str, changes: dict) -> tuple[bool, str]:
    """Update an event atomically, including automatic room replanning if needed."""
    activity = courseDataManager.FindCourse(database, activityId)
    if activity is None or activity.get("course_type") != "event":
        return False, ACTIVITY_NOT_FOUND
    if not isinstance(changes, dict):
        return False, INVALID_FIELD

    updated = copy.deepcopy(activity)
    for field in ("title", "capacity", "classroom_id", "time_slots",
                  "activity_type", "required_equipment", "teacher"):
        if field in changes:
            updated[field] = copy.deepcopy(changes[field])
    updated["activity_id"] = activityId

    if updated["capacity"] < updated.get("enrolled_count", 0):
        return False, INVALID_CAPACITY

    ok, code = AddActivity(
        {
            "classrooms": database["classrooms"],
            "courses": [
                course for course in database["courses"]
                if course["course_id"] != activityId
            ],
            "students": database["students"],
            "campus_graph": database.get("campus_graph", {}),
        },
        updated,
    )
    if not ok:
        return False, code

    for course in database["courses"]:
        if course["course_id"] == activityId:
            course.clear()
            course.update({
                "course_id": activityId,
                "title": updated["title"],
                "credits": 0,
                "required": False,
                "teacher": updated.get("teacher", "NPC"),
                "classroom_id": updated["classroom_id"],
                "capacity": updated["capacity"],
                "time_slots": copy.deepcopy(updated["time_slots"]),
                "enrolled_count": activity.get("enrolled_count", 0),
                "course_type": "event",
                "activity_type": updated.get("activity_type", ""),
                "required_equipment": copy.deepcopy(updated.get("required_equipment", [])),
            })
            break
    return True, OK


def CancelActivity(database: dict, activityId: str) -> tuple[bool, str, list[str]]:
    """Remove an event and drop it from every student's enrolled course list."""
    activity = courseDataManager.FindCourse(database, activityId)
    if activity is None or activity.get("course_type") != "event":
        return False, ACTIVITY_NOT_FOUND, []
    dropped = []
    for student in database.get("students", []):
        if activityId in student.get("enrolled_courses", []):
            student["enrolled_courses"].remove(activityId)
            dropped.append(student["student_id"])
    database["courses"] = [
        course for course in database["courses"]
        if course["course_id"] != activityId
    ]
    return True, OK, dropped
