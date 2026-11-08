"""Main.py（命令列介面）的自動化測試：F1 資料管理、F2 加選退選、F3 課表與空堂。

用假的 ask（照順序回傳預先寫好的輸入）和 show（把輸出收進清單）取代鍵盤和螢幕，
所以不需要人工輸入。每個測試都在 tmp_path 裡放一份 TestInput 複本，不會碰到真正的檔案。

執行：python -m pytest test_main.py -v      只跑這類：python -m pytest -m cli -v
"""

import json
import os
import shutil

import pytest

import Main as main

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_INPUT = os.path.join(HERE, "TestInput")  # 修改：測試資料改為 TestInput/Courses、TestInput/Students 按 ID 分檔
USER_DATA = os.path.join(os.path.dirname(HERE), "CampusPlanner", "UserData")  # 教室與校園圖放在 UserData

pytestmark = pytest.mark.cli  # 這個檔案的測試全部標成 cli


def Scripted(inputs):
    """回傳一個假的 ask：每呼叫一次就給下一筆輸入；用完時丟 EOFError（等同使用者按 Ctrl+Z）。"""
    remaining = iter(inputs)

    def Ask(prompt=""):
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError from None

    return Ask


def RunSession(dataDir, inputs):
    """跑一次完整的 main()，回傳所有輸出合成的字串。"""
    output = []
    main.Main(ask=Scripted(inputs), show=output.append, dataDir=str(dataDir), arguments=[])
    return "\n".join(output)


@pytest.fixture(name="dataDir")
def DataDir(tmp_path):
    """把 TestInput 的 Courses/、Students/ 和 UserData 的固定資料複製到 tmp_path，程式在這裡讀寫。"""
    for directoryName in ("Courses", "Students"):
        shutil.copytree(os.path.join(TEST_INPUT, directoryName), tmp_path / directoryName)
    for filename in ("Classroom.json", "CampusGraph.json"):
        shutil.copy(os.path.join(USER_DATA, filename), tmp_path / filename)
    return tmp_path


# 新增一門合法課程時要輸入的內容（選單 1 之後）
NewCourse = ["NEW101", "測試課程", "3", "選", "測試教授", "TR-310", "30", "2-1,2-2"]  # TR-310 星期二第 1、2 節沒有課


# ======================================================================
# 解析輸入
# ======================================================================
def test_ParseTimeSlotsMultipleAndUppercase():
    """多個時段、有空白、節次大寫 → 正確轉成 dict 清單，節次變小寫。"""
    assert main.ParseTimeSlots("2-3, 2-4,4-A") == [
        {"day": 2, "period": "3"},
        {"day": 2, "period": "4"},
        {"day": 4, "period": "a"},
    ]


@pytest.mark.parametrize("text", ["", "2", "2-3,", "2-3-4", "-3", "2-"])
def test_ParseTimeSlotsBadFormatReturnsText(text):
    """格式不對時交由資料管理模組回報 INVALID_TIME_SLOTS。"""
    assert main.ParseTimeSlots(text) == text


def test_ParseIntAndBool():
    assert main.ParseInt(" 3 ") == 3
    assert main.ParseInt("abc") == "abc"
    assert main.ParseBool("必修") is True
    assert main.ParseBool("選") is False
    assert main.ParseBool("不知道") is None


def test_FormatTimeSlotsGroupsByDay():
    """同一天的節次合併並依節次順序排列（a 排在 9 後面）。"""
    slots = [{"day": 4, "period": "a"}, {"day": 2, "period": "4"}, {"day": 2, "period": "3"}, {"day": 4, "period": "9"}]
    assert main.FormatTimeSlots(slots) == "星期二 3,4 節；星期四 9,a 節"


# ======================================================================
# 輸出訊息符合規格書格式
# ======================================================================
def test_AddCourseSuccessMessage(dataDir):
    out = RunSession(dataDir, ["1", *NewCourse, "0"])
    assert "[成功] 課程 [NEW101] 測試課程 新增成功。" in out


