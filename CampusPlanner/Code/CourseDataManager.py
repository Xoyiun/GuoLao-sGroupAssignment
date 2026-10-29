"""課程、學生與教室資料管理（功能 F1）。

核心函式都是純函式：function(database, ...) -> (ok, code)，不碰檔案、不用全域變數，
可直接用 dict 測試。CourseDataManager 將純函式接上 StorageManager 的存檔。

欄位使用 StorageManager 正規化後的內部格式；種子檔依 Reference/Formate 定義，
由 F6 載入時轉換：
  course : course_id, title, credits, required, teacher, classroom_id,
           capacity, enrolled_count, time_slots[{day, period}]
  student: student_id, name, department, max_credits, enrolled_courses
  room   : classroom_id, building_id, building_name, capacity, equipment
"""

import copy

# 錯誤代碼與全系統共用常數統一由 constants.py 管理並匯入
from Constants import (
    ALLOW_ZERO_CREDITS,
    CAPACITY_EXCEEDS_ROOM,
    CLASSROOM_IN_USE,
    CLASSROOM_NOT_FOUND,
    COURSE_FIELDS,
    COURSE_HAS_STUDENTS,
    COURSE_NOT_FOUND,
    DEFAULT_MAX_CREDITS,
    DUPLICATE_ID,
    DUPLICATE_SLOT,
    INVALID_CAPACITY,
    INVALID_CREDITS,
    INVALID_DAY,
    INVALID_FIELD,
    INVALID_PERIOD,
    INVALID_STUDENT_COURSES,
    INVALID_TIME_SLOTS,
    NOT_FOUND,
    OK,
    SAVE_FAILED,
    STUDENT_FIELDS,
    VALID_DAYS,
    VALID_PERIODS,
)

from StorageManager import StorageManager
from TimeSlotUtils import IsValidTimeSlotDay, GetWeekday


# ======================================================================
# 小工具
# ======================================================================
def IsInteger(value):
    """是整數但不是 bool（避免 True 被當成 1）。"""
    return isinstance(value, int) and not isinstance(value, bool)


def IsNonemptyString(value):
    """確認value不是空的"""
    return isinstance(value, str) and value.strip() != ""


def FindCourse(database, courseId):
    """依課程代號（例如 CS101）查找課程，回傳包含課名、教師、學分等完整資料。

    通用查找工具，不限 F1：F2 選課檢查、F3 課表、F5 課程篩選都要用代號找課程。
    """
    return next((course for course in database["courses"] if course["course_id"] == courseId), None)


def FindStudent(database, studentId):
    """用學號找學生，找不到回傳 None。

    通用查找工具，不限 F1：F2 選課檢查、F3 個人課表都要先找到學生。
    """
    return next((student for student in database["students"]
                 if student["student_id"] == studentId), None)


def FindClassroom(database, classroomId):
    """用教室代號找教室，找不到回傳 None。

    通用查找工具，不限 F1：F2 教室衝突檢查、F4 活動配置教室都會用到。
    """
    return next((classroom for classroom in database["classrooms"] if classroom["classroom_id"] == classroomId), None)


def CountEnrolled(database, courseId):
    """學生資料中實際選修該課的人數。

    F1 刪除課程時用來檢查是否有人選修；F2 名額限制驗證（人數是否已達 capacity）也會用到。
    """
    return sum(
        1 for student in database["students"]
        if courseId in student["enrolled_courses"]
    )


def RemainingSeats(course):
    """剩餘名額 = 人數上限 − 目前人數 (enrolled_count)。

    資料管理功能用於剩餘名額查詢；衝突檢查與課程篩選也會共用。
    """
    return course["capacity"] - course.get("enrolled_count", 0)


# ======================================================================
# 驗證（純函式，皆回傳 (ok, code)）
# ======================================================================
def ValidateTimeSlots(timeSlots):
    """防止種子檔的time_slot設定錯誤 或是防止未來add_course時設定錯誤

    F4 活動的 time_slots 格式跟課程相同（星期 1–7、節次 1–9, a, b, c），新增活動時可共用。
    """
    if not isinstance(timeSlots, list) or len(timeSlots) == 0:
        return False, INVALID_TIME_SLOTS
    seen = set()
    for slot in timeSlots:
        if not isinstance(slot, dict) or "day" not in slot or "period" not in slot:
            return False, INVALID_TIME_SLOTS
        day, period = slot["day"], slot["period"]
        if not IsValidTimeSlotDay(day):
            return False, INVALID_DAY
        if not isinstance(period, str) or period not in VALID_PERIODS:
            return False, INVALID_PERIOD
        if (day, period) in seen:
            return False, DUPLICATE_SLOT
        seen.add((day, period))
    return True, OK


