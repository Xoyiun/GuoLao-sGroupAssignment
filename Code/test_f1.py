"""F1 課程、學生與教室資料管理 的自動化測試。

分類（用 pytest 標記，可分開執行與計數）：
  normal      正常案例   10 個   python -m pytest -m normal -v
  boundary    邊界案例   10 個   python -m pytest -m boundary -v
  error       錯誤案例   10 個   python -m pytest -m error -v
  extra       補充案例（參數化與較細的檢查，不計入上面 30 個）
  persistence 存檔與容錯載入（F6 相關，不計入上面 30 個）
  acceptance  F1 驗收條件（資料量）

測試資料 = 種子檔 04_data_format.json（每個測試讀進記憶體後複製一份，不會被改動）
          + 每個測試自己組出來的輸入（new_course / new_student）。
"""

import copy
import json
import os
import shutil

import pytest

import f1_manager as f1
from data_manager import DataManager, load_db

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, "04_data_format.json")
if not os.path.exists(SEED):  # 找不到就往上一層找
    SEED = os.path.join(os.path.dirname(HERE), "04_data_format.json")


@pytest.fixture
def db():
    """每個測試拿到一份全新的記憶體資料，完全不碰檔案。"""
    assert os.path.exists(SEED), f"找不到種子檔：{SEED}"
    data, _errors, _corrupted = load_db(SEED)
    return copy.deepcopy(data)


def new_course(**overrides):
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


def new_student(**overrides):
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
def test_seed_meets_acceptance_counts(db):
    """種子資料至少有 20 門課、15 名學生、5 間教室。"""
    assert len(db["courses"]) >= 20
    assert len(db["students"]) >= 15
    assert len(db["classrooms"]) >= 5


# ======================================================================
# 正常案例（10）：合法輸入，預期成功
# ======================================================================
@pytest.mark.normal
def test_n01_add_course(db):
    """新增一門合法課程 → 成功，且初始人數為 0。"""
    assert f1.add_course(db, new_course()) == (True, f1.OK)
    assert f1.find_course(db, "NEW101")["enrolled_count"] == 0


@pytest.mark.normal
def test_n02_update_course(db):
    """修改課程的教師與學分 → 成功，資料確實更新。"""
    f1.add_course(db, new_course())
    assert f1.update_course(db, "NEW101", {"teacher": "新老師", "credits": 2}) == (True, f1.OK)
    course = f1.find_course(db, "NEW101")
    assert (course["teacher"], course["credits"]) == ("新老師", 2)


@pytest.mark.normal
def test_n03_delete_course_without_students(db):
    """刪除沒有學生選修的課程 → 成功，課程消失。"""
    f1.add_course(db, new_course())
    assert f1.delete_course(db, "NEW101") == (True, f1.OK)
    assert f1.find_course(db, "NEW101") is None


@pytest.mark.normal
def test_n04_add_student(db):
    """新增一位合法學生 → 成功，且選課清單為空。"""
    assert f1.add_student(db, new_student()) == (True, f1.OK)
    assert f1.find_student(db, "S99999")["enrolled_courses"] == []


@pytest.mark.normal
def test_n05_update_student(db):
    """修改學生姓名與學分上限 → 成功，資料確實更新。"""
    f1.add_student(db, new_student())
    assert f1.update_student(db, "S99999", {"name": "改名", "max_credits": 20}) == (True, f1.OK)
    student = f1.find_student(db, "S99999")
    assert (student["name"], student["max_credits"]) == ("改名", 20)


@pytest.mark.normal
def test_n06_delete_student_decrements_enrolled_count(db):
    """刪除已選 CS101 的學生 → 成功，CS101 的 enrolled_count 減 1。"""
    before = f1.find_course(db, "CS101")["enrolled_count"]
    assert f1.delete_student(db, "S10901") == (True, f1.OK)
    assert f1.find_student(db, "S10901") is None
    assert f1.find_course(db, "CS101")["enrolled_count"] == before - 1


@pytest.mark.normal
def test_n07_query_by_teacher(db):
    """依教師查詢「林教授」→ 只有 CS101 與 CS203。"""
    ids = {c["course_id"] for c in f1.query_courses(db, teacher="林教授")}
    assert ids == {"CS101", "CS203"}


@pytest.mark.normal
def test_n08_query_by_day(db):
    """依星期查詢週五 → 包含 MA101、CS201、GE102、PE101，不含週一的 CS101。"""
    ids = {c["course_id"] for c in f1.query_courses(db, day=5)}
    assert {"MA101", "CS201", "GE102", "PE101"} <= ids
    assert "CS101" not in ids