def test_AddCourseDuplicateMessage(dataDir):
    """重複代號 → 規格書的錯誤訊息。輸入小寫 cs101 也會被轉成 CS101。"""
    out = RunSession(dataDir, ["1", "cs101", *NewCourse[1:], "0"])
    assert "[錯誤] 新增失敗：課程代號 CS101 已重複存在。" in out


def test_DeleteCourseWithStudentsMessage(dataDir):
    """已有學生選修的課程 → 拒絕刪除並顯示人數（CS101 的 enrolled_count 是 45）。"""
    out = RunSession(dataDir, ["3", "CS101", "y", "0"])
    assert "[錯誤] 刪除失敗：課程 CS101 目前已有 45 名學生選修，請先辦理退選。" in out


# ======================================================================
# 驗收條件：拒絕非法節次、無效學分；錯誤輸入不會當掉
# ======================================================================
@pytest.mark.parametrize("period", ["d", "0"])
def test_AddCourseRejectsIllegalPeriod(dataDir, period):
    course = NewCourse[:-1] + [f"1-{period}"]
    out = RunSession(dataDir, ["1", *course, "0"])
    assert "[錯誤] 新增失敗：節次必須為 1–9、a、b、c。" in out


@pytest.mark.parametrize("credits", ["0", "-1", "abc", ""])
def test_AddCourseRejectsInvalidCredits(dataDir, credits):
    course = NewCourse[:2] + [credits] + NewCourse[3:]
    out = RunSession(dataDir, ["1", *course, "0"])
    assert "[錯誤] 新增失敗：學分必須為正整數。" in out


def test_CapacityExceedsRoomShowsRoomCapacity(dataDir):
    course = NewCourse[:6] + ["999"] + NewCourse[7:]
    out = RunSession(dataDir, ["1", *course, "0"])
    assert "人數上限不得超過教室容量（教室 TR-310 容量 60）" in out


def test_UnknownMenuChoiceAndEofDoNotCrash(dataDir):
    """亂輸入選項 → 提示後繼續；輸入用完（EOF）→ 正常離開，不丟例外。"""
    out = RunSession(dataDir, ["99", "abc"])
    assert out.count("[錯誤] 沒有這個選項") == 2
    assert "再見！" in out


def test_EofInTheMiddleOfAFlow(dataDir):
    """新增課程填到一半輸入就結束 → 印「已取消並離開」，不丟例外。"""
    out = RunSession(dataDir, ["1", "NEW101", "測試課程"])
    assert "已取消並離開" in out


# ======================================================================
# 修改、刪除、查詢
# ======================================================================
def test_UpdateCourseBlankKeepsOtherFields(dataDir):
    """修改時只填人數上限，其他欄位按 Enter → 只有人數上限改變。"""
    out = RunSession(dataDir, ["2", "CS101", "", "", "", "", "", "50", "", "0"])
    assert "[成功] 課程 [CS101] 計算機程式設計 修改成功。" in out
    cs101 = json.loads((dataDir / "Courses" / "CS101.json").read_text("utf-8"))
    assert cs101["capacity"] == 50
    assert cs101["teacher"] == "林教授"


def test_UpdateCourseNotFoundAsksNothingElse(dataDir):
    out = RunSession(dataDir, ["2", "XX999", "0"])
    assert "[錯誤] 修改失敗：找不到課程 XX999。" in out


def test_DeleteCancelledKeepsCourse(dataDir):
    """刪除時回答 n → 不刪除。"""
    RunSession(dataDir, ["1", *NewCourse, "3", "NEW101", "n", "0"])
    saved = json.loads((dataDir / "Courses" / "NEW101.json").read_text("utf-8"))
    assert saved["course_id"] == "NEW101"


def test_QueryCoursesByTeacher(dataDir):
    """依教師查詢「林教授」→ 列出 CS101 和 CS203。"""
    out = RunSession(dataDir, ["4", "", "林教授", "", "", "", "0"])
    assert "[查詢] 共 2 筆課程" in out
    assert "CS101" in out and "CS203" in out


def test_QueryCoursesInvalidDay(dataDir):
    out = RunSession(dataDir, ["4", "", "", "8", "0"])
    assert "[錯誤] 查詢失敗：星期必須為 1–7。" in out


