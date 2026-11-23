"""F4 校園活動與教室配置初版的自動化測試。

本組測試對準迭代 2 已完成的兩個介面：可用教室篩選與指定教室新增活動。
每個案例使用獨立的小型資料庫，失敗案例也會確認原資料沒有被部分修改。
執行：python -m pytest -m f4 -v
"""

import copy
import datetime

import pytest

import VenueManager as venueManager
from Constants import (
    CAPACITY_EXCEEDS_ROOM,
    CLASSROOM_NOT_FOUND,
    DUPLICATE_ID,
    INVALID_CAPACITY,
    INVALID_DAY,
    INVALID_FIELD,
    INVALID_PERIOD,
    INVALID_TIME_SLOTS,
    NO_AVAILABLE_ROOM,
    OK,
    ROOM_CONFLICT,
)
from TimeSlotUtils import LOCAL_TIME_ZONE

pytestmark = pytest.mark.f4


def Room(roomId, capacity, equipment=()):
    return {
        "classroom_id": roomId,
        "capacity": capacity,
        "equipment": list(equipment),
    }


def Course(courseId, roomId, slots):
    return {
        "course_id": courseId,
        "title": courseId,
        "credits": 3,
        "required": False,
        "teacher": "T",
        "classroom_id": roomId,
        "capacity": 10,
        "enrolled_count": 0,
        "time_slots": [{"day": day, "period": period} for day, period in slots],
    }


def Database(courses=()):
    return {
        "classrooms": [
            Room("R-S", 10, ["projector"]),
            Room("R-A", 30, ["projector", "audio"]),
            Room("R-B", 30, ["projector", "audio"]),
            Room("R-L", 80, ["projector", "audio", "computer"]),
        ],
        "courses": list(courses),
        "students": [],
        "campus_graph": {"nodes": [], "edges": []},
    }


def Activity(**overrides):
    activity = {
        "activity_id": "ACT-NEW",
        "title": "測試活動",
        "classroom_id": "R-A",
        "capacity": 20,
        "time_slots": [{"day": 2, "period": "5"}],
        "activity_type": "講座",
        "required_equipment": ["projector", "audio"],
    }
    activity.update(overrides)
    return activity


def test_AvailableRoomsFilterCapacityEquipmentAndSortSmallestFirst():
    database = Database()
    ok, code, rooms = venueManager.FindAvailableClassrooms(
        database,
        [{"day": 2, "period": "5"}],
        minCapacity=20,
        requiredEquipment=["projector", "audio"],
    )
    assert (ok, code) == (True, OK)
    assert [room["classroom_id"] for room in rooms] == ["R-A", "R-B", "R-L"]


def test_OccupiedRoomIsExcludedForTheWholeRequestedRange():
    database = Database([Course("CS1", "R-A", [(2, "5")])])
    ok, code, rooms = venueManager.FindAvailableClassrooms(
        database,
        [{"day": 2, "period": "5"}, {"day": 2, "period": "6"}],
        minCapacity=20,
        requiredEquipment=["audio"],
    )
    assert (ok, code) == (True, OK)
    assert [room["classroom_id"] for room in rooms] == ["R-B", "R-L"]


def test_DateBasedActivityConflictsWithWeeklyCourseOnSameWeekday():
    tuesday = int(datetime.datetime(2026, 10, 6, tzinfo=LOCAL_TIME_ZONE).timestamp())
    database = Database([Course("CS1", "R-A", [(2, "5")])])
    _, _, rooms = venueManager.FindAvailableClassrooms(
        database, [{"day": tuesday, "period": "5"}], minCapacity=20
    )
    assert "R-A" not in {room["classroom_id"] for room in rooms}


@pytest.mark.parametrize(
    ("slots", "expectedCode"),
    [
        ([], INVALID_TIME_SLOTS),
        ([{"day": 0, "period": "1"}], INVALID_DAY),
        ([{"day": 1, "period": "d"}], INVALID_PERIOD),
    ],
)
def test_AvailableRoomsRejectInvalidTimeSlots(slots, expectedCode):
    assert venueManager.FindAvailableClassrooms(Database(), slots) == (
        False, expectedCode, []
    )


@pytest.mark.parametrize(
    ("capacity", "equipment", "expectedCode"),
    [
        (0, [], INVALID_CAPACITY),
        (True, [], INVALID_CAPACITY),
        (1, "projector", INVALID_FIELD),
        (1, [""], INVALID_FIELD),
    ],
)
def test_AvailableRoomsRejectInvalidRequirements(capacity, equipment, expectedCode):
    assert venueManager.FindAvailableClassrooms(
        Database(), [{"day": 1, "period": "1"}], capacity, equipment
    ) == (False, expectedCode, [])


def test_AddActivityCreatesEventAndCopiesMutableFields():
    database = Database()
    activity = Activity()
    assert venueManager.AddActivity(database, activity) == (True, OK)

    event = database["courses"][0]
    assert event == {
        "course_id": "ACT-NEW",
        "title": "測試活動",
        "credits": 0,
        "required": False,
        "teacher": "NPC",
        "classroom_id": "R-A",
        "capacity": 20,
        "time_slots": [{"day": 2, "period": "5"}],
        "enrolled_count": 0,
        "course_type": "event",
        "activity_type": "講座",
        "required_equipment": ["projector", "audio"],
    }
    activity["time_slots"][0]["period"] = "9"
    activity["required_equipment"].append("computer")
    assert event["time_slots"] == [{"day": 2, "period": "5"}]
    assert event["required_equipment"] == ["projector", "audio"]


