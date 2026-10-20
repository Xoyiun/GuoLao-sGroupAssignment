"""F1 課程、學生與教室資料管理 的自動化測試。

分類（用 pytest 標記，可分開執行與計數）：
  normal      正常案例   10 個   python -m pytest -m normal -v
  boundary    邊界案例   11 個   python -m pytest -m boundary -v
  error       錯誤案例   10 個   python -m pytest -m error -v
  extra       補充案例（參數化與較細的檢查，不計入上面 30 個）
  persistence 存檔與容錯載入（F6 相關，不計入上面 30 個）
  acceptance  F1 驗收條件（資料量）

測試資料 = TestInput/Courses 與 TestInput/Students（按 ID 分檔，載入後複製到記憶體）
          + 每個測試自己組出來的輸入（new_course / new_student）。
"""

import copy
import datetime
import json
import os
import shutil

import pytest

import CourseDataManager as courseDataManager
from ConflictChecker import CheckTimeConflict
from StorageManager import StorageManager, LoadDatabase
from TimeSlotUtils import GetWeekday, LOCAL_TIME_ZONE
from VenueManager import AddActivity

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, "TestInput")


def CopyFixedData(directory):
    userData = os.path.join(os.path.dirname(HERE), "UserData")
    for filename in ("Classroom.json", "CampusGraph.json"):
        shutil.copy(os.path.join(userData, filename), directory)


def CopyInputData(directory):
    os.makedirs(directory, exist_ok=True)
    for category in ("Courses", "Students"):
        shutil.copytree(os.path.join(SEED, category), os.path.join(directory, category))
    CopyFixedData(directory)


def ReadSeedData():
    data = {"course": [], "students": [], "activities": []}
    for fileName in os.listdir(os.path.join(SEED, "Courses")):
        with open(os.path.join(SEED, "Courses", fileName), encoding="utf-8") as dataFile:
            data["course"].append(json.load(dataFile))
    for fileName in os.listdir(os.path.join(SEED, "Students")):
        with open(os.path.join(SEED, "Students", fileName), encoding="utf-8") as dataFile:
            data["students"].append(json.load(dataFile))
    return data


@pytest.fixture(name="database")
def Database(tmp_path):
    """每個測試拿到一份全新的記憶體資料，完全不碰檔案。"""
    assert os.path.exists(SEED), f"找不到種子檔：{SEED}"
    CopyInputData(tmp_path)
    data, errors, corrupted = LoadDatabase(str(tmp_path))
    assert not errors and not corrupted
    return copy.deepcopy(data)


def NewCourse(**overrides):
    """組出一門合法的新課程；用 overrides 改掉想測的欄位。"""
    course = {
        "course_id": "NEW101",
        "title": "測試課程",
        "credits": 3,
        "required": False,
        "teacher": "測試教授",
        "classroom_id": "TR-310",
        "capacity": 30,
        "time_slots": [{"day": 1, "period": "1"}],
    }
    course.update(overrides)
    return course


def NewStudent(**overrides):
    """組出一位合法的新學生；用 overrides 改掉想測的欄位。"""
    student = {
        "student_id": "S99999",
        "name": "測試生",
        "department": "資工系",
        "max_credits": 25,
        "enrolled_courses": [],
    }
    student.update(overrides)
    return student


# ======================================================================
# 驗收條件（資料量）
# ======================================================================
@pytest.mark.acceptance
def test_SeedMeetsAcceptanceCounts(database):
    """種子資料至少有 20 門課、15 名學生、5 間教室。"""
    assert len(database["courses"]) >= 23
    assert len(database["students"]) >= 15
    assert len(database["classrooms"]) >= 5


@pytest.mark.acceptance
def test_SeedUsesReferenceFormatAndLoadsFixedData(database):
    """測試資料按 ID 拆檔，活動依課程格式轉成 event 課程。"""
    raw = ReadSeedData()
    assert {"name", "type", "classroom"} <= raw["course"][0].keys()
    assert {"grade", "enrolled_courses"} <= raw["students"][0].keys()
    assert "enrolled_activities" not in raw["students"][0]
    events = [course for course in raw["course"] if course["type"] == "event"]
    assert len(events) == 3
    assert all(course["credits"] == 0 for course in events)
    assert all(course["time_slots"][0]["day"] > 86_400 for course in events)

    assert database["courses"][0]["title"] == raw["course"][0]["name"]
    assert database["classrooms"][0]["building_name"] == "研揚大樓"
    assert len(database["campus_graph"]["nodes"]) == 10
    assert len(database["courses"]) == 23 and database["activities"] == []