@pytest.mark.normal
def test_n09_query_has_seats(db):
    """依剩餘名額查詢已額滿 → 包含 GE101、PE101，不含還有空位的 CS101。"""
    full = {c["course_id"] for c in f1.query_courses(db, has_seats=False)}
    assert {"GE101", "PE101"} <= full
    assert "CS101" not in full


@pytest.mark.normal
def test_n10_add_classroom(db):
    """新增一間合法教室 → 成功，且可被查到。"""
    room = {"classroom_id": "X-1", "capacity": 10, "equipment": ["projector"]}
    assert f1.add_classroom(db, room) == (True, f1.OK)
    assert f1.find_classroom(db, "X-1")["capacity"] == 10


# ======================================================================
# 邊界案例（10）：剛好在合法範圍邊緣，預期成功或行為正確
# ======================================================================
@pytest.mark.boundary
def test_b01_capacity_exactly_one(db):
    """課程人數上限剛好 1（最小合法值）→ 成功。"""
    assert f1.add_course(db, new_course(capacity=1)) == (True, f1.OK)


@pytest.mark.boundary
def test_b02_capacity_equals_classroom_capacity(db):
    """課程人數上限剛好等於教室容量（TR-310 為 60）→ 成功。"""
    assert f1.add_course(db, new_course(capacity=60)) == (True, f1.OK)


@pytest.mark.boundary
def test_b03_credits_exactly_one(db):
    """學分剛好 1（最小合法值）→ 成功。"""
    assert f1.add_course(db, new_course(credits=1)) == (True, f1.OK)


@pytest.mark.boundary
def test_b04_day_1_and_day_7(db):
    """星期 1 與星期 7（合法範圍的兩端）同時出現 → 成功。"""
    slots = [{"day": 1, "period": "1"}, {"day": 7, "period": "1"}]
    assert f1.add_course(db, new_course(time_slots=slots)) == (True, f1.OK)


@pytest.mark.boundary
def test_b05_period_9(db):
    """節次 "9"（最後一個數字節次）→ 成功。"""
    assert f1.add_course(db, new_course(time_slots=[{"day": 1, "period": "9"}]))[0]


@pytest.mark.boundary
def test_b06_period_a(db):
    """節次 "a"（第一個字母節次）→ 成功。"""
    assert f1.add_course(db, new_course(time_slots=[{"day": 1, "period": "a"}]))[0]


@pytest.mark.boundary
def test_b07_period_c(db):
    """節次 "c"（最後一個合法節次）→ 成功。"""
    assert f1.add_course(db, new_course(time_slots=[{"day": 1, "period": "c"}]))[0]


@pytest.mark.boundary
def test_b08_query_no_match_returns_empty(db):
    """查詢不存在的教師 → 回傳空清單，不報錯。"""
    assert f1.query_courses(db, teacher="不存在的人") == []


@pytest.mark.boundary
def test_b09_query_without_conditions_returns_all(db):
    """不給任何查詢條件 → 回傳全部課程。"""
    assert len(f1.query_courses(db)) == len(db["courses"])


@pytest.mark.boundary
def test_b10_update_capacity_down_to_enrolled_count(db):
    """把人數上限降到剛好等於目前人數 → 成功（再低一個才會被拒絕）。"""
    f1.add_course(db, new_course())
    db["courses"][-1]["enrolled_count"] = 10
    assert f1.update_course(db, "NEW101", {"capacity": 10}) == (True, f1.OK)


# ======================================================================
# 錯誤案例（10）：違規輸入，預期被拒絕並回傳正確錯誤碼
# ======================================================================
@pytest.mark.error
def test_e01_duplicate_course_id(db):
    """新增已存在的課程代號 CS101 → DUPLICATE_ID。"""
    assert f1.add_course(db, new_course(course_id="CS101")) == (False, f1.DUPLICATE_ID)


@pytest.mark.error
def test_e02_duplicate_student_id(db):
    """新增已存在的學號 S10901 → DUPLICATE_ID。"""
    assert f1.add_student(db, new_student(student_id="S10901")) == (False, f1.DUPLICATE_ID)


@pytest.mark.error
def test_e03_invalid_period(db):
    """節次 "d"（超出 1–9、a、b、c）→ INVALID_PERIOD。"""
    r = f1.add_course(db, new_course(time_slots=[{"day": 1, "period": "d"}]))
    assert r == (False, f1.INVALID_PERIOD)


@pytest.mark.error
def test_e04_invalid_day(db):
    """星期 8（超出 1–7）→ INVALID_DAY。"""
    r = f1.add_course(db, new_course(time_slots=[{"day": 8, "period": "1"}]))
    assert r == (False, f1.INVALID_DAY)