def ValidateCourseFields(database, course):
    """檢查一份完整的課程資料（不含代號重複檢查）。"""
    if not IsNonemptyString(course.get("course_id")):
        return False, INVALID_FIELD
    if not IsNonemptyString(course.get("title")):
        return False, INVALID_FIELD
    if not isinstance(course.get("required"), bool):
        return False, INVALID_FIELD
    if not IsNonemptyString(course.get("teacher")):
        return False, INVALID_FIELD

    credits = course.get("credits")
    minCredits = 0 if ALLOW_ZERO_CREDITS or course.get("course_type") == "event" else 1
    if not IsInteger(credits) or credits < minCredits:
        return False, INVALID_CREDITS

    capacity = course.get("capacity")
    if not IsInteger(capacity) or capacity < 1:
        return False, INVALID_CAPACITY

    room = FindClassroom(database, course.get("classroom_id"))
    if room is None:
        return False, CLASSROOM_NOT_FOUND
    if capacity > room["capacity"]:
        return False, CAPACITY_EXCEEDS_ROOM

    return ValidateTimeSlots(course.get("time_slots"))


def ValidateStudentFields(database, student):
    """檢查學生資料"""
    if not IsNonemptyString(student.get("student_id")):
        return False, INVALID_FIELD
    if not IsNonemptyString(student.get("name")):
        return False, INVALID_FIELD
    if not IsNonemptyString(student.get("department")):
        return False, INVALID_FIELD
    maxCredits = student.get("max_credits")
    if not IsInteger(maxCredits) or maxCredits < 1:
        return False, INVALID_CREDITS
    courses = student.get("enrolled_courses")
    if not isinstance(courses, list) or len(set(courses)) != len(courses):
        return False, INVALID_STUDENT_COURSES
    if any(FindCourse(database, courseId) is None for courseId in courses):
        return False, COURSE_NOT_FOUND
    return True, OK


# ======================================================================
# 教室
# ======================================================================
def AddClassroom(database, room):
    """新增教室資料。

    輸入：
        room: 教室字典，包含 classroom_id, capacity, equipment 等欄位
    回傳：
        (ok, code): 成功為 (True, OK)，失敗為 (False, 錯誤碼)
    """
    if not IsNonemptyString(room.get("classroom_id")):
        return False, INVALID_FIELD
    if FindClassroom(database, room["classroom_id"]) is not None:
        return False, DUPLICATE_ID
    if not IsInteger(room.get("capacity")) or room["capacity"] < 1:
        return False, INVALID_CAPACITY
    equipment = room.get("equipment", [])
    if not isinstance(equipment, list) or not all(isinstance(equipmentItem, str) for equipmentItem in equipment):
        return False, INVALID_FIELD
    newRoom = {
        "classroom_id": room["classroom_id"],
        "building_id": room.get("building_id", ""),
        "building_name": room.get("building_name", ""),
        "capacity": room["capacity"],
        "equipment": list(equipment),
    }
    database["classrooms"].append(newRoom)
    return True, OK


def DeleteClassroom(database, classroomId):
    """刪除教室。

    輸入：
        classroom_id: 欲刪除的教室代號
    回傳：
        (ok, code): 成功為 (True, OK)，失敗為 (False, 錯誤碼)
    """
    room = FindClassroom(database, classroomId)
    if room is None:
        return False, NOT_FOUND
    inUse = any(course["classroom_id"] == classroomId for course in database["courses"])  # 含 event 活動
    if inUse:
        return False, CLASSROOM_IN_USE
    database["classrooms"].remove(room)
    return True, OK


# ======================================================================
# 課程
# ======================================================================
def AddCourse(database, course):
    """新增課程。enrolled_count 若未提供則為 0；成功才會改動 db。

    輸入：
        course: 課程字典，包含 course_id, title, credits, required, teacher, classroom_id, capacity, time_slots
    回傳：
        (ok, code): 成功為 (True, OK)，失敗為 (False, 錯誤碼)
    """
    if not isinstance(course, dict):
        return False, INVALID_FIELD
    courseId = course.get("course_id")
    if IsNonemptyString(courseId) and FindCourse(database, courseId) is not None:
        return False, DUPLICATE_ID
    ok, code = ValidateCourseFields(database, course)
    if not ok:
        return False, code

    newCourse = {fieldName: copy.deepcopy(course[fieldName])
                 for fieldName in ("course_id", *COURSE_FIELDS)}
    newCourse["enrolled_count"] = 0
    database["courses"].append(newCourse)
    return True, OK


