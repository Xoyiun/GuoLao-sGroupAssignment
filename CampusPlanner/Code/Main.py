"""命令列介面與操作日誌模組。

本模組職責範圍：
1. 輸入 (Input)：詢問使用者操作、接收文字輸入並轉換為副程式所需的基本資料型別。
2. 呼叫副程式：呼叫各功能模組（F1–F10）的公開介面，不介入業務規則與驗證。
3. 輸出與 Log (Output & Logging)：接收副程式回傳的狀態與錯誤碼 (代碼非字串句)，
   將錯誤代碼轉譯為易讀日誌訊息並呈現於介面。
4. 保持介面功能：僅維護選單與互動流程，不直接操作內部資料結構 (如 self.data)。

執行方式：在專案根目錄執行 python CampusPlanner/Code/main.py（在任何資料夾執行都可以）。
"""

import os

from TimeSlotUtils import GetDateLabel, GetWeekday
from Constants import (
    ACTION,
    CAPACITY_EXCEEDS_ROOM,
    CLASSROOM_IN_USE,
    CLASSROOM_NOT_FOUND,
    COURSE_HAS_STUDENTS,
    COURSE_NOT_FOUND,
    DAY_NAMES,
    DEFAULT_MAX_CREDITS,
    DUPLICATE_ID,
    DUPLICATE_SLOT,
    ERROR_REASONS,
    ID_LABEL,
    INVALID_CAPACITY,
    INVALID_CREDITS,
    INVALID_DAY,
    INVALID_FIELD,
    INVALID_FIELD_REASONS,
    INVALID_PERIOD,
    INVALID_STUDENT_COURSES,
    INVALID_TIME_SLOTS,
    KIND,
    NOT_FOUND,
    OK,
    SAVE_FAILED,
    VALID_DAYS,
    VALID_PERIODS,
)
import CourseDataManager as courseDataManager
import Timetable as timetableModule

# 用 __file__ 算路徑，從哪個資料夾執行都找得到資料資料夾
HERE = os.path.dirname(os.path.abspath(__file__))
# 課程、學生的 ID 分檔與固定資料都放在 CampusPlanner/UserData
DATADIR = os.path.join(os.path.dirname(HERE), "UserData")


# ======================================================================
# 一、輸入處理 (Input Parsers & Helpers)
# ======================================================================
def ParseInt(text):
    """'3' → 3。轉不成整數就原樣回傳字串，讓副程式回報對應的錯誤碼。"""
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        return text


def ParseBool(text):
    """必修 → True、選修 → False；看不懂回傳 None（副程式會回報 INVALID_FIELD）。"""
    text = text.strip().lower()
    if text in ("必", "必修", "y", "yes", "1", "true"):
        return True
    if text in ("選", "選修", "n", "no", "0", "false"):
        return False
    return None


def ParseTimeSlots(text):
    """
    格式不對（少了「-」、有空的項目）就原樣回傳字串，副程式會回報 INVALID_TIME_SLOTS。
    星期、節次的範圍也交給副程式檢查（例如 8-1 會得到 INVALID_DAY）。
    """
    pieces = [piece.strip() for piece in text.split(",")]
    if not text.strip() or any(piece.count("-") != 1 for piece in pieces):
        return text
    slots = []
    for piece in pieces:
        day, period = (part.strip() for part in piece.split("-"))
        if not day or not period:
            return text
        slots.append({"day": ParseInt(day), "period": period.lower()})
    return slots


def ParseList(text):
    """'projector, mic' → ['projector', 'mic']；空白輸入 → []。"""
    return [item.strip() for item in text.split(",") if item.strip()]


def AskText(ask, prompt):
    """提示使用者並讀取輸入字串（去除前後空白）。"""
    return ask(prompt).strip()


def AskIdentifier(ask, prompt):
    """代號一律轉大寫，輸入 cs101 也能找到 CS101。"""
    return AskText(ask, prompt).upper()


def Confirm(ask, prompt):
    """詢問確認（y/n）。"""
    return AskText(ask, f"{prompt}（y/n）：").lower() in ("y", "yes")


