"""F1 課程、學生與教室資料管理。

核心函式都是純函式：f(db, ...) -> (ok, code)，不碰檔案、不用全域變數，
可直接用 dict 測試。F1Manager 只是把純函式接上 DataManager 的存檔。

欄位一律以 04_data_format.json 為準：
  course : course_id, title, credits, required, teacher, classroom_id,
           capacity, enrolled_count, time_slots[{day, period}]
  student: student_id, name, department, max_credits, enrolled_courses
  room   : classroom_id, building_id, building_name, capacity, equipment
"""

import copy

from data_manager import DataManager

# ---- 規格常數（修改規格時請同步更新需求規格文件）----
VALID_DAYS = range(1, 8)  # 星期 1–7
VALID_PERIODS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c")
ALLOW_ZERO_CREDITS = False  # F1：學分必須為正整數。體育課 0 學分待團隊決議

# ---- 錯誤碼 ----
OK = "OK"
NOT_FOUND = "NOT_FOUND"
DUPLICATE_ID = "DUPLICATE_ID"
INVALID_FIELD = "INVALID_FIELD"
INVALID_CREDITS = "INVALID_CREDITS"
INVALID_CAPACITY = "INVALID_CAPACITY"
INVALID_DAY = "INVALID_DAY"
INVALID_PERIOD = "INVALID_PERIOD"
INVALID_TIME_SLOTS = "INVALID_TIME_SLOTS"
DUPLICATE_SLOT = "DUPLICATE_SLOT"
CLASSROOM_NOT_FOUND = "CLASSROOM_NOT_FOUND"
CAPACITY_EXCEEDS_ROOM = "CAPACITY_EXCEEDS_ROOM"
COURSE_NOT_FOUND = "COURSE_NOT_FOUND"
COURSE_HAS_STUDENTS = "COURSE_HAS_STUDENTS"
CLASSROOM_IN_USE = "CLASSROOM_IN_USE"
INVALID_STUDENT_COURSES = "INVALID_STUDENT_COURSES"

COURSE_FIELDS = (
    "title", "credits", "required", "teacher", "classroom_id",
    "capacity", "time_slots",
)
STUDENT_FIELDS = ("name", "department", "max_credits", "enrolled_courses")