@pytest.mark.parametrize(
    ("changes", "expectedCode"),
    [
        ({"activity_id": ""}, INVALID_FIELD),
        ({"title": "  "}, INVALID_FIELD),
        ({"classroom_id": "NOPE"}, CLASSROOM_NOT_FOUND),
        ({"capacity": 0}, INVALID_CAPACITY),
        ({"capacity": 31}, CAPACITY_EXCEEDS_ROOM),
        ({"required_equipment": ["computer"]}, NO_AVAILABLE_ROOM),
    ],
)
def test_AddActivityRejectsInvalidFieldsWithoutChangingDatabase(changes, expectedCode):
    database = Database()
    before = copy.deepcopy(database)
    assert venueManager.AddActivity(database, Activity(**changes)) == (False, expectedCode)
    assert database == before


def test_AddActivityRejectsDuplicateIdWithoutChangingDatabase():
    database = Database([Course("ACT-NEW", "R-S", [(1, "1")])])
    before = copy.deepcopy(database)
    assert venueManager.AddActivity(database, Activity()) == (False, DUPLICATE_ID)
    assert database == before


def test_AddActivityReportsRoomConflictAndKeepsDatabaseUnchanged():
    database = Database([Course("CS1", "R-A", [(2, "5")])])
    before = copy.deepcopy(database)
    assert venueManager.AddActivity(database, Activity()) == (False, ROOM_CONFLICT)
    assert database == before


def test_NoRoomMeetsAllRequirements():
    assert venueManager.FindAvailableClassrooms(
        Database(),
        [{"day": 2, "period": "5"}],
        minCapacity=100,
        requiredEquipment=["computer"],
    ) == (False, NO_AVAILABLE_ROOM, [])


def test_AutoMatchSelectsSmallestAvailableRoom():
    database = Database()
    activity = Activity(classroom_id=None)
    assert venueManager.AddActivity(database, activity) == (True, OK)
    assert database["courses"][0]["classroom_id"] == "R-A"


def test_TimeRangeToSlotsUsesOverlappingPeriods():
    timestamp = int(datetime.datetime(2026, 10, 6, tzinfo=LOCAL_TIME_ZONE).timestamp())
    assert venueManager.TimeRangeToSlots(timestamp, "14:00", "16:30") == (
        True,
        OK,
        [
            {"day": int(datetime.datetime(2026, 10, 6, tzinfo=LOCAL_TIME_ZONE).timestamp()), "period": "6"},
            {"day": int(datetime.datetime(2026, 10, 6, tzinfo=LOCAL_TIME_ZONE).timestamp()), "period": "7"},
            {"day": int(datetime.datetime(2026, 10, 6, tzinfo=LOCAL_TIME_ZONE).timestamp()), "period": "8"},
        ],
    )
    assert venueManager.TimeRangeToSlots(timestamp, "12:00", "13:00")[1] == INVALID_TIME_SLOTS


def test_UpdateAndCancelActivityAreAtomicAndReleaseRoom():
    database = Database()
    assert venueManager.AddActivity(database, Activity()) == (True, OK)
    database["students"] = [{"student_id": "S1", "name": "S", "department": "CS",
                             "max_credits": 25, "grade": 1, "enrolled_courses": ["ACT-NEW"]}]
    assert venueManager.UpdateActivity(database, "ACT-NEW", {"title": "更新活動"}) == (True, OK)
    assert database["courses"][0]["title"] == "更新活動"
    assert venueManager.CancelActivity(database, "ACT-NEW") == (True, OK, ["S1"])
    assert database["courses"] == []
    assert database["students"][0]["enrolled_courses"] == []


def test_QueryActivitiesFiltersByTypeDateAndSeats():
    timestamp = int(datetime.datetime(2026, 10, 6, tzinfo=LOCAL_TIME_ZONE).timestamp())
    database = Database([{
        "course_id": "ACT-X", "title": "講座", "credits": 0, "required": False,
        "teacher": "NPC", "classroom_id": "R-A", "capacity": 20,
        "enrolled_count": 20, "time_slots": [{"day": timestamp, "period": "5"}],
        "course_type": "event", "activity_type": "講座",
        "required_equipment": ["projector"],
    }])
    assert venueManager.QueryActivities(database, activityType="講座", date=timestamp, hasSeats=False)[0]["course_id"] == "ACT-X"
    assert venueManager.QueryActivities(database, activityType="講座", hasSeats=True) == []


def test_ExplainUnavailableReportsCapacityAndEquipment():
    reasons = venueManager.ExplainUnavailable(Database(), [{"day": 2, "period": "5"}], 100, ["computer"])
    assert any(reason["reason"] == "INSUFFICIENT_CAPACITY" for reason in reasons)