def AskChanges(ask, fields):
    """依序詢問每個欄位，直接按 Enter 代表不修改。fields = [(欄位, 提示, 轉換函式), ...]"""
    changes = {}
    for field, prompt, parser in fields:
        text = AskText(ask, prompt)
        if text:
            changes[field] = parser(text)
    return changes


SLOTPROMPT = "上課時段（星期-節次，用逗號分隔，例如 2-3,2-4,4-a）"


def CourseFieldPrompts(suffix=""):
    """新增和修改課程共用的欄位與提示。suffix 用來在修改時加上「（Enter 不修改）」。"""
    return [
        ("title", f"課程名稱{suffix}：", str.strip),
        ("credits", f"學分{suffix}：", ParseInt),
        ("required", f"必修或選修（必/選）{suffix}：", ParseBool),
        ("teacher", f"授課教師{suffix}：", str.strip),
        ("classroom_id", f"教室代號（例如 TR-310）{suffix}：", lambda userInput: userInput.strip().upper()),
        ("capacity", f"人數上限{suffix}：", ParseInt),
        ("time_slots", f"{SLOTPROMPT}{suffix}：", ParseTimeSlots),
    ]


# ======================================================================
# 二、輸出與 Log 格式化 (Output & Log Formatters)
# ======================================================================
def ErrorReason(code, kind, objId, detail=""):
    """把副程式回傳的錯誤碼轉成中文日誌說明（不含句號）。detail 為補充資訊。"""
    if code == DUPLICATE_ID:
        return f"{ID_LABEL[kind]} {objId} 已重複存在"
    if code == NOT_FOUND:
        return f"找不到{KIND[kind]} {objId}"
    if code == COURSE_HAS_STUDENTS:
        return f"課程 {objId} 目前已有 {detail} 名學生選修，請先辦理退選"
    if code == CLASSROOM_IN_USE:
        return f"教室 {objId} 仍有課程或活動使用中"
    if code == INVALID_FIELD:
        return INVALID_FIELD_REASONS[kind]
    if code == INVALID_CREDITS:
        return "學分上限必須為正整數" if kind == "student" else "學分必須為正整數"
    if code == INVALID_CAPACITY:
        if kind == "classroom":
            return "教室容量必須是大於或等於 1 的整數"
        return "人數上限必須是大於或等於 1 的整數，且不得低於目前選課人數"
    if code == CAPACITY_EXCEEDS_ROOM:
        return "人數上限不得超過教室容量" + (f"（{detail}）" if detail else "")
    return ERROR_REASONS.get(code, f"未知的錯誤（{code}）")


def ResultMessage(ok, code, action, kind, objId, name="", detail=""):
    """依規格書格式組出執行結果 log，例如：
    [成功] 課程 [CS101] 計算機程式設計 新增成功。
    [錯誤] 新增失敗：課程代號 CS101 已重複存在。
    """
    activity = ACTION[action]
    if ok:
        label = f"{KIND[kind]} [{objId}]" + (f" {name}" if name else "")
        return f"[成功] {label} {activity}成功。"
    return f"[錯誤] {activity}失敗：{ErrorReason(code, kind, objId, detail)}。"


def FormatTimeSlots(slots):
    """[{'day': 2, 'period': '3'}, {'day': 2, 'period': '4'}] → '星期二 3,4 節'"""
    byDay = {}
    for slot in slots:
        day = slot["day"]
        dateLabel = GetDateLabel(day)
        key = (dateLabel or "", GetWeekday(day))
        byDay.setdefault(key, []).append(slot["period"])
    parts = []
    for (dateLabel, day), periods in sorted(byDay.items()):
        periods.sort(key=VALID_PERIODS.index)
        dayLabel = f"{dateLabel}（星期{DAY_NAMES[day]}）" if dateLabel else f"星期{DAY_NAMES[day]}"
        parts.append(f"{dayLabel} {','.join(periods)} 節")
    return "；".join(parts)