@pytest.mark.acceptance
def test_EventsAreStoredAsDateBasedCourses(database):
    """活動轉成 event 課程，day 為台北時區午夜的 Unix 時間戳。"""
    eventCourses = [
        course for course in database["courses"]
        if course.get("course_type") == "event"
    ]
    assert {course["course_id"] for course in eventCourses} == {
        "ACT01", "ACT02", "ACT03"
    }
    assert all(course["credits"] == 0 for course in eventCourses)
    assert all(
        slot["day"] > 86_400
        for course in eventCourses
        for slot in course["time_slots"]
    )
    assert all(
        datetime.datetime.fromtimestamp(
            slot["day"], LOCAL_TIME_ZONE
        ).time() == datetime.time()
        for course in eventCourses
        for slot in course["time_slots"]
    )


@pytest.mark.acceptance
def test_PerIdFilesAreNamedByRecordIds():
    for directoryName, idField in (
        ("Courses", "course_id"),
        ("Students", "student_id"),
    ):
        directory = os.path.join(SEED, directoryName)
        for fileName in os.listdir(directory):
            with open(os.path.join(directory, fileName), encoding="utf-8") as dataFile:
                record = json.load(dataFile)
            assert fileName == f"{record[idField]}.json"


@pytest.mark.extra
def test_DateBasedEventSlotsKeepDatesWhenCheckingConflicts(database):
    firstEvent = courseDataManager.FindCourse(database, "ACT02")
    secondEvent = courseDataManager.FindCourse(database, "ACT03")
    assert firstEvent and secondEvent
    assert firstEvent["time_slots"][0]["day"] != secondEvent["time_slots"][0]["day"]
    assert CheckTimeConflict(
        firstEvent["time_slots"], secondEvent["time_slots"]
    ) == (True, courseDataManager.OK, [])

    eventSlot = firstEvent["time_slots"][0]
    weekdaySlot = {"day": GetWeekday(eventSlot["day"]), "period": eventSlot["period"]}
    assert not CheckTimeConflict([eventSlot], [weekdaySlot])[0]


@pytest.mark.extra
def test_NewActivitiesAreStoredAsEventCourses(database):
    activity = {
        "activity_id": "ACT-NEW",
        "title": "測試活動",
        "classroom_id": "TR-310",
        "capacity": 20,
        "time_slots": [{"day": 7, "period": "c"}],
    }
    assert AddActivity(database, activity) == (True, courseDataManager.OK)
    eventCourse = courseDataManager.FindCourse(database, "ACT-NEW")
    assert eventCourse["course_type"] == "event"
    assert eventCourse["credits"] == 0
    assert database["activities"] == []


# ======================================================================
# 正常案例（10）：合法輸入，預期成功
# ======================================================================
@pytest.mark.normal
def test_N01AddCourse(database):
    """新增一門合法課程 → 成功，且初始人數為 0。"""
    assert courseDataManager.AddCourse(database, NewCourse()) == (True, courseDataManager.OK)
    assert courseDataManager.FindCourse(database, "NEW101")["enrolled_count"] == 0


@pytest.mark.normal
def test_N02UpdateCourse(database):
    """修改課程的教師與學分 → 成功，資料確實更新。"""
    courseDataManager.AddCourse(database, NewCourse())
    assert courseDataManager.UpdateCourse(database, "NEW101", {"teacher": "新老師", "credits": 2}) == (True, courseDataManager.OK)
    course = courseDataManager.FindCourse(database, "NEW101")
    assert (course["teacher"], course["credits"]) == ("新老師", 2)


@pytest.mark.normal
def test_N03DeleteCourseWithoutStudents(database):
    """刪除沒有學生選修的課程 → 成功，課程消失。"""
    courseDataManager.AddCourse(database, NewCourse())
    assert courseDataManager.DeleteCourse(database, "NEW101") == (True, courseDataManager.OK)
    assert courseDataManager.FindCourse(database, "NEW101") is None


@pytest.mark.normal
def test_N04AddStudent(database):
    """新增一位合法學生 → 成功，且選課清單為空。"""
    assert courseDataManager.AddStudent(database, NewStudent()) == (True, courseDataManager.OK)
    assert courseDataManager.FindStudent(database, "S99999")["enrolled_courses"] == []


