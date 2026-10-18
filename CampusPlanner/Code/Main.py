"""F1 課程、學生與教室資料管理的命令列介面。

分工：
- 這個檔案只負責「問使用者、把輸入轉成資料、把結果印出來」。
- 所有規則檢查（代號重複、學分、節次…）都交給 F1_DataManager.py，不在這裡重寫。
- 每個流程函式都收 ask（讀輸入）和 show（印輸出），預設是 input / print；
  測試時換成假的 ask / show，就能自動測試，不需要人工輸入。

執行方式：在專案根目錄 python CampusPlanner/Code/Main.py（在任何資料夾執行都可以）。
"""

import os

import F1_DataManager as f1  # 搬到 CampusPlanner：原本是 import f1_manager as f1
from F6_StorageManager import DEFAULT_WORK_FILE  # 原本是 from data_manager import DEFAULT_WORK_FILE

HERE = os.path.dirname(os.path.abspath(__file__))  # 用 __file__ 算路徑，從哪個資料夾執行都找得到種子檔
SEED_FILE = "04_data_format.json"
DATA_DIR = os.path.join(os.path.dirname(HERE), "UserData")  # 新增：種子檔和 db.json 都放在 CampusPlanner/UserData

DAY_NAMES = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "日"}

KIND = {"course": "課程", "student": "學生", "classroom": "教室"}
ID_LABEL = {"course": "課程代號", "student": "學號", "classroom": "教室代號"}
ACTION = {"add": "新增", "update": "修改", "delete": "刪除"}

DEFAULT_MAX_CREDITS = 25  # 規格書：學分上限預設 25

# 錯誤碼 → 錯誤原因（跟課程／學生／教室無關的通用訊息）
ERROR_REASONS = {
    f1.INVALID_DAY: "星期必須為 1–7",
    f1.INVALID_PERIOD: "節次必須為 1–9、a、b、c",
    f1.INVALID_TIME_SLOTS: "時段格式錯誤，請用「星期-節次」並以逗號分隔，例如 2-3,2-4,4-a",
    f1.DUPLICATE_SLOT: "同一門課的時段不可重複",
    f1.CLASSROOM_NOT_FOUND: "找不到指定的教室",
    f1.COURSE_NOT_FOUND: "已選課程中有不存在的課程",
    f1.INVALID_STUDENT_COURSES: "已選課程清單不可重複",
    "SAVE_FAILED": "存檔失敗，這次的修改只存在記憶體中，關閉程式後會消失",
}

# INVALID_FIELD 依資料種類給不同提示
INVALID_FIELD_REASONS = {
    "course": "資料格式錯誤（代號、名稱、教師不可空白；必選修請輸入「必」或「選」）", #輸入必修選修
    "student": "資料格式錯誤（學號、姓名、系級不可空白）",
    "classroom": "資料格式錯誤（教室代號不可空白）",
}


# ======================================================================
# 解析輸入（純函式）：只負責把文字轉成資料，合不合法交給 F1_DataManager 判斷
# ======================================================================
def parse_int(text):
    """'3' → 3。轉不成整數就原樣回傳字串，讓 F1_DataManager 回報對應的錯誤碼。"""
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        return text


def parse_bool(text):
    """必修 → True、選修 → False；看不懂回傳 None（F1_DataManager 會回報 INVALID_FIELD）。"""
    text = text.strip().lower()
    if text in ("必", "必修", "y", "yes", "1", "true"):
        return True
    if text in ("選", "選修", "n", "no", "0", "false"):
        return False
    return None


def parse_time_slots(text):
    """
    格式不對（少了「-」、有空的項目）就原樣回傳字串，F1_DataManager 會回報 INVALID_TIME_SLOTS。
    星期、節次的範圍也交給 F1_DataManager 檢查（例如 8-1 會得到 INVALID_DAY）。
    """
    pieces = [p.strip() for p in text.split(",")]
    if not text.strip() or any(p.count("-") != 1 for p in pieces): #防止沒打和沒打-和多打-
        return text
    slots = []
    for piece in pieces:
        day, period = (part.strip() for part in piece.split("-")) #利用-把左用分別存進day , period
        if not day or not period: #最後確保-左右有沒有打東西
            return text
        slots.append({"day": parse_int(day), "period": period.lower()})
    return slots