def test_StudentAddDefaultCreditsThenDelete(dataDir):
    """新增學生（學分上限按 Enter 用預設 25）→ 查得到 → 刪除成功。"""
    out = RunSession(dataDir, [
        "5", "S99999", "測試生", "資工系", "1", "",
        "8", "S99999", "", "",
        "7", "S99999", "y",
        "0",
    ])
    assert "[成功] 學生 [S99999] 測試生 新增成功。" in out
    assert "資工系 1 年級" in out and "學分上限 25" in out
    assert "[成功] 學生 [S99999] 測試生 刪除成功。" in out


def test_ClassroomInUseCannotBeDeleted(dataDir):
    out = RunSession(dataDir, ["10", "TR-310", "y", "0"])
    assert "[錯誤] 刪除失敗：教室 TR-310 仍有課程或活動使用中。" in out


# ======================================================================
# 存檔與重新啟動（不會改到種子檔）
# ======================================================================
def test_RestartLoadsPreviousSaveAndTestInputUntouched(dataDir):
    """第一次執行新增課程 → 存成 Courses/NEW101.json → 第二次執行讀得到；原本的 TestInput 沒被改到。"""
    first = RunSession(dataDir, ["1", *NewCourse, "0"])
    assert "[載入] 讀取資料" in first
    assert (dataDir / "Courses" / "NEW101.json").exists()

    second = RunSession(dataDir, ["4", "NEW101", "", "", "", "", "0"])
    assert "[查詢] 共 1 筆課程" in second

    assert not os.path.exists(os.path.join(TEST_INPUT, "Courses", "NEW101.json"))


def test_CorruptedCourseFileSkippedAndBackedUp(dataDir):
    """其中一個課程檔壞掉 → 警告並略過該檔，其他課程照常查詢，壞檔有備份。"""
    (dataDir / "Courses" / "BROKEN.json").write_text("{ 壞掉的 json", encoding="utf-8")
    out = RunSession(dataDir, ["4", "CS101", "", "", "", "", "0"])
    assert "[警告] 載入時略過 1 筆" in out and "BROKEN.json" in out
    assert "[查詢] 共 1 筆課程" in out
    assert (dataDir / "Courses" / "BROKEN.json.corrupt.bak").exists()


def test_ManagerInterfaceDecoupling(dataDir):
    """驗證 CourseDataManager 提供統一查詢介面，呼叫端不需直接讀取 manager.data。"""
    m = main.OpenManager(str(dataDir), show=lambda message: None)
    # find_course
    course = m.FindCourse("CS101")
    assert course is not None and course["course_id"] == "CS101"
    assert m.FindCourse("NON_EXISTENT") is None

    # find_student
    student = m.FindStudent("S10902")
    assert student is not None and student["student_id"] == "S10902"
    assert m.FindStudent("NON_EXISTENT") is None

    # find_classroom & get_classroom_capacity
    room = m.FindClassroom("TR-310")
    assert room is not None and room["classroom_id"] == "TR-310"
    assert m.GetClassroomCapacity("TR-310") == room["capacity"]
    assert m.GetClassroomCapacity("NON_EXISTENT") is None

    # count_enrolled & get_course_student_count
    assert m.CountEnrolled("CS101") >= 0
    assert m.GetCourseStudentCount("CS101") >= 45


# ======================================================================
# 啟動與隱藏匯入指令
# ======================================================================
def test_MainCanExitWithoutInteraction(tmp_path):
    """空資料夾也能啟動，選單標題正確，輸入 0 正常離開。"""
    output = []
    assert main.Main(ask=lambda _: "0", show=output.append, dataDir=str(tmp_path), arguments=[]) is None
    assert any("校園選課與課表規劃系統" in line for line in output)


def test_ImportCommandCopiesCurrentDataLayout(tmp_path):
    target = tmp_path / "imported"
    result = main.Main(show=lambda _: None, dataDir=str(target), arguments=["import", USER_DATA, str(target)])
    assert result is True
    assert (target / "Classroom.json").exists() and (target / "CampusGraph.json").exists()
    assert (target / "Courses").is_dir() and (target / "Students").is_dir()