def UpdateCourse(database, courseId, changes):
    """修改課程。course_id 不可變更；人數上限不得低於目前人數。

    輸入：
        course_id: 欲修改的課程代號
        changes: 欲異動的欄位字典（例如 {"capacity": 50}）
    回傳：
        (ok, code): 成功為 (True, OK)，失敗為 (False, 錯誤碼)
    """
    course = FindCourse(database, courseId)
    if course is None:
        return False, NOT_FOUND
    if not isinstance(changes, dict) or not set(changes) <= set(COURSE_FIELDS):
        return False, INVALID_FIELD

    candidate = copy.deepcopy(course)
    candidate.update(copy.deepcopy(changes))
    ok, code = ValidateCourseFields(database, candidate)
    if not ok:
        return False, code
    if candidate["capacity"] < max(course.get("enrolled_count", 0), CountEnrolled(database, courseId)):
        return False, INVALID_CAPACITY

    course.update(candidate)
    return True, OK


def DeleteCourse(database, courseId):
    """已有學生選修（或 enrolled_count > 0）的課程不得刪除。

    輸入：
        course_id: 欲刪除的課程代號
    回傳：
        (ok, code): 成功為 (True, OK)，失敗為 (False, 錯誤碼)
    """
    course = FindCourse(database, courseId)
    if course is None:
        return False, NOT_FOUND
    if CountEnrolled(database, courseId) > 0 or course.get("enrolled_count", 0) > 0:
        return False, COURSE_HAS_STUDENTS
    database["courses"].remove(course)
    return True, OK


def QueryCourses(database, courseId=None, teacher=None, day=None,
                  required=None, hasSeats=None):
    """多條件查詢，條件之間為 AND；未指定（None）的條件不篩選。

    輸入：
        courseId: 指定課程代號
        teacher: 指定授課教師
        day: 指定上課星期 (1-7)
        required: 指定必修 (True) 或選修 (False)
        hasSeats: 指定是否僅保留有名額 (True/False)
    回傳：
        符合條件的課程字典清單
    """
    results = []
    for course in database["courses"]:
        if courseId is not None and course["course_id"] != courseId:
            continue
        if teacher is not None and course.get("teacher") != teacher:
            continue
        if day is not None and not any(
            GetWeekday(timeSlot["day"]) == day for timeSlot in course["time_slots"]
        ):
            continue
        if required is not None and course.get("required") != required:
            continue
        if hasSeats is not None and (RemainingSeats(course) > 0) != hasSeats:
            continue
        results.append(course)
    return results


# ======================================================================
# 學生
# ======================================================================
def AddStudent(database, student):
    """新增學生資料。

    輸入：
        student: 學生字典，包含 student_id, name, department, max_credits 等欄位
    回傳：
        (ok, code): 成功為 (True, OK)，失敗為 (False, 錯誤碼)
    """
    if not isinstance(student, dict):
        return False, INVALID_FIELD
    student = dict(student)
    student.setdefault("enrolled_courses", [])
    studentId = student.get("student_id")
    if IsNonemptyString(studentId) and FindStudent(database, studentId) is not None:
        return False, DUPLICATE_ID
    ok, code = ValidateStudentFields(database, student)
    if not ok:
        return False, code
    database["students"].append({fieldName: copy.deepcopy(student[fieldName]) for fieldName in (
        "student_id", *STUDENT_FIELDS)})
    return True, OK


def UpdateStudent(database, studentId, changes):
    """修改學生基本資料。選課異動屬於 F2，這裡不允許改 enrolled_courses。

    輸入：
        student_id: 欲修改的學號
        changes: 欲異動的欄位字典（如 name, department, max_credits）
    回傳：
        (ok, code): 成功為 (True, OK)，失敗為 (False, 錯誤碼)
    """
    student = FindStudent(database, studentId)
    if student is None:
        return False, NOT_FOUND
    allowed = {"name", "department", "max_credits"}
    if not isinstance(changes, dict) or not set(changes) <= allowed:
        return False, INVALID_FIELD
    candidate = {**student, **changes}
    ok, code = ValidateStudentFields(database, candidate)
    if not ok:
        return False, code
    student.update(changes)
    return True, OK