def parse_list(text):
    """'projector, mic' → ['projector', 'mic']；空白輸入 → []。"""
    return [item.strip() for item in text.split(",") if item.strip()]


# ======================================================================
# 組出輸出文字（純函式）
# ======================================================================
def error_reason(code, kind, obj_id, detail=""): #kind = 實體種類 obj = 物件代碼 
    """把錯誤碼轉成中文原因（不含句號）。detail 是額外資訊，例如選課人數。"""
    if code == f1.DUPLICATE_ID:
        return f"{ID_LABEL[kind]} {obj_id} 已重複存在"
    if code == f1.NOT_FOUND:
        return f"找不到{KIND[kind]} {obj_id}"
    if code == f1.COURSE_HAS_STUDENTS:
        return f"課程 {obj_id} 目前已有 {detail} 名學生選修，請先辦理退選"
    if code == f1.CLASSROOM_IN_USE:
        return f"教室 {obj_id} 仍有課程或活動使用中"
    if code == f1.INVALID_FIELD:
        return INVALID_FIELD_REASONS[kind]
    if code == f1.INVALID_CREDITS:
        return "學分上限必須為正整數" if kind == "student" else "學分必須為正整數"
    if code == f1.INVALID_CAPACITY:
        if kind == "classroom":
            return "教室容量必須是大於或等於 1 的整數"
        return "人數上限必須是大於或等於 1 的整數，且不得低於目前選課人數"
    if code == f1.CAPACITY_EXCEEDS_ROOM:
        return "人數上限不得超過教室容量" + (f"（{detail}）" if detail else "")
    return ERROR_REASONS.get(code, f"未知的錯誤（{code}）")


def result_message(ok, code, action, kind, obj_id, name="", detail=""):
    """依規格書格式組出結果訊息，例如：
    [成功] 課程 [CS101] 計算機程式設計 新增成功。
    [錯誤] 新增失敗：課程代號 CS101 已重複存在。
    """
    act = ACTION[action]
    if ok:
        label = f"{KIND[kind]} [{obj_id}]" + (f" {name}" if name else "")
        return f"[成功] {label} {act}成功。"
    return f"[錯誤] {act}失敗：{error_reason(code, kind, obj_id, detail)}。" #去跟error_reason配合


def format_time_slots(slots): #把同一天不同堂合併到一起輸出
    """[{'day': 2, 'period': '3'}, {'day': 2, 'period': '4'}] → '星期二 3,4 節'（同一天合併、依節次排序）"""
    by_day = {}
    for slot in slots:
        by_day.setdefault(slot["day"], []).append(slot["period"])
    parts = []
    for day in sorted(by_day): #確保排出來星期一在星期二前面
        periods = sorted(by_day[day], key=f1.VALID_PERIODS.index)
        parts.append(f"星期{DAY_NAMES[day]} {','.join(periods)} 節")
    return "；".join(parts)


def format_course(course):
    """ CS101 計算機概論 | 3 學分 | 必修 | 王大明 | A101 | 人數 45/50（剩 5）| 星期一 A,B 節；星期二 3 節"""
    required = "必修" if course["required"] else "選修"
    enrolled = course.get("enrolled_count", 0)
    return (
        f"{course['course_id']} {course['title']} | {course['credits']} 學分 | {required} | "
        f"{course['teacher']} | {course['classroom_id']} | "
        f"人數 {enrolled}/{course['capacity']}（剩 {f1.remaining_seats(course)}）| "
        f"{format_time_slots(course['time_slots'])}"
    )


def format_student(student):
    """A1234567 王大明 | 資工系 | 學分上限 25 | 已選 CS101、CS102"""
    courses = "、".join(student["enrolled_courses"]) or "（尚未選課）"
    return (
        f"{student['student_id']} {student['name']} | {student['department']} | "#department 系所
        f"學分上限 {student['max_credits']} | 已選 {courses}"
    )


def format_classroom(room):
    """A101 | 綜合教學大樓 | 容量 50 | 設備 投影機、麥克風"""
    equipment = "、".join(room.get("equipment", [])) or "無"
    building = room.get("building_name") or room.get("building_id") or "未填"
    return f"{room['classroom_id']} | {building} | 容量 {room['capacity']} | 設備 {equipment}"