@pytest.mark.normal
def test_N05UpdateStudent(database):
    """修改學生姓名與學分上限 → 成功，資料確實更新。"""
    courseDataManager.AddStudent(database, NewStudent())
    assert courseDataManager.UpdateStudent(database, "S99999", {"name": "改名", "max_credits": 20}) == (True, courseDataManager.OK)
    student = courseDataManager.FindStudent(database, "S99999")
    assert (student["name"], student["max_credits"]) == ("改名", 20)


@pytest.mark.normal
def test_N06DeleteStudentDecrementsEnrolledCount(database):
    """刪除已選 CS101 的學生 → 成功，CS101 的 enrolled_count 減 1。"""
    before = courseDataManager.FindCourse(database, "CS101")["enrolled_count"]
    assert courseDataManager.DeleteStudent(database, "S10901") == (True, courseDataManager.OK)
    assert courseDataManager.FindStudent(database, "S10901") is None
    assert courseDataManager.FindCourse(database, "CS101")["enrolled_count"] == before - 1


@pytest.mark.normal
def test_N07QueryByTeacher(database):
    """依教師查詢「林教授」→ 只有 CS101 與 CS203。"""
    ids = {c["course_id"] for c in courseDataManager.QueryCourses(database, teacher="林教授")}
    assert ids == {"CS101", "CS203"}


@pytest.mark.normal
def test_N08QueryByDay(database):
    """依星期查詢週五 → 包含 MA101、CS201、GE102、PE101，不含週一的 CS101。"""
    ids = {c["course_id"] for c in courseDataManager.QueryCourses(database, day=5)}
    assert {"MA101", "CS201", "GE102", "PE101"} <= ids
    assert "CS101" not in ids


@pytest.mark.normal
def test_N09QueryHasSeats(database):
    """依剩餘名額查詢已額滿 → 包含 GE101、PE101，不含還有空位的 CS101。"""
    full = {c["course_id"] for c in courseDataManager.QueryCourses(database, hasSeats=False)}
    assert {"GE101", "PE101"} <= full
    assert "CS101" not in full


@pytest.mark.normal
def test_N10AddClassroom(database):
    """新增一間合法教室 → 成功，且可被查到。"""
    room = {"classroom_id": "X-1", "capacity": 10, "equipment": ["projector"]}
    assert courseDataManager.AddClassroom(database, room) == (True, courseDataManager.OK)
    assert courseDataManager.FindClassroom(database, "X-1")["capacity"] == 10


# ======================================================================
# 邊界案例（11）：剛好在合法範圍邊緣，預期成功或行為正確
# ======================================================================
@pytest.mark.boundary
def test_B01CapacityExactlyOne(database):
    """課程人數上限剛好 1（最小合法值）→ 成功。"""
    assert courseDataManager.AddCourse(database, NewCourse(capacity=1)) == (True, courseDataManager.OK)


@pytest.mark.boundary
def test_B02CapacityEqualsClassroomCapacity(database):
    """課程人數上限剛好等於教室容量（TR-310 為 60）→ 成功。"""
    assert courseDataManager.AddCourse(database, NewCourse(capacity=60)) == (True, courseDataManager.OK)


@pytest.mark.boundary
def test_B03CreditsExactlyOne(database):
    """學分剛好 1（最小合法值）→ 成功。"""
    assert courseDataManager.AddCourse(database, NewCourse(credits=1)) == (True, courseDataManager.OK)


@pytest.mark.boundary
def test_B04Day1AndDay7(database):
    """星期 1 與星期 7（合法範圍的兩端）同時出現 → 成功。"""
    slots = [{"day": 1, "period": "1"}, {"day": 7, "period": "1"}]
    assert courseDataManager.AddCourse(database, NewCourse(time_slots=slots)) == (True, courseDataManager.OK)


@pytest.mark.boundary
def test_B05Period9(database):
    """節次 "9"（最後一個數字節次）→ 成功。"""
    assert courseDataManager.AddCourse(database, NewCourse(time_slots=[{"day": 1, "period": "9"}]))[0]


@pytest.mark.boundary
def test_B06PeriodA(database):
    """節次 "a"（第一個字母節次）→ 成功。"""
    assert courseDataManager.AddCourse(database, NewCourse(time_slots=[{"day": 1, "period": "a"}]))[0]