def DeleteStudent(database, studentId):
    """刪除學生，並把其已選課程的 enrolled_count 各減 1（不低於 0）。

    輸入：
        student_id: 欲刪除的學號
    回傳：
        (ok, code): 成功為 (True, OK)，失敗為 (False, 錯誤碼)
    """
    student = FindStudent(database, studentId)
    if student is None:
        return False, NOT_FOUND
    for courseId in student["enrolled_courses"]:
        course = FindCourse(database, courseId)
        if course is not None:
            course["enrolled_count"] = max(
                0, course.get("enrolled_count", 0) - 1)
    database["students"].remove(student)
    return True, OK


def QueryStudents(database, studentId=None, department=None, courseId=None):
    """多條件查詢學生。

    輸入：
        student_id: 指定學號
        department: 指定系級
        course_id: 指定已選修之課程代號
    回傳：
        符合條件的學生字典清單
    """
    results = []
    for student in database["students"]:
        if studentId is not None and student["student_id"] != studentId:
            continue
        if department is not None and student.get("department") != department:
            continue
        if courseId is not None and courseId not in student["enrolled_courses"]:
            continue
        results.append(student)
    return results


# ======================================================================
# 接上存檔的包裝類別
# ======================================================================
class CourseDataManager(StorageManager):
    """呼叫純函式後，成功才存檔；存檔失敗會回報 SAVE_FAILED。"""

    def SaveIfSuccessful(self, result):
        """成功才存檔，存檔失敗回傳 (False, "SAVE_FAILED")。

        實際存檔由 storageManager.py 負責，這裡只負責接合資料管理操作。
        """
        ok, code = result
        if ok and not self.AutoSave():
            return False, "SAVE_FAILED"
        return ok, code

    # ---- 查詢與查找介面（供 Main 或其他模組呼叫，隱藏 self.data 內部結構）----
    def FindCourse(self, courseId: str):
        """依課程代號查找課程字典，找不到回傳 None。"""
        return FindCourse(self.data, courseId)

    def FindStudent(self, studentId: str):
        """依學號查找學生字典，找不到回傳 None。"""
        return FindStudent(self.data, studentId)

    def FindClassroom(self, classroomId: str):
        """依教室代號查找教室字典，找不到回傳 None。"""
        return FindClassroom(self.data, classroomId)

    def CountEnrolled(self, courseId: str) -> int:
        """計算指定課程的實際修課人數。"""
        return CountEnrolled(self.data, courseId)

    def GetClassroomCapacity(self, classroomId: str):
        """取得指定教室的容量上限，找不到教室時回傳 None。"""
        room = FindClassroom(self.data, classroomId)
        return room["capacity"] if room else None

    def GetCourseStudentCount(self, courseId: str) -> int:
        """取得課程的學生人數（取 enrolled_count 與實際選課學生人數之較大者）。"""
        course = FindCourse(self.data, courseId)
        if not course:
            return 0
        return max(course.get("enrolled_count", 0), CountEnrolled(self.data, courseId))

    def AddClassroom(self, room):
        return self.SaveIfSuccessful(AddClassroom(self.data, room))

    def DeleteClassroom(self, classroomId):
        return self.SaveIfSuccessful(DeleteClassroom(self.data, classroomId))

    def AddCourse(self, course):
        return self.SaveIfSuccessful(AddCourse(self.data, course))

    def UpdateCourse(self, courseId, changes):
        return self.SaveIfSuccessful(UpdateCourse(self.data, courseId, changes))

    def DeleteCourse(self, courseId):
        return self.SaveIfSuccessful(DeleteCourse(self.data, courseId))

    def QueryCourses(self, **conditions):
        return QueryCourses(self.data, **conditions)

    def AddStudent(self, student):
        return self.SaveIfSuccessful(AddStudent(self.data, student))

    def UpdateStudent(self, studentId, changes):
        return self.SaveIfSuccessful(UpdateStudent(self.data, studentId, changes))

    def DeleteStudent(self, studentId):
        return self.SaveIfSuccessful(DeleteStudent(self.data, studentId))

    def QueryStudents(self, **conditions):
        return QueryStudents(self.data, **conditions)