def show_results(show, title, items, formatter): #show 輸出工具 formatter 排版工具人 item原始資料
    """印出查詢結果；沒有資料時印提示。"""
    if not items:
        show(f"[查詢] 沒有符合條件的{title}。")
        return
    show(f"[查詢] 共 {len(items)} 筆{title}：")
    for item in items:
        show("  " + formatter(item))


def capacity_detail(db, classroom_id):
    """CAPACITY_EXCEEDS_ROOM 時告訴使用者教室容量是多少。"""
    room = f1.find_classroom(db, classroom_id)
    return f"教室 {classroom_id} 容量 {room['capacity']}" if room else ""


def students_in_course(db, course):
    """刪除失敗時要顯示的選課人數：取 enrolled_count 和實際學生資料中較大的那個。"""
    return max(course.get("enrolled_count", 0), f1.count_enrolled(db, course["course_id"]))


# ======================================================================
# 互動小工具
# ======================================================================
def ask_text(ask, prompt): #ask 相當於input
    return ask(prompt).strip()


def ask_id(ask, prompt):
    """代號一律轉大寫，輸入 cs101 也能找到 CS101。"""
    return ask_text(ask, prompt).upper()


def confirm(ask, prompt):
    return ask_text(ask, f"{prompt}（y/n）：").lower() in ("y", "yes")


def ask_changes(ask, fields):
    """依序詢問每個欄位，直接按 Enter 代表不修改。fields = [(欄位, 提示, 轉換函式), ...]"""
    changes = {}
    for field, prompt, parser in fields: #field 欄位名稱 prompt 提示文字 parser轉換器
        text = ask_text(ask, prompt)
        if text:
            changes[field] = parser(text)
    return changes


SLOT_PROMPT = "上課時段（星期-節次，用逗號分隔，例如 2-3,2-4,4-a）"


def course_field_prompts(suffix=""):
    """新增和修改課程共用的欄位與提示。suffix 用來在修改時加上「（Enter 不修改）」。"""
    return [
        ("title", f"課程名稱{suffix}：", str.strip),
        ("credits", f"學分{suffix}：", parse_int),
        ("required", f"必修或選修（必/選）{suffix}：", parse_bool),
        ("teacher", f"授課教師{suffix}：", str.strip),
        ("classroom_id", f"教室代號（例如 TR-310）{suffix}：", lambda t: t.strip().upper()),#使用lambda快速創造小涵式做轉大寫去空白
        ("capacity", f"人數上限{suffix}：", parse_int),
        ("time_slots", f"{SLOT_PROMPT}{suffix}：", parse_time_slots),
    ]


# ======================================================================
# 課程
# ======================================================================
def add_course_flow(m, ask, show):   #m F1Manager  ask輸入 show輸出
    course = {"course_id": ask_id(ask, "課程代號（例如 CS101）：")}
    for field, prompt, parser in course_field_prompts():
        course[field] = parser(ask_text(ask, prompt))  # 空白也照樣送出，讓 F1_DataManager 判斷
    ok, code = m.add_course(course)
    detail = capacity_detail(m.data, course["classroom_id"]) if code == f1.CAPACITY_EXCEEDS_ROOM else ""
    show(result_message(ok, code, "add", "course", course["course_id"], course["title"], detail))


def update_course_flow(m, ask, show):
    course_id = ask_id(ask, "要修改的課程代號：")
    course = f1.find_course(m.data, course_id)
    if course is None:  # 先確認課程存在，免得使用者填完全部欄位才知道找不到
        show(result_message(False, f1.NOT_FOUND, "update", "course", course_id))
        return
    show("目前資料：" + format_course(course))
    changes = ask_changes(ask, course_field_prompts("（Enter 不修改）"))
    if not changes:
        show("[提示] 沒有任何修改。")
        return
    ok, code = m.update_course(course_id, changes)
    classroom_id = changes.get("classroom_id", course["classroom_id"])
    detail = capacity_detail(m.data, classroom_id) if code == f1.CAPACITY_EXCEEDS_ROOM else ""
    show(result_message(ok, code, "update", "course", course_id, course["title"], detail))