@pytest.mark.boundary
def test_B07PeriodC(database):
    """節次 "c"（最後一個合法節次）→ 成功。"""
    assert courseDataManager.AddCourse(database, NewCourse(time_slots=[{"day": 1, "period": "c"}]))[0]


@pytest.mark.boundary
def test_B08QueryNoMatchReturnsEmpty(database):
    """查詢不存在的教師 → 回傳空清單，不報錯。"""
    assert courseDataManager.QueryCourses(database, teacher="不存在的人") == []


@pytest.mark.boundary
def test_B09QueryWithoutConditionsReturnsAll(database):
    """不給任何查詢條件 → 回傳全部課程。"""
    assert len(courseDataManager.QueryCourses(database)) == len(database["courses"])


@pytest.mark.boundary
def test_B10UpdateCapacityDownToEnrolledCount(database):
    """把人數上限降到剛好等於目前人數 → 成功（再低一個才會被拒絕）。"""
    courseDataManager.AddCourse(database, NewCourse())
    database["courses"][-1]["enrolled_count"] = 10
    assert courseDataManager.UpdateCourse(database, "NEW101", {"capacity": 10}) == (True, courseDataManager.OK)


# 新增：enrolled_count 已經是 0 時刪除學生，人數要停在 0，不能變成 -1
@pytest.mark.boundary
def test_B11DeleteStudentEnrolledCountStaysAtZero(database):
    """CS101 的 enrolled_count 設成 0，再刪除已選 CS101 的學生 → 成功，人數停在 0（不會變 -1）。"""
    courseDataManager.FindCourse(database, "CS101")["enrolled_count"] = 0
    assert courseDataManager.DeleteStudent(database, "S10901") == (True, courseDataManager.OK)
    assert courseDataManager.FindStudent(database, "S10901") is None
    assert courseDataManager.FindCourse(database, "CS101")["enrolled_count"] == 0



# ======================================================================
# 錯誤案例（10）：違規輸入，預期被拒絕並回傳正確錯誤碼
# ======================================================================
@pytest.mark.error
def test_E01DuplicateCourseId(database):
    """新增已存在的課程代號 CS101 → DUPLICATE_ID。"""
    assert courseDataManager.AddCourse(database, NewCourse(course_id="CS101")) == (False, courseDataManager.DUPLICATE_ID)


@pytest.mark.error
def test_E02DuplicateStudentId(database):
    """新增已存在的學號 S10901 → DUPLICATE_ID。"""
    assert courseDataManager.AddStudent(database, NewStudent(student_id="S10901")) == (False, courseDataManager.DUPLICATE_ID)


@pytest.mark.error
def test_E03InvalidPeriod(database):
    """節次 "d"（超出 1–9、a、b、c）→ INVALID_PERIOD。"""
    r = courseDataManager.AddCourse(database, NewCourse(time_slots=[{"day": 1, "period": "d"}]))
    assert r == (False, courseDataManager.INVALID_PERIOD)


@pytest.mark.error
def test_E04InvalidDay(database):
    """星期 8（超出 1–7）→ INVALID_DAY。"""
    r = courseDataManager.AddCourse(database, NewCourse(time_slots=[{"day": 8, "period": "1"}]))
    assert r == (False, courseDataManager.INVALID_DAY)


@pytest.mark.error
def test_E05InvalidCreditsZero(database):
    """學分為 0（必須是正整數）→ INVALID_CREDITS。"""
    assert courseDataManager.AddCourse(database, NewCourse(credits=0)) == (False, courseDataManager.INVALID_CREDITS)


@pytest.mark.error
def test_E06InvalidCapacityZero(database):
    """人數上限為 0（不得小於 1）→ INVALID_CAPACITY。"""
    assert courseDataManager.AddCourse(database, NewCourse(capacity=0)) == (False, courseDataManager.INVALID_CAPACITY)


@pytest.mark.error
def test_E07CapacityExceedsClassroom(database):
    """人數上限 61 超過 TR-310 的容量 60 → CAPACITY_EXCEEDS_ROOM。"""
    assert courseDataManager.AddCourse(database, NewCourse(capacity=61)) == (False, courseDataManager.CAPACITY_EXCEEDS_ROOM)


@pytest.mark.error
def test_E08ClassroomNotFound(database):
    """使用不存在的教室 → CLASSROOM_NOT_FOUND。"""
    assert courseDataManager.AddCourse(database, NewCourse(classroom_id="ZZ-999")) == (False, courseDataManager.CLASSROOM_NOT_FOUND)


