"""main.py（F1 命令列介面）的自動化測試。

用假的 ask（照順序回傳預先寫好的輸入）和 show（把輸出收進清單）取代鍵盤和螢幕，
所以不需要人工輸入。每個測試都在 tmp_path 裡放一份種子檔複本，不會碰到真正的檔案。

執行：python -m pytest test_main.py -v      只跑這類：python -m pytest -m cli -v
"""

import json
import os
import shutil

import pytest

import Main as main  # 搬到 CampusPlanner：原本是 import main

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(os.path.dirname(HERE), "UserData", "04_data_format.json")  # 修改：種子檔在 CampusPlanner/UserData

pytestmark = pytest.mark.cli  # 這個檔案的測試全部標成 cli


def scripted(inputs):
    """回傳一個假的 ask：每呼叫一次就給下一筆輸入；用完時丟 EOFError（等同使用者按 Ctrl+Z）。"""
    remaining = iter(inputs)

    def ask(prompt=""):
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError from None

    return ask


def run_session(data_dir, inputs):
    """跑一次完整的 main()，回傳所有輸出合成的字串。"""
    output = []
    main.main(ask=scripted(inputs), show=output.append, data_dir=str(data_dir))
    return "\n".join(output)


@pytest.fixture
def data_dir(tmp_path):
    shutil.copy(SEED, tmp_path / main.SEED_FILE)
    return tmp_path


# 新增一門合法課程時要輸入的內容（選單 1 之後）
NEW_COURSE = ["NEW101", "測試課程", "3", "選", "測試教授", "TR-310", "30", "1-1,1-2"]


# ======================================================================
# 解析輸入
# ======================================================================
def test_parse_time_slots_multiple_and_uppercase():
    """多個時段、有空白、節次大寫 → 正確轉成 dict 清單，節次變小寫。"""
    assert main.parse_time_slots("2-3, 2-4,4-A") == [
        {"day": 2, "period": "3"},
        {"day": 2, "period": "4"},
        {"day": 4, "period": "a"},
    ]


@pytest.mark.parametrize("text", ["", "2", "2-3,", "2-3-4", "-3", "2-"])
def test_parse_time_slots_bad_format_returns_text(text):
    """格式不對 → 原樣回傳字串（交給 F1_DataManager 回報 INVALID_TIME_SLOTS）。"""
    assert main.parse_time_slots(text) == text


def test_parse_int_and_bool():
    assert main.parse_int(" 3 ") == 3
    assert main.parse_int("abc") == "abc"
    assert main.parse_bool("必修") is True
    assert main.parse_bool("選") is False
    assert main.parse_bool("不知道") is None


def test_format_time_slots_groups_by_day():
    """同一天的節次合併並依節次順序排列（a 排在 9 後面）。"""
    slots = [{"day": 4, "period": "a"}, {"day": 2, "period": "4"}, {"day": 2, "period": "3"}, {"day": 4, "period": "9"}]
    assert main.format_time_slots(slots) == "星期二 3,4 節；星期四 9,a 節"


# ======================================================================
# 輸出訊息符合規格書格式
# ======================================================================
def test_add_course_success_message(data_dir):
    out = run_session(data_dir, ["1", *NEW_COURSE, "0"])
    assert "[成功] 課程 [NEW101] 測試課程 新增成功。" in out


def test_add_course_duplicate_message(data_dir):
    """重複代號 → 規格書的錯誤訊息。輸入小寫 cs101 也會被轉成 CS101。"""
    out = run_session(data_dir, ["1", "cs101", *NEW_COURSE[1:], "0"])
    assert "[錯誤] 新增失敗：課程代號 CS101 已重複存在。" in out


def test_delete_course_with_students_message(data_dir):
    """已有學生選修的課程 → 拒絕刪除並顯示人數（CS101 的 enrolled_count 是 45）。"""
    out = run_session(data_dir, ["3", "CS101", "y", "0"])
    assert "[錯誤] 刪除失敗：課程 CS101 目前已有 45 名學生選修，請先辦理退選。" in out


# ======================================================================
# 驗收條件：拒絕非法節次、無效學分；錯誤輸入不會當掉
# ======================================================================
@pytest.mark.parametrize("period", ["d", "0"])
def test_add_course_rejects_illegal_period(data_dir, period):
    course = NEW_COURSE[:-1] + [f"1-{period}"]
    out = run_session(data_dir, ["1", *course, "0"])
    assert "[錯誤] 新增失敗：節次必須為 1–9、a、b、c。" in out


@pytest.mark.parametrize("credits", ["0", "-1", "abc", ""])
def test_add_course_rejects_invalid_credits(data_dir, credits):
    course = NEW_COURSE[:2] + [credits] + NEW_COURSE[3:]
    out = run_session(data_dir, ["1", *course, "0"])
    assert "[錯誤] 新增失敗：學分必須為正整數。" in out