def delete_course_flow(m, ask, show):
    course_id = ask_id(ask, "要刪除的課程代號：")
    course = f1.find_course(m.data, course_id)
    if course is None:
        show(result_message(False, f1.NOT_FOUND, "delete", "course", course_id))
        return
    show("將刪除：" + format_course(course))
    if not confirm(ask, "確定要刪除嗎"):
        show("[提示] 已取消刪除。")
        return
    title, count = course["title"], students_in_course(m.data, course)  # 刪除前先記下來
    ok, code = m.delete_course(course_id)
    show(result_message(ok, code, "delete", "course", course_id, title, count))


def query_courses_flow(m, ask, show):
    show("輸入查詢條件，直接按 Enter 代表不限（多個條件會同時成立）。")
    conditions = {}

    course_id = ask_id(ask, "課程代號：")
    if course_id:
        conditions["course_id"] = course_id

    teacher = ask_text(ask, "授課教師：")
    if teacher:
        conditions["teacher"] = teacher

    day_text = ask_text(ask, "星期（1–7）：")
    if day_text:
        day = parse_int(day_text)
        if day not in f1.VALID_DAYS:
            show(f"[錯誤] 查詢失敗：{ERROR_REASONS[f1.INVALID_DAY]}。")
            return
        conditions["day"] = day

    required_text = ask_text(ask, "必修或選修（必/選）：")
    if required_text:
        required = parse_bool(required_text)
        if required is None:
            show("[錯誤] 查詢失敗：必選修請輸入「必」或「選」。")
            return
        conditions["required"] = required

    if ask_text(ask, "只看還有剩餘名額的課程？（y/Enter 不限）：").lower() in ("y", "yes"):
        conditions["has_seats"] = True

    show_results(show, "課程", m.query_courses(**conditions), format_course)


# ======================================================================
# 學生
# ======================================================================
def add_student_flow(m, ask, show):
    student = {
        "student_id": ask_id(ask, "學號（例如 S11200001）："),
        "name": ask_text(ask, "姓名："),
        "department": ask_text(ask, "系級："),
    }
    max_text = ask_text(ask, f"學分上限（Enter 預設 {DEFAULT_MAX_CREDITS}）：")
    student["max_credits"] = parse_int(max_text) if max_text else DEFAULT_MAX_CREDITS
    student["enrolled_courses"] = []  # 選課屬於 F2，新增學生時一律從沒選課開始
    ok, code = m.add_student(student)
    show(result_message(ok, code, "add", "student", student["student_id"], student["name"]))


def update_student_flow(m, ask, show):
    student_id = ask_id(ask, "要修改的學號：")
    student = f1.find_student(m.data, student_id)
    if student is None:
        show(result_message(False, f1.NOT_FOUND, "update", "student", student_id))
        return
    show("目前資料：" + format_student(student))
    changes = ask_changes(ask, [
        ("name", "姓名（Enter 不修改）：", str.strip),
        ("department", "系級（Enter 不修改）：", str.strip),
        ("max_credits", "學分上限（Enter 不修改）：", parse_int),
    ])
    if not changes:
        show("[提示] 沒有任何修改。")
        return
    ok, code = m.update_student(student_id, changes)
    show(result_message(ok, code, "update", "student", student_id, student["name"]))


def delete_student_flow(m, ask, show):
    student_id = ask_id(ask, "要刪除的學號：")
    student = f1.find_student(m.data, student_id)
    if student is None:
        show(result_message(False, f1.NOT_FOUND, "delete", "student", student_id))
        return
    show("將刪除：" + format_student(student))
    if not confirm(ask, "確定要刪除嗎（已選課程的人數會各減 1）"):
        show("[提示] 已取消刪除。")
        return
    name = student["name"]
    ok, code = m.delete_student(student_id)
    show(result_message(ok, code, "delete", "student", student_id, name))


def query_students_flow(m, ask, show):
    show("輸入查詢條件，直接按 Enter 代表不限（多個條件會同時成立）。")
    conditions = {}
    student_id = ask_id(ask, "學號：")
    if student_id:
        conditions["student_id"] = student_id
    department = ask_text(ask, "系級：")
    if department:
        conditions["department"] = department
    course_id = ask_id(ask, "有選修的課程代號：")
    if course_id:
        conditions["course_id"] = course_id
    show_results(show, "學生", m.query_students(**conditions), format_student)