def FormatCourse(course):
    """CS101 計算機概論 | 3 學分 | 必修 | 王大明 | A101 | 人數 45/50（剩 5）| 星期一 A,B 節"""
    if course.get("course_type") == "event":
        required = "活動"
    else:
        required = "必修" if course["required"] else "選修"
    enrolled = course.get("enrolled_count", 0)
    return (
        f"{course['course_id']} {course['title']} | {course['credits']} 學分 | {required} | "
        f"{course['teacher']} | {course['classroom_id']} | "
        f"人數 {enrolled}/{course['capacity']}（剩 {courseDataManager.RemainingSeats(course)}）| "
        f"{FormatTimeSlots(course['time_slots'])}"
    )


def FormatStudent(student):
    """A1234567 王大明 | 資工系 | 學分上限 25 | 已選 CS101、CS102"""
    courses = "、".join(student["enrolled_courses"]) or "（尚未選課）"
    return (
        f"{student['student_id']} {student['name']} | {student['department']} | "
        f"學分上限 {student['max_credits']} | 已選 {courses}"
    )


def FormatClassroom(room):
    """A101 | 綜合教學大樓 | 容量 50 | 設備 投影機、麥克風"""
    equipment = "、".join(room.get("equipment", [])) or "無"
    building = room.get("building_name") or room.get("building_id") or "未填"
    return f"{room['classroom_id']} | {building} | 容量 {room['capacity']} | 設備 {equipment}"


def ShowResults(show, title, items, formatter):
    """印出查詢結果；沒有資料時印提示 log。"""
    if not items:
        show(f"[查詢] 沒有符合條件的{title}。")
        return
    show(f"[查詢] 共 {len(items)} 筆{title}：")
    for item in items:
        show("  " + formatter(item))


def CapacityDetail(manager, classroomId):
    """CAPACITY_EXCEEDS_ROOM 時查詢教室容量（透過 manager 介面或相容 dict）。"""
    if hasattr(manager, "get_classroom_capacity"):
        classroomCapacity = manager.GetClassroomCapacity(classroomId)
    elif hasattr(manager, "data"):
        room = courseDataManager.FindClassroom(manager.data, classroomId)
        classroomCapacity = room["capacity"] if room else None
    elif isinstance(manager, dict):
        room = courseDataManager.FindClassroom(manager, classroomId)
        classroomCapacity = room["capacity"] if room else None
    else:
        classroomCapacity = None
    return (
        f"教室 {classroomId} 容量 {classroomCapacity}"
        if classroomCapacity is not None else ""
    )


def StudentsInCourse(manager, course):
    """刪除失敗時查詢選課人數（透過 manager 介面或相容 dict）。"""
    if hasattr(manager, "get_course_student_count"):
        return manager.GetCourseStudentCount(course["course_id"])
    if hasattr(manager, "data"):
        return max(course.get("enrolled_count", 0), courseDataManager.CountEnrolled(manager.data, course["course_id"]))
    if isinstance(manager, dict):
        return max(course.get("enrolled_count", 0), courseDataManager.CountEnrolled(manager, course["course_id"]))
    return course.get("enrolled_count", 0)


# ======================================================================
# 三、介面操作流程 (Interface Flows)
# ======================================================================
# 課程流程
def AddCourseFlow(manager, ask, show):
    course = {"course_id": AskIdentifier(ask, "課程代號（例如 CS101）：")}
    for field, prompt, parser in CourseFieldPrompts():
        course[field] = parser(AskText(ask, prompt))
    ok, code = manager.AddCourse(course)
    detail = CapacityDetail(manager, course["classroom_id"]) if code == CAPACITY_EXCEEDS_ROOM else ""
    show(ResultMessage(ok, code, "add", "course",
         course["course_id"], course["title"], detail))


def UpdateCourseFlow(manager, ask, show):
    courseId = AskIdentifier(ask, "要修改的課程代號：")
    course = manager.FindCourse(courseId)
    if course is None:
        show(ResultMessage(False, NOT_FOUND, "update", "course", courseId))
        return
    show("目前資料：" + FormatCourse(course))
    changes = AskChanges(ask, CourseFieldPrompts("（Enter 不修改）"))
    if not changes:
        show("[提示] 沒有任何修改。")
        return
    ok, code = manager.UpdateCourse(courseId, changes)
    classroomId = changes.get("classroom_id", course["classroom_id"])
    detail = CapacityDetail(manager, classroomId) if code == CAPACITY_EXCEEDS_ROOM else ""
    show(ResultMessage(ok, code, "update", "course",
         courseId, course["title"], detail))