@pytest.mark.error
def test_e05_invalid_credits_zero(db):
    """學分為 0（必須是正整數）→ INVALID_CREDITS。"""
    assert f1.add_course(db, new_course(credits=0)) == (False, f1.INVALID_CREDITS)


@pytest.mark.error
def test_e06_invalid_capacity_zero(db):
    """人數上限為 0（不得小於 1）→ INVALID_CAPACITY。"""
    assert f1.add_course(db, new_course(capacity=0)) == (False, f1.INVALID_CAPACITY)


@pytest.mark.error
def test_e07_capacity_exceeds_classroom(db):
    """人數上限 61 超過 TR-310 的容量 60 → CAPACITY_EXCEEDS_ROOM。"""
    assert f1.add_course(db, new_course(capacity=61)) == (False, f1.CAPACITY_EXCEEDS_ROOM)


@pytest.mark.error
def test_e08_classroom_not_found(db):
    """使用不存在的教室 → CLASSROOM_NOT_FOUND。"""
    assert f1.add_course(db, new_course(classroom_id="ZZ-999")) == (False, f1.CLASSROOM_NOT_FOUND)


@pytest.mark.error
def test_e09_delete_course_with_students_rejected(db):
    """刪除已有學生選修的 CS101 → COURSE_HAS_STUDENTS，且課程仍在。"""
    assert f1.delete_course(db, "CS101") == (False, f1.COURSE_HAS_STUDENTS)
    assert f1.find_course(db, "CS101") is not None


@pytest.mark.error
def test_e10_empty_time_slots(db):
    """上課時段為空清單 → INVALID_TIME_SLOTS。"""
    assert f1.add_course(db, new_course(time_slots=[])) == (False, f1.INVALID_TIME_SLOTS)


# ======================================================================
# 補充案例（不計入 10/10/10）：更多數值與較細的規則
# ======================================================================
@pytest.mark.extra
@pytest.mark.parametrize("period", ["d", "0", "10", "", "A", 2])
def test_x_invalid_period_values(db, period):
    r = f1.add_course(db, new_course(time_slots=[{"day": 1, "period": period}]))
    assert r == (False, f1.INVALID_PERIOD)


@pytest.mark.extra
@pytest.mark.parametrize("day", [0, 8, -1, "1", True])
def test_x_invalid_day_values(db, day):
    r = f1.add_course(db, new_course(time_slots=[{"day": day, "period": "1"}]))
    assert r == (False, f1.INVALID_DAY)


@pytest.mark.extra
@pytest.mark.parametrize("credits", [0, -1, 2.5, "3", True, None])
def test_x_invalid_credits_values(db, credits):
    assert f1.add_course(db, new_course(credits=credits)) == (False, f1.INVALID_CREDITS)


@pytest.mark.extra
@pytest.mark.parametrize("capacity", [0, -5, "30", 1.5, None])
def test_x_invalid_capacity_values(db, capacity):
    assert f1.add_course(db, new_course(capacity=capacity)) == (False, f1.INVALID_CAPACITY)


@pytest.mark.extra
def test_x_duplicate_time_slot(db):
    dup = [{"day": 1, "period": "1"}, {"day": 1, "period": "1"}]
    assert f1.add_course(db, new_course(time_slots=dup)) == (False, f1.DUPLICATE_SLOT)


@pytest.mark.extra
def test_x_multiple_time_slots_accepted(db):
    slots = [{"day": 1, "period": "1"}, {"day": 3, "period": "c"}]
    assert f1.add_course(db, new_course(time_slots=slots))[0]


@pytest.mark.extra
def test_x_query_by_required_and_course_id(db):
    assert all(c["required"] for c in f1.query_courses(db, required=True))
    assert [c["course_id"] for c in f1.query_courses(db, course_id="CS103")] == ["CS103"]


@pytest.mark.extra
def test_x_failed_add_does_not_modify_db(db):
    before = copy.deepcopy(db)
    f1.add_course(db, new_course(credits=0))
    assert db == before


@pytest.mark.extra
def test_x_delete_course_listed_student_but_zero_count(db):
    f1.add_course(db, new_course())
    f1.add_student(db, new_student(enrolled_courses=["NEW101"]))
    assert f1.delete_course(db, "NEW101") == (False, f1.COURSE_HAS_STUDENTS)


@pytest.mark.extra
def test_x_delete_missing_course(db):
    assert f1.delete_course(db, "NOPE") == (False, f1.NOT_FOUND)