@pytest.mark.error
def test_E09DeleteCourseWithStudentsRejected(database):
    """刪除已有學生選修的 CS101 → COURSE_HAS_STUDENTS，且課程仍在。"""
    assert courseDataManager.DeleteCourse(database, "CS101") == (False, courseDataManager.COURSE_HAS_STUDENTS)
    assert courseDataManager.FindCourse(database, "CS101") is not None


@pytest.mark.error
def test_E10EmptyTimeSlots(database):
    """上課時段為空清單 → INVALID_TIME_SLOTS。"""
    assert courseDataManager.AddCourse(database, NewCourse(time_slots=[])) == (False, courseDataManager.INVALID_TIME_SLOTS)


# ======================================================================
# 補充案例（不計入 10/10/10）：更多數值與較細的規則
# ======================================================================
@pytest.mark.extra
@pytest.mark.parametrize("period", ["d", "0", "10", "", "A", 2])
def test_XInvalidPeriodValues(database, period):
    r = courseDataManager.AddCourse(database, NewCourse(time_slots=[{"day": 1, "period": period}]))
    assert r == (False, courseDataManager.INVALID_PERIOD)


@pytest.mark.extra
@pytest.mark.parametrize("day", [0, 8, -1, "1", True])
def test_XInvalidDayValues(database, day):
    r = courseDataManager.AddCourse(database, NewCourse(time_slots=[{"day": day, "period": "1"}]))
    assert r == (False, courseDataManager.INVALID_DAY)


@pytest.mark.extra
@pytest.mark.parametrize("credits", [0, -1, 2.5, "3", True, None])
def test_XInvalidCreditsValues(database, credits):
    assert courseDataManager.AddCourse(database, NewCourse(credits=credits)) == (False, courseDataManager.INVALID_CREDITS)


@pytest.mark.extra
@pytest.mark.parametrize("capacity", [0, -5, "30", 1.5, None])
def test_XInvalidCapacityValues(database, capacity):
    assert courseDataManager.AddCourse(database, NewCourse(capacity=capacity)) == (False, courseDataManager.INVALID_CAPACITY)


@pytest.mark.extra
def test_XDuplicateTimeSlot(database):
    dup = [{"day": 1, "period": "1"}, {"day": 1, "period": "1"}]
    assert courseDataManager.AddCourse(database, NewCourse(time_slots=dup)) == (False, courseDataManager.DUPLICATE_SLOT)


@pytest.mark.extra
def test_XMultipleTimeSlotsAccepted(database):
    slots = [{"day": 1, "period": "1"}, {"day": 3, "period": "c"}]
    assert courseDataManager.AddCourse(database, NewCourse(time_slots=slots))[0]


@pytest.mark.extra
def test_XQueryByRequiredAndCourseId(database):
    assert all(c["required"] for c in courseDataManager.QueryCourses(database, required=True))
    assert [c["course_id"] for c in courseDataManager.QueryCourses(database, courseId="CS103")] == ["CS103"]


@pytest.mark.extra
def test_XFailedAddDoesNotModifyDb(database):
    before = copy.deepcopy(database)
    courseDataManager.AddCourse(database, NewCourse(credits=0))
    assert database == before


@pytest.mark.extra
def test_XDeleteCourseListedStudentButZeroCount(database):
    courseDataManager.AddCourse(database, NewCourse())
    courseDataManager.AddStudent(database, NewStudent(enrolled_courses=["NEW101"]))
    assert courseDataManager.DeleteCourse(database, "NEW101") == (False, courseDataManager.COURSE_HAS_STUDENTS)


@pytest.mark.extra
def test_XDeleteMissingCourse(database):
    assert courseDataManager.DeleteCourse(database, "NOPE") == (False, courseDataManager.NOT_FOUND)


@pytest.mark.extra
def test_XUpdateMissingCourseAndBadField(database):
    assert courseDataManager.UpdateCourse(database, "NOPE", {"title": "x"}) == (False, courseDataManager.NOT_FOUND)
    assert courseDataManager.UpdateCourse(database, "CS101", {"course_id": "X"}) == (False, courseDataManager.INVALID_FIELD)