def DeleteCourseFlow(manager, ask, show):
    courseId = AskIdentifier(ask, "要刪除的課程代號：")
    course = manager.FindCourse(courseId)
    if course is None:
        show(ResultMessage(False, NOT_FOUND, "delete", "course", courseId))
        return
    show("將刪除：" + FormatCourse(course))
    if not Confirm(ask, "確定要刪除嗎"):
        show("[提示] 已取消刪除。")
        return
    title = course["title"]
    count = StudentsInCourse(manager, course)
    ok, code = manager.DeleteCourse(courseId)
    show(ResultMessage(ok, code, "delete", "course", courseId, title, (str)(count)))


def QueryCoursesFlow(manager, ask, show):
    show("輸入查詢條件，直接按 Enter 代表不限（多個條件會同時成立）。")
    conditions = {}

    courseId = AskIdentifier(ask, "課程代號：")
    if courseId:
        conditions["courseId"] = courseId

    teacher = AskText(ask, "授課教師：")
    if teacher:
        conditions["teacher"] = teacher

    dayText = AskText(ask, "星期（1–7）：")
    if dayText:
        day = ParseInt(dayText)
        if day not in VALID_DAYS:
            show(f"[錯誤] 查詢失敗：{ERROR_REASONS[INVALID_DAY]}。")
            return
        conditions["day"] = day

    requiredText = AskText(ask, "必修或選修（必/選）：")
    if requiredText:
        required = ParseBool(requiredText)
        if required is None:
            show("[錯誤] 查詢失敗：必選修請輸入「必」或「選」。")
            return
        conditions["required"] = required

    if AskText(ask, "只看還有剩餘名額的課程？（y/Enter 不限）：").lower() in ("y", "yes"):
        conditions["hasSeats"] = True

    ShowResults(show, "課程", manager.QueryCourses(**conditions), FormatCourse)


# 學生流程
def AddStudentFlow(manager, ask, show):
    student = {
        "student_id": AskIdentifier(ask, "學號（例如 S11200001）："),
        "name": AskText(ask, "姓名："),
        "department": AskText(ask, "系級："),
    }
    maxText = AskText(ask, f"學分上限（Enter 預設 {DEFAULT_MAX_CREDITS}）：")
    student["max_credits"] = ParseInt(maxText) if maxText else DEFAULT_MAX_CREDITS
    student["enrolled_courses"] = []
    ok, code = manager.AddStudent(student)
    show(ResultMessage(ok, code, "add", "student",
         student["student_id"], student["name"]))


def UpdateStudentFlow(manager, ask, show):
    studentId = AskIdentifier(ask, "要修改的學號：")
    student = manager.FindStudent(studentId)
    if student is None:
        show(ResultMessage(False, NOT_FOUND, "update", "student", studentId))
        return
    show("目前資料：" + FormatStudent(student))
    changes = AskChanges(ask, [
        ("name", "姓名（Enter 不修改）：", str.strip),
        ("department", "系級（Enter 不修改）：", str.strip),
        ("max_credits", "學分上限（Enter 不修改）：", ParseInt),
    ])
    if not changes:
        show("[提示] 沒有任何修改。")
        return
    ok, code = manager.UpdateStudent(studentId, changes)
    show(ResultMessage(ok, code, "update",
         "student", studentId, student["name"]))


def DeleteStudentFlow(manager, ask, show):
    studentId = AskIdentifier(ask, "要刪除的學號：")
    student = manager.FindStudent(studentId)
    if student is None:
        show(ResultMessage(False, NOT_FOUND, "delete", "student", studentId))
        return
    show("將刪除：" + FormatStudent(student))
    if not Confirm(ask, "確定要刪除嗎（已選課程的人數會各減 1）"):
        show("[提示] 已取消刪除。")
        return
    name = student["name"]
    ok, code = manager.DeleteStudent(studentId)
    show(ResultMessage(ok, code, "delete", "student", studentId, name))