@pytest.mark.extra
def test_x_update_missing_course_and_bad_field(db):
    assert f1.update_course(db, "NOPE", {"title": "x"}) == (False, f1.NOT_FOUND)
    assert f1.update_course(db, "CS101", {"course_id": "X"}) == (False, f1.INVALID_FIELD)


@pytest.mark.extra
def test_x_update_capacity_below_enrolled_rejected(db):
    assert f1.update_course(db, "CS101", {"capacity": 10}) == (False, f1.INVALID_CAPACITY)


@pytest.mark.extra
def test_x_student_with_unknown_course(db):
    r = f1.add_student(db, new_student(enrolled_courses=["NOPE"]))
    assert r == (False, f1.COURSE_NOT_FOUND)


@pytest.mark.extra
def test_x_student_invalid_max_credits(db):
    assert f1.add_student(db, new_student(max_credits=0)) == (False, f1.INVALID_CREDITS)


@pytest.mark.extra
def test_x_delete_classroom_in_use(db):
    assert f1.delete_classroom(db, "TR-310") == (False, f1.CLASSROOM_IN_USE)


# ======================================================================
# 存檔與容錯載入（F6 相關，不計入 10/10/10）
# ======================================================================
@pytest.mark.persistence
def test_p_save_goes_to_save_path_and_seed_untouched(tmp_path):
    """存檔寫到工作檔，種子檔位元組完全不變；重新載入後資料還在。"""
    seed_copy = tmp_path / "seed.json"
    shutil.copy(SEED, seed_copy)
    seed_bytes = seed_copy.read_bytes()
    work = tmp_path / "work.json"

    m = f1.F1Manager(str(seed_copy), save_path=str(work))
    assert m.add_course(new_course()) == (True, f1.OK)

    assert seed_copy.read_bytes() == seed_bytes
    assert any(c["course_id"] == "NEW101" for c in json.loads(work.read_text("utf-8"))["courses"])
    again = f1.F1Manager(str(work), save_path=str(work))
    assert f1.find_course(again.data, "NEW101") is not None


# ▼▼▼ 【Claude 新增 10/16】驗證「沒指定 save_path 時不會覆蓋種子檔」（對應 data_manager.py 的預設存檔路徑修改）
@pytest.mark.persistence
def test_p_default_save_path_never_overwrites_seed(tmp_path):
    """沒指定 save_path 時，預設存到同資料夾的 db.json，種子檔位元組完全不變。"""
    seed_copy = tmp_path / "seed.json"
    shutil.copy(SEED, seed_copy)
    seed_bytes = seed_copy.read_bytes()

    m = f1.F1Manager(str(seed_copy))  # 故意不給 save_path
    assert m.add_course(new_course()) == (True, f1.OK)

    assert seed_copy.read_bytes() == seed_bytes
    assert (tmp_path / "db.json").exists()
# ▲▲▲ 【Claude 新增】到此結束


@pytest.mark.persistence
def test_p_autosave_off_writes_nothing(tmp_path):
    """autosave=False 時，新增資料不會產生任何檔案。"""
    work = tmp_path / "work.json"
    m = f1.F1Manager(SEED, save_path=str(work), autosave=False)
    m.add_course(new_course())
    assert not work.exists()


@pytest.mark.persistence
def test_p_bad_record_skipped_not_crash(tmp_path):
    """檔案中有缺欄位或型別錯誤的單筆資料 → 跳過並記錄，程式不當掉。"""
    with open(SEED, encoding="utf-8") as f:
        raw = json.load(f)
    raw["courses"].append({"course_id": "BROKEN"})  # 缺欄位
    raw["courses"].append("not a dict")
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    m = DataManager(str(path), save_path=str(tmp_path / "out.json"))
    assert len(m.get_courses()) == 20
    assert len(m.load_errors) == 2


@pytest.mark.persistence
def test_p_corrupted_file_backed_up_and_not_overwritten(tmp_path):
    """整個檔案損毀 → 備份、回傳空資料庫，且拒絕覆蓋原檔。"""
    path = tmp_path / "broken.json"
    path.write_text("{ this is not json", encoding="utf-8")
    m = DataManager(str(path))
    assert m.corrupted and m.get_courses() == []
    assert m.save() is False
    assert path.read_text(encoding="utf-8") == "{ this is not json"
    assert (tmp_path / "broken.json.corrupt.bak").exists()


@pytest.mark.persistence
def test_p_missing_file_gives_empty_db(tmp_path):
    """檔案不存在 → 空資料庫，不當掉。"""
    m = DataManager(str(tmp_path / "nope.json"))
    assert m.get_courses() == [] and not m.corrupted