def test_capacity_exceeds_room_shows_room_capacity(data_dir):
    course = NEW_COURSE[:6] + ["999"] + NEW_COURSE[7:]
    out = run_session(data_dir, ["1", *course, "0"])
    assert "人數上限不得超過教室容量（教室 TR-310 容量 60）" in out


def test_unknown_menu_choice_and_eof_do_not_crash(data_dir):
    """亂輸入選項 → 提示後繼續；輸入用完（EOF）→ 正常離開，不丟例外。"""
    out = run_session(data_dir, ["99", "abc"])
    assert out.count("[錯誤] 沒有這個選項") == 2
    assert "再見！" in out


def test_eof_in_the_middle_of_a_flow(data_dir):
    """新增課程填到一半輸入就結束 → 印「已取消並離開」，不丟例外。"""
    out = run_session(data_dir, ["1", "NEW101", "測試課程"])
    assert "已取消並離開" in out


# ======================================================================
# 修改、刪除、查詢
# ======================================================================
def test_update_course_blank_keeps_other_fields(data_dir):
    """修改時只填人數上限，其他欄位按 Enter → 只有人數上限改變。"""
    out = run_session(data_dir, ["2", "CS101", "", "", "", "", "", "50", "", "0"])
    assert "[成功] 課程 [CS101] 計算機程式設計 修改成功。" in out
    saved = json.loads((data_dir / "db.json").read_text("utf-8"))
    cs101 = next(c for c in saved["courses"] if c["course_id"] == "CS101")
    assert cs101["capacity"] == 50
    assert cs101["teacher"] == "林教授"


def test_update_course_not_found_asks_nothing_else(data_dir):
    out = run_session(data_dir, ["2", "XX999", "0"])
    assert "[錯誤] 修改失敗：找不到課程 XX999。" in out


def test_delete_cancelled_keeps_course(data_dir):
    """刪除時回答 n → 不刪除。"""
    run_session(data_dir, ["1", *NEW_COURSE, "3", "NEW101", "n", "0"])
    saved = json.loads((data_dir / "db.json").read_text("utf-8"))
    assert any(c["course_id"] == "NEW101" for c in saved["courses"])


def test_query_courses_by_teacher(data_dir):
    """依教師查詢「林教授」→ 列出 CS101 和 CS203。"""
    out = run_session(data_dir, ["4", "", "林教授", "", "", "", "0"])
    assert "[查詢] 共 2 筆課程" in out
    assert "CS101" in out and "CS203" in out


def test_query_courses_invalid_day(data_dir):
    out = run_session(data_dir, ["4", "", "", "8", "0"])
    assert "[錯誤] 查詢失敗：星期必須為 1–7。" in out


def test_student_add_default_credits_then_delete(data_dir):
    """新增學生（學分上限按 Enter 用預設 25）→ 查得到 → 刪除成功。"""
    out = run_session(data_dir, [
        "5", "S99999", "測試生", "資工系", "",
        "8", "S99999", "", "",
        "7", "S99999", "y",
        "0",
    ])
    assert "[成功] 學生 [S99999] 測試生 新增成功。" in out
    assert "學分上限 25" in out
    assert "[成功] 學生 [S99999] 測試生 刪除成功。" in out


def test_classroom_in_use_cannot_be_deleted(data_dir):
    out = run_session(data_dir, ["10", "TR-310", "y", "0"])
    assert "[錯誤] 刪除失敗：教室 TR-310 仍有課程或活動使用中。" in out


# ======================================================================
# 存檔與重新啟動（不會改到種子檔）
# ======================================================================
def test_restart_loads_previous_save_and_seed_untouched(data_dir):
    """第一次執行新增課程 → 第二次執行讀得到 → 種子檔完全沒變。"""
    seed_bytes = (data_dir / main.SEED_FILE).read_bytes()

    first = run_session(data_dir, ["1", *NEW_COURSE, "0"])
    assert "讀取種子檔" in first

    second = run_session(data_dir, ["4", "NEW101", "", "", "", "", "0"])
    assert "讀取上次的存檔" in second
    assert "[查詢] 共 1 筆課程" in second

    assert (data_dir / main.SEED_FILE).read_bytes() == seed_bytes


def test_corrupted_save_falls_back_to_seed(data_dir):
    """db.json 壞掉 → 警告並改用種子檔，壞檔有備份。"""
    (data_dir / "db.json").write_text("{ 壞掉的 json", encoding="utf-8")
    out = run_session(data_dir, ["4", "CS101", "", "", "", "", "0"])
    assert "[警告] 存檔" in out and "損毀" in out
    assert "[查詢] 共 1 筆課程" in out
    assert (data_dir / "db.json.corrupt.bak").exists()