def QueryStudentsFlow(manager, ask, show):
    show("輸入查詢條件，直接按 Enter 代表不限（多個條件會同時成立）。")
    conditions = {}
    studentId = AskIdentifier(ask, "學號：")
    if studentId:
        conditions["studentId"] = studentId
    department = AskText(ask, "系級：")
    if department:
        conditions["department"] = department
    courseId = AskIdentifier(ask, "有選修的課程代號：")
    if courseId:
        conditions["courseId"] = courseId
    ShowResults(show, "學生", manager.QueryStudents(**conditions), FormatStudent)


# 教室流程
def AddClassroomFlow(manager, ask, show):
    room = {
        "classroom_id": AskIdentifier(ask, "教室代號（例如 TR-310）："),
        "building_id": AskIdentifier(ask, "大樓代號（可留空）："),
        "building_name": AskText(ask, "大樓名稱（可留空）："),
        "capacity": ParseInt(AskText(ask, "教室容量：")),
        "equipment": ParseList(AskText(ask, "設備（用逗號分隔，可留空）：")),
    }
    ok, code = manager.AddClassroom(room)
    show(ResultMessage(ok, code, "add", "classroom", room["classroom_id"]))


def DeleteClassroomFlow(manager, ask, show):
    classroomId = AskIdentifier(ask, "要刪除的教室代號：")
    room = manager.FindClassroom(classroomId)
    if room is None:
        show(ResultMessage(False, NOT_FOUND, "delete", "classroom", classroomId))
        return
    show("將刪除：" + FormatClassroom(room))
    if not Confirm(ask, "確定要刪除嗎"):
        show("[提示] 已取消刪除。")
        return
    ok, code = manager.DeleteClassroom(classroomId)
    show(ResultMessage(ok, code, "delete", "classroom", classroomId))


def ListClassroomsFlow(manager, ask, show):
    ShowResults(show, "教室", manager.GetClassrooms(), FormatClassroom)



def ViewTimetableFlow(manager, ask, show):
    student_id = AskIdentifier(ask, "請輸入學號：")
    db = {
        "courses": manager.QueryCourses(),
        "students": manager.QueryStudents(),
    }

    timetable = timetableModule.build_timetable(db, student_id)
    if timetable is None:
        show(f"[錯誤] 找不到學生：{student_id}")
        return

    summary = timetableModule.summarize_timetable(timetable, db, student_id)
    show(f"\n學生 {student_id} 的每週課表：")
    show("星期 | " + " | ".join(timetableModule.PERIODS))

    for day_index, row in enumerate(timetable):
        cells = [cell if cell is not None else "--" for cell in row]
        daily_count = summary["daily_period_counts"][day_index]
        show(f"星期{day_index + 1} | " + " | ".join(cells) + f" | 上課 {daily_count} 節")

    show(f"總學分：{summary['total_credits']}")
    show(f"佔用節數：{sum(summary['daily_period_counts'])}")
    show(f"空堂數：{summary['free_period_count']}")

def QueryTimetableFlow(manager, ask, show):
    student_id = AskIdentifier(ask, "請輸入學號：")
    db = {"courses": manager.QueryCourses(), "students": manager.QueryStudents()}
    timetable = timetableModule.build_timetable(db, student_id)
    if timetable is None:
        show(f"[錯誤] 找不到學生：{student_id}")
        return

    day_text = AskText(ask, "星期（1-7，留空不限）：")
    day = ParseInt(day_text) if day_text else None
    period = AskText(ask, "節次（留空不限）：") or None
    course_id = AskText(ask, "課程／活動代碼（留空不限）：") or None

    if day is not None and not isinstance(day, int):
        show("[錯誤] 星期必須輸入 1 到 7。")
        return
    try:
        results = timetableModule.query_timetable(timetable, day, period, course_id)
    except ValueError as error:
        show(f"[錯誤] {error}")
        return

    if not results:
        show("符合條件的課表時段是空的。")
        return
    for result_day, result_period, result_id in results:
        show(f"星期{result_day} 第{result_period}節：{result_id}")