# ======================================================================
# 教室
# ======================================================================
def add_classroom_flow(m, ask, show):
    room = {
        "classroom_id": ask_id(ask, "教室代號（例如 TR-310）："),
        "building_id": ask_id(ask, "大樓代號（可留空）："),
        "building_name": ask_text(ask, "大樓名稱（可留空）："),
        "capacity": parse_int(ask_text(ask, "教室容量：")),
        "equipment": parse_list(ask_text(ask, "設備（用逗號分隔，可留空）：")),
    }
    ok, code = m.add_classroom(room)
    show(result_message(ok, code, "add", "classroom", room["classroom_id"]))


def delete_classroom_flow(m, ask, show):
    classroom_id = ask_id(ask, "要刪除的教室代號：")
    room = f1.find_classroom(m.data, classroom_id)
    if room is None:
        show(result_message(False, f1.NOT_FOUND, "delete", "classroom", classroom_id))
        return
    show("將刪除：" + format_classroom(room))
    if not confirm(ask, "確定要刪除嗎"):
        show("[提示] 已取消刪除。")
        return
    ok, code = m.delete_classroom(classroom_id)
    show(result_message(ok, code, "delete", "classroom", classroom_id))


def list_classrooms_flow(m, ask, show):
    show_results(show, "教室", m.get_classrooms(), format_classroom)


# ======================================================================
# 選單與啟動
# ======================================================================
MENU = (
    ("1", "新增課程", add_course_flow),
    ("2", "修改課程", update_course_flow),
    ("3", "刪除課程", delete_course_flow),
    ("4", "查詢課程", query_courses_flow),
    ("5", "新增學生", add_student_flow),
    ("6", "修改學生", update_student_flow),
    ("7", "刪除學生", delete_student_flow),
    ("8", "查詢學生", query_students_flow),
    ("9", "新增教室", add_classroom_flow),
    ("10", "刪除教室", delete_classroom_flow),
    ("11", "列出教室", list_classrooms_flow),
)


def menu_text():
    lines = ["", "===== F1 課程與學生資料管理 ====="]
    lines += [f" {key:>2}. {label}" for key, label, _ in MENU]
    lines.append("  0. 離開")
    return "\n".join(lines)


def open_manager(data_dir, show=print):
    """有上次的存檔（db.json）就讀它，沒有才讀種子檔；兩種情況都存到 db.json，不會改到種子檔。"""
    seed_path = os.path.join(data_dir, SEED_FILE)
    work_path = os.path.join(data_dir, DEFAULT_WORK_FILE)

    if os.path.exists(work_path):
        m = f1.F1Manager(work_path, save_path=work_path)
        if not m.corrupted:
            show(f"[載入] 讀取上次的存檔：{work_path}")
            return m
        # 存檔壞掉：DataManager 已把它備份成 db.json.corrupt.bak，改從種子檔重新開始
        show(f"[警告] 存檔 {work_path} 損毀，已備份為 .corrupt.bak，改用種子檔重新開始。")

    m = f1.F1Manager(seed_path, save_path=work_path)
    show(f"[載入] 讀取種子檔：{seed_path}")
    return m


def run(m, ask=input, show=print):
    """主選單迴圈。任何輸入錯誤都只印訊息，不讓程式當掉。"""
    if m.load_errors:
        show(f"[警告] 載入時略過 {len(m.load_errors)} 筆有問題的資料：")
        for message in m.load_errors:
            show("  " + message)
    actions = {key: flow for key, _, flow in MENU}
    while True:
        show(menu_text())
        try:
            choice = ask_text(ask, "請選擇功能：")
        except (EOFError, KeyboardInterrupt):  # Ctrl+Z / Ctrl+C 直接離開
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
            flow(m, ask, show)
        except (EOFError, KeyboardInterrupt):
            show("\n已取消並離開。")
            return
        except Exception as e:  # 最後一道防線：規格要求遇到錯誤不得導致程式異常終止
            show(f"[錯誤] 發生未預期的錯誤：{e}")


def main(ask=input, show=print, data_dir=DATA_DIR):
    m = open_manager(data_dir, show)
    run(m, ask, show)


if __name__ == "__main__":
    main()