@pytest.mark.extra
def test_XUpdateCapacityBelowEnrolledRejected(database):
    assert courseDataManager.UpdateCourse(database, "CS101", {"capacity": 10}) == (False, courseDataManager.INVALID_CAPACITY)


@pytest.mark.extra
def test_XStudentWithUnknownCourse(database):
    r = courseDataManager.AddStudent(database, NewStudent(enrolled_courses=["NOPE"]))
    assert r == (False, courseDataManager.COURSE_NOT_FOUND)


@pytest.mark.extra
def test_XStudentInvalidMaxCredits(database):
    assert courseDataManager.AddStudent(database, NewStudent(max_credits=0)) == (False, courseDataManager.INVALID_CREDITS)


@pytest.mark.extra
def test_XDeleteClassroomInUse(database):
    assert courseDataManager.DeleteClassroom(database, "TR-310") == (False, courseDataManager.CLASSROOM_IN_USE)


@pytest.mark.extra
@pytest.mark.parametrize("equipment", ["projector", [1, 2], ["projector", None]])
def test_XAddClassroomBadEquipment(database, equipment):
    """設備必須是文字清單；否則列出教室時會當掉，新增時就要擋下。"""
    room = {"classroom_id": "X-2", "capacity": 10, "equipment": equipment}
    assert courseDataManager.AddClassroom(database, room) == (False, courseDataManager.INVALID_FIELD)
    assert courseDataManager.FindClassroom(database, "X-2") is None


# ======================================================================
# 存檔與容錯載入（F6 相關，不計入 10/10/10）
# ======================================================================
@pytest.mark.persistence
def test_PSaveGoesToSavePathAndSeedUntouched(tmp_path):
    """存檔寫到工作資料夾，輸入檔位元組完全不變；重新載入後資料還在。"""
    seedCopy = tmp_path / "seed"
    CopyInputData(seedCopy)
    seedBytes = (seedCopy / "Courses" / "CS101.json").read_bytes()
    work = tmp_path / "work"
    work.mkdir()
    CopyFixedData(work)

    m = courseDataManager.CourseDataManager(str(seedCopy), savePath=str(work))
    assert m.AddCourse(NewCourse()) == (True, courseDataManager.OK)

    assert (seedCopy / "Courses" / "CS101.json").read_bytes() == seedBytes
    assert (work / "Courses" / "NEW101.json").exists()
    again = courseDataManager.CourseDataManager(str(work), savePath=str(work))
    assert courseDataManager.FindCourse(again.data, "NEW101") is not None


@pytest.mark.persistence
def test_PClassroomChangesPersistToFixedDataFile(tmp_path):
    seedCopy = tmp_path / "seed"
    work = tmp_path / "work"
    CopyInputData(seedCopy)
    CopyInputData(work)
    manager = courseDataManager.CourseDataManager(
        str(seedCopy), savePath=str(work)
    )
    room = {
        "classroom_id": "NEW-1",
        "building_id": "NEW",
        "building_name": "新教學大樓",
        "capacity": 20,
        "equipment": ["projector"],
    }
    assert manager.AddClassroom(room) == (True, courseDataManager.OK)

    savedClassrooms = json.loads(
        (work / "Classroom.json").read_text(encoding="utf-8")
    )["classroom"]
    assert any(record["room_id"] == "NEW-1" for record in savedClassrooms)
    reloaded = courseDataManager.CourseDataManager(str(work), savePath=str(work))
    assert reloaded.FindClassroom("NEW-1")["building_name"] == "新教學大樓"



@pytest.mark.persistence
def test_PDefaultSavePathNeverOverwritesSeed(tmp_path):
    """沒指定 save_path 時，預設存到同資料夾的 db.json，種子檔位元組完全不變。"""
    seedCopy = tmp_path / "seed"
    CopyInputData(seedCopy)
    seedBytes = (seedCopy / "Courses" / "CS101.json").read_bytes()

    m = courseDataManager.CourseDataManager(str(seedCopy))  # 故意不給 save_path
    assert m.AddCourse(NewCourse()) == (True, courseDataManager.OK)

    assert (seedCopy / "Courses" / "CS101.json").read_bytes() == seedBytes
    assert (seedCopy / "db.json").exists()



@pytest.mark.persistence
def test_PAutosaveOffWritesNothing(tmp_path):
    """autosave=False 時，新增資料不會產生任何檔案。"""
    seedCopy = tmp_path / "seed"
    CopyInputData(seedCopy)
    work = tmp_path / "work.json"
    m = courseDataManager.CourseDataManager(str(seedCopy), savePath=str(work), autosave=False)
    m.AddCourse(NewCourse())
    assert not work.exists()