def FindFreeSlotsFlow(manager, ask, show):
    student_id = AskIdentifier(ask, "請輸入學號：")
    db = {"courses": manager.QueryCourses(), "students": manager.QueryStudents()}
    timetable = timetableModule.build_timetable(db, student_id)
    if timetable is None:
        show(f"[錯誤] 找不到學生：{student_id}")
        return

    day = ParseInt(AskText(ask, "星期（1-7）："))
    start_period = AskText(ask, "開始節次（1-9、a-c）：")
    end_period = AskText(ask, "結束節次（1-9、a-c）：")
    min_length = ParseInt(AskText(ask, "至少連續幾節："))

    if not isinstance(day, int) or not isinstance(min_length, int):
        show("[錯誤] 星期和連續節數都必須輸入整數。")
        return
    try:
        slots = timetableModule.find_free_slots(
            timetable, day, start_period, end_period, min_length
        )
    except ValueError as error:
        show(f"[錯誤] {error}")
        return

    if not slots:
        show("指定範圍內沒有符合長度的連續空堂。")
        return
    for first_period, last_period in slots:
        show(f"星期{day} 第{first_period}節到第{last_period}節為空堂。")

# ======================================================================
# 四、選單與啟動 (Menu & Main Loop)
# ======================================================================
MENU = (
    ("1", "新增課程", AddCourseFlow),
    ("2", "修改課程", UpdateCourseFlow),
    ("3", "刪除課程", DeleteCourseFlow),
    ("4", "查詢課程", QueryCoursesFlow),
    ("5", "新增學生", AddStudentFlow),
    ("6", "修改學生", UpdateStudentFlow),
    ("7", "刪除學生", DeleteStudentFlow),
    ("8", "查詢學生", QueryStudentsFlow),
    ("9", "新增教室", AddClassroomFlow),
    ("10", "刪除教室", DeleteClassroomFlow),
    ("11", "列出教室", ListClassroomsFlow),
    ("12", "查看個人課表", ViewTimetableFlow),
    ("13", "依條件查詢個人課表", QueryTimetableFlow),
    ("14", "查詢連續空堂", FindFreeSlotsFlow),
)


def MenuText():
    lines = ["", "===== 校園選課與課表規劃系統 ====="]
    lines += [f" {key:>2}. {label}" for key, label, _ in MENU]
    lines.append("  0. 離開")
    return "\n".join(lines)


def OpenManager(dataDir, show=print):
    """初始化並開啟資料管理器，讀寫都在 dataDir，顯示載入狀態日誌。"""
    manager = courseDataManager.CourseDataManager(dataDir, savePath=dataDir)
    show(f"[載入] 讀取資料：{dataDir}")
    return manager


def Run(manager, ask=input, show=print):
    """主介面迴圈：負責使用者互動、呼叫流程並處理終止/日誌顯示。"""
    if manager.loadErrors:
        show(f"[警告] 載入時略過 {len(manager.loadErrors)} 筆有問題的資料：")
        for message in manager.loadErrors:
            show("  " + message)
    actions = {key: flow for key, _, flow in MENU}
    while True:
        show(MenuText())
        try:
            choice = AskText(ask, "請選擇功能：")
        except (EOFError, KeyboardInterrupt):
            show("\n再見！")
            return
        if choice == "0":
            show("再見！")
            return
        flow = actions.get(choice)
        if flow is None:
            show("[錯誤] 沒有這個選項，請輸入選單上的數字。")
            continue
        try:
            flow(manager, ask, show)
        except (EOFError, KeyboardInterrupt):
            show("\n已取消並離開。")
            return
        except Exception as error:
            show(f"[錯誤] 發生未預期的錯誤：{error}")


def Main(ask=input, show=print, dataDir=DATADIR):
    manager = OpenManager(dataDir, show)
    Run(manager, ask, show)


if __name__ == "__main__":
    Main()