# ======================================================================
# 小工具
# ======================================================================
def _is_int(value):
    """是整數但不是 bool（避免 True 被當成 1）。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_nonempty_str(value):
    return isinstance(value, str) and value.strip() != ""


def find_course(db, course_id):
    return next((c for c in db["courses"] if c["course_id"] == course_id), None)


def find_student(db, student_id):
    return next((s for s in db["students"] if s["student_id"] == student_id), None)


def find_classroom(db, classroom_id):
    return next((r for r in db["classrooms"] if r["classroom_id"] == classroom_id), None)


def count_enrolled(db, course_id):
    """學生資料中實際選修該課的人數。"""
    return sum(1 for s in db["students"] if course_id in s["enrolled_courses"])


def remaining_seats(course):
    """剩餘名額 = 人數上限 − 目前人數 (enrolled_count)。"""
    return course["capacity"] - course.get("enrolled_count", 0)


# ======================================================================
# 驗證（純函式，皆回傳 (ok, code)）
# ======================================================================
def validate_time_slots(time_slots):
    if not isinstance(time_slots, list) or len(time_slots) == 0:
        return False, INVALID_TIME_SLOTS
    seen = set()
    for slot in time_slots:
        if not isinstance(slot, dict) or "day" not in slot or "period" not in slot:
            return False, INVALID_TIME_SLOTS
        day, period = slot["day"], slot["period"]
        if not _is_int(day) or day not in VALID_DAYS:
            return False, INVALID_DAY
        if not isinstance(period, str) or period not in VALID_PERIODS:
            return False, INVALID_PERIOD
        if (day, period) in seen:
            return False, DUPLICATE_SLOT
        seen.add((day, period))
    return True, OK


def validate_course_fields(db, course):
    """檢查一份完整的課程資料（不含代號重複檢查）。"""
    if not _is_nonempty_str(course.get("course_id")):
        return False, INVALID_FIELD
    if not _is_nonempty_str(course.get("title")):
        return False, INVALID_FIELD
    if not isinstance(course.get("required"), bool):
        return False, INVALID_FIELD
    if not _is_nonempty_str(course.get("teacher")):
        return False, INVALID_FIELD

    credits = course.get("credits")
    min_credits = 0 if ALLOW_ZERO_CREDITS else 1
    if not _is_int(credits) or credits < min_credits:
        return False, INVALID_CREDITS

    capacity = course.get("capacity")
    if not _is_int(capacity) or capacity < 1:
        return False, INVALID_CAPACITY

    room = find_classroom(db, course.get("classroom_id"))
    if room is None:
        return False, CLASSROOM_NOT_FOUND
    if capacity > room["capacity"]:
        return False, CAPACITY_EXCEEDS_ROOM

    return validate_time_slots(course.get("time_slots"))


def validate_student_fields(db, student):
    if not _is_nonempty_str(student.get("student_id")):
        return False, INVALID_FIELD
    if not _is_nonempty_str(student.get("name")):
        return False, INVALID_FIELD
    if not _is_nonempty_str(student.get("department")):
        return False, INVALID_FIELD
    max_credits = student.get("max_credits")
    if not _is_int(max_credits) or max_credits < 1:
        return False, INVALID_CREDITS
    courses = student.get("enrolled_courses")
    if not isinstance(courses, list) or len(set(courses)) != len(courses):
        return False, INVALID_STUDENT_COURSES
    if any(find_course(db, cid) is None for cid in courses):
        return False, COURSE_NOT_FOUND
    return True, OK


# ======================================================================
# 教室
# ======================================================================
def add_classroom(db, room):
    if not _is_nonempty_str(room.get("classroom_id")):
        return False, INVALID_FIELD
    if find_classroom(db, room["classroom_id"]) is not None:
        return False, DUPLICATE_ID
    if not _is_int(room.get("capacity")) or room["capacity"] < 1:
        return False, INVALID_CAPACITY
    equipment = room.get("equipment", [])
    if not isinstance(equipment, list):
        return False, INVALID_FIELD
    new_room = {
        "classroom_id": room["classroom_id"],
        "building_id": room.get("building_id", ""),
        "building_name": room.get("building_name", ""),
        "capacity": room["capacity"],
        "equipment": list(equipment),
    }
    db["classrooms"].append(new_room)
    return True, OK


def delete_classroom(db, classroom_id):
    room = find_classroom(db, classroom_id)
    if room is None:
        return False, NOT_FOUND
    in_use = any(c["classroom_id"] == classroom_id for c in db["courses"]) or any(
        a["classroom_id"] == classroom_id for a in db["activities"]
    )
    if in_use:
        return False, CLASSROOM_IN_USE
    db["classrooms"].remove(room)
    return True, OK


# ======================================================================
# 課程
# ======================================================================
def add_course(db, course):
    """新增課程。enrolled_count 若未提供則為 0；成功才會改動 db。"""
    if not isinstance(course, dict):
        return False, INVALID_FIELD
    course_id = course.get("course_id")
    if _is_nonempty_str(course_id) and find_course(db, course_id) is not None:
        return False, DUPLICATE_ID
    ok, code = validate_course_fields(db, course)
    if not ok:
        return False, code

    new_course = {k: copy.deepcopy(course[k]) for k in ("course_id", *COURSE_FIELDS)}
    new_course["enrolled_count"] = 0
    db["courses"].append(new_course)
    return True, OK


def update_course(db, course_id, changes):
    """修改課程。course_id 不可變更；人數上限不得低於目前人數。"""
    course = find_course(db, course_id)
    if course is None:
        return False, NOT_FOUND
    if not isinstance(changes, dict) or not set(changes) <= set(COURSE_FIELDS):
        return False, INVALID_FIELD

    candidate = copy.deepcopy(course)
    candidate.update(copy.deepcopy(changes))
    ok, code = validate_course_fields(db, candidate)
    if not ok:
        return False, code
    if candidate["capacity"] < max(course.get("enrolled_count", 0), count_enrolled(db, course_id)):
        return False, INVALID_CAPACITY

    course.update(candidate)
    return True, OK


def delete_course(db, course_id):
    """已有學生選修（或 enrolled_count > 0）的課程不得刪除。"""
    course = find_course(db, course_id)
    if course is None:
        return False, NOT_FOUND
    if count_enrolled(db, course_id) > 0 or course.get("enrolled_count", 0) > 0:
        return False, COURSE_HAS_STUDENTS
    db["courses"].remove(course)
    return True, OK


def query_courses(db, course_id=None, teacher=None, day=None,
                  required=None, has_seats=None):
    """多條件查詢，條件之間為 AND；未指定(None)的條件不篩選。"""
    results = []
    for c in db["courses"]:
        if course_id is not None and c["course_id"] != course_id:
            continue
        if teacher is not None and c.get("teacher") != teacher:
            continue
        if day is not None and not any(s["day"] == day for s in c["time_slots"]):
            continue
        if required is not None and c.get("required") != required:
            continue
        if has_seats is not None and (remaining_seats(c) > 0) != has_seats:
            continue
        results.append(c)
    return results


# ======================================================================
# 學生
# ======================================================================
def add_student(db, student):
    if not isinstance(student, dict):
        return False, INVALID_FIELD
    student = dict(student)
    student.setdefault("enrolled_courses", [])
    student_id = student.get("student_id")
    if _is_nonempty_str(student_id) and find_student(db, student_id) is not None:
        return False, DUPLICATE_ID
    ok, code = validate_student_fields(db, student)
    if not ok:
        return False, code
    db["students"].append({k: copy.deepcopy(student[k]) for k in ("student_id", *STUDENT_FIELDS)})
    return True, OK


def update_student(db, student_id, changes):
    """修改學生基本資料。選課異動屬於 F2，這裡不允許改 enrolled_courses。"""
    student = find_student(db, student_id)
    if student is None:
        return False, NOT_FOUND
    allowed = {"name", "department", "max_credits"}
    if not isinstance(changes, dict) or not set(changes) <= allowed:
        return False, INVALID_FIELD
    candidate = {**student, **changes}
    ok, code = validate_student_fields(db, candidate)
    if not ok:
        return False, code
    student.update(changes)
    return True, OK


def delete_student(db, student_id):
    """刪除學生，並把其已選課程的 enrolled_count 各減 1（不低於 0）。"""
    student = find_student(db, student_id)
    if student is None:
        return False, NOT_FOUND
    for cid in student["enrolled_courses"]:
        course = find_course(db, cid)
        if course is not None:
            course["enrolled_count"] = max(0, course.get("enrolled_count", 0) - 1)
    db["students"].remove(student)
    return True, OK


def query_students(db, student_id=None, department=None, course_id=None):
    results = []
    for s in db["students"]:
        if student_id is not None and s["student_id"] != student_id:
            continue
        if department is not None and s.get("department") != department:
            continue
        if course_id is not None and course_id not in s["enrolled_courses"]:
            continue
        results.append(s)
    return results


# ======================================================================
# 接上存檔的包裝類別
# ======================================================================
class F1Manager(DataManager):
    """呼叫純函式後，成功才存檔；存檔失敗會回報 SAVE_FAILED。"""

    def _commit(self, result):
        ok, code = result
        if ok and not self._autosave():
            return False, "SAVE_FAILED"
        return ok, code

    def add_classroom(self, room):
        return self._commit(add_classroom(self.data, room))

    def delete_classroom(self, classroom_id):
        return self._commit(delete_classroom(self.data, classroom_id))

    def add_course(self, course):
        return self._commit(add_course(self.data, course))

    def update_course(self, course_id, changes):
        return self._commit(update_course(self.data, course_id, changes))

    def delete_course(self, course_id):
        return self._commit(delete_course(self.data, course_id))

    def query_courses(self, **conditions):
        return query_courses(self.data, **conditions)

    def add_student(self, student):
        return self._commit(add_student(self.data, student))

    def update_student(self, student_id, changes):
        return self._commit(update_student(self.data, student_id, changes))

    def delete_student(self, student_id):
        return self._commit(delete_student(self.data, student_id))

    def query_students(self, **conditions):
        return query_students(self.data, **conditions)