# ======================================================================
# F2 加選與退選
# ======================================================================
def test_EnrollSuccessUpdatesStudentAndCount(dataDir):
    """加選成功 → 顯示學分摘要；學生已選清單與課程人數都更新並存檔。"""
    before = json.loads((dataDir / "Courses" / "MA101.json").read_text("utf-8"))["enrolled_count"]
    out = RunSession(dataDir, ["15", "S10902", "MA101", "0"])
    assert "選課結果：成功" in out
    assert "目前學分：7" in out and "加選後學分：11" in out and "學分上限：25" in out
    student = json.loads((dataDir / "Students" / "S10902.json").read_text("utf-8"))
    course = json.loads((dataDir / "Courses" / "MA101.json").read_text("utf-8"))
    assert "MA101" in student["enrolled_courses"] and course["enrolled_count"] == before + 1


def test_EnrollListsEveryConflict(dataDir):
    """同時衝堂又額滿 → 一次列出所有衝突，並照「衝突 1、衝突 2」編號，資料不變。"""
    RunSession(dataDir, [
        "1", "CLASH1", "衝堂課", "3", "選", "測試教授", "TR-310", "1", "4-2,4-3",  # 跟 CS102 同時段
        "15", "S10901", "CLASH1",            # 先讓一位學生選滿（人數上限 1）
        "0",
    ])
    out = RunSession(dataDir, ["15", "S10902", "CLASH1", "0"])
    assert "選課結果：失敗" in out
    assert "衝突 1：星期四第 2、3 節" in out and "已選課程：CS102 資料結構" in out
    assert "衝突 2：課程已額滿" in out
    student = json.loads((dataDir / "Students" / "S10902.json").read_text("utf-8"))
    assert "CLASH1" not in student["enrolled_courses"]


def test_EnrollTwiceIsRejected(dataDir):
    out = RunSession(dataDir, ["15", "S10902", "CS102", "0"])
    assert "選課結果：失敗（已經選過這門課）" in out


def test_EnrollUnknownStudent(dataDir):
    out = RunSession(dataDir, ["15", "NOPE", "0"])
    assert "[錯誤] 加選失敗：找不到學生 NOPE。" in out


def test_DropThenDropAgain(dataDir):
    """退選成功 → 人數減 1；同一門課再退選一次 → 回報沒有選這門課。"""
    before = json.loads((dataDir / "Courses" / "CS102.json").read_text("utf-8"))["enrolled_count"]
    out = RunSession(dataDir, ["16", "S10902", "CS102", "16", "S10902", "CS102", "0"])
    assert "[成功] 學生 S10902 已退選 CS102 資料結構。" in out
    assert "[錯誤] 退選失敗：沒有選這門課，無法退選。" in out
    course = json.loads((dataDir / "Courses" / "CS102.json").read_text("utf-8"))
    assert course["enrolled_count"] == before - 1


# ======================================================================
# F3 課表與空堂
# ======================================================================
def test_TimetableShowsCoursesActivitiesAndStats(dataDir):
    """報名活動後，課表同時顯示課程與活動，並列出圖例與統計。"""
    out = RunSession(dataDir, ["15", "S10901", "ACT02", "12", "S10901", "0"])
    assert "星期1 | -- | CS101 | CS101 | CS101 |" in out
    assert "ACT02：程式競賽培訓工作坊（活動）" in out and "CS101：計算機程式設計（課程）" in out
    assert "總學分：7" in out
    assert "空堂數（上課日中兩堂課之間的空節）：1" in out


def test_FreeSlotsAcrossDays(dataDir):
    """跨日查詢：星期一第 1 節到星期三第 c 節，至少連續 3 節。"""
    out = RunSession(dataDir, ["14", "S10901", "1", "1", "3", "c", "3", "0"])
    assert "星期一 第9節到第c節為空堂。" in out
    assert "星期二 第1節到第c節為空堂。" in out and "星期三 第1節到第c節為空堂。" in out
    assert "星期一 第1節到第1節" not in out  # 只有 1 節，不足 3 節


def test_FreeSlotsRejectsReversedRange(dataDir):
    out = RunSession(dataDir, ["14", "S10901", "3", "1", "1", "c", "1", "0"])
    assert "[錯誤]" in out