@pytest.mark.persistence
def test_PBadRecordSkippedNotCrash(tmp_path):
    """檔案中有缺欄位或型別錯誤的單筆資料 → 跳過並記錄，程式不當掉。"""
    raw = ReadSeedData()
    raw["course"].append({"course_id": "BROKEN"})  # 缺欄位
    raw["course"].append("not a dict")
    CopyFixedData(tmp_path)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    m = StorageManager(str(path), savePath=str(tmp_path / "out.json"))
    assert len(m.GetCourses()) == 23
    assert len(m.loadErrors) == 2


@pytest.mark.persistence
@pytest.mark.parametrize("field, value", [
    ("time_slots", "1-3"),                      # 時段寫成字串
    ("time_slots", [{"day": 9, "period": "1"}]),  # 星期超出 1–7
    ("time_slots", [{"day": 1, "period": "z"}]),  # 節次不是 1–9、a、b、c
    ("credits", "abc"),
    ("capacity", "60"),
    ("type", "是"),
    ("enrolled_count", None),
])
def test_PBadCourseFormatSkippedNotCrash(tmp_path, field, value):
    """欄位都在但格式錯 → 載入時跳過，之後查詢課程不會當掉。"""
    raw = ReadSeedData()
    course = NewCourse(course_id="BROKEN", **({"required": False} if field == "type" else {}))
    referenceCourse = {
        "course_id": course["course_id"],
        "name": course["title"],
        "credits": course["credits"],
        "type": "Required" if course["required"] else "unRequired",
        "teacher": course["teacher"],
        "capacity": course["capacity"],
        "classroom": course["classroom_id"],
        "time_slots": course["time_slots"],
        "enrolled_count": 0,
    }
    referenceCourse[field] = value
    raw["course"].append(referenceCourse)
    CopyFixedData(tmp_path)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    m = StorageManager(str(path), savePath=str(tmp_path / "out.json"))
    assert courseDataManager.FindCourse(m.data, "BROKEN") is None
    assert len(m.GetCourses()) == 23
    assert len(m.loadErrors) == 1 and field in m.loadErrors[0]
    courseDataManager.QueryCourses(m.data, day=1, hasSeats=True)  # 不得拋出例外


@pytest.mark.persistence
def test_PBadStudentClassroomActivityFormatSkipped(tmp_path):
    """學生、教室、活動的欄位格式錯誤也一樣跳過，其他資料照常載入。"""
    raw = ReadSeedData()
    raw["students"].append(NewStudent(student_id="BAD-S", enrolled_courses="CS101"))
    raw["activities"].append({"activity_id": "BAD-A", "title": "x", "classroom_id": "TR-310", "time_slots": None})
    CopyFixedData(tmp_path)
    classroomPath = tmp_path / "Classroom.json"
    with classroomPath.open(encoding="utf-8") as f:
        classroomData = json.load(f)
    classroomData["classroom"].append(
        {"room_id": "BAD-R", "capacity": 10, "equipment": "projector"}
    )
    classroomPath.write_text(json.dumps(classroomData), encoding="utf-8")
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    m = StorageManager(str(path), savePath=str(tmp_path / "out.json"))
    assert (len(m.GetStudents()), len(m.GetClassrooms()), len(m.GetActivities())) == (15, 5, 3)
    assert len(m.loadErrors) == 3


@pytest.mark.persistence
def test_PCorruptedFileBackedUpAndNotOverwritten(tmp_path):
    """整個檔案損毀 → 備份、回傳空資料庫，且拒絕覆蓋原檔。"""
    path = tmp_path / "broken.json"
    path.write_text("{ this is not json", encoding="utf-8")
    m = StorageManager(str(path))
    assert m.corrupted and m.GetCourses() == []
    assert m.Save() is False
    assert path.read_text(encoding="utf-8") == "{ this is not json"
    assert (tmp_path / "broken.json.corrupt.bak").exists()


@pytest.mark.persistence
def test_PMissingFileGivesEmptyDb(tmp_path):
    """檔案不存在 → 空資料庫，不當掉。"""
    m = StorageManager(str(tmp_path / "nope.json"))
    assert m.GetCourses() == [] and not m.corrupted
