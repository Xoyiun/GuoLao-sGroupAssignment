"""全系統通用常數與錯誤代碼定義 (Constants)。

供校園選課與課表規劃系統的所有副程式 (F1–F10, Main 等) 引用，
將系統規格常數、檔案名稱、資料欄位與錯誤代碼統一集中於此處，
避免跨模組循環匯入與規格修改時各副程式不同步的問題。
"""

# ======================================================================
# 一、通用操作狀態與錯誤代碼 (Status & Error Codes)
# ======================================================================
# 標註說明：
#   [規格] 需求規格書或 Use Case 定義之規則代碼
#   [系統/自訂] 為了資料完整性與防護而加的檢查代碼
OK = "OK"                                    # 操作成功（通用）
NOT_FOUND = "NOT_FOUND"                      # 找不到該課程、學生或教室
DUPLICATE_ID = "DUPLICATE_ID"                # 課程代號、學號或教室代號已存在
INVALID_FIELD = "INVALID_FIELD"              # 欄位格式錯誤、空白、型別不對或不可修改欄位
INVALID_CREDITS = "INVALID_CREDITS"          # 學分或學分上限不符合正整數規定
INVALID_CAPACITY = "INVALID_CAPACITY"        # 容量/人數上限無效，或修改後低於目前選課人數
INVALID_DAY = "INVALID_DAY"                  # 星期不在 1–7 範圍
INVALID_PERIOD = "INVALID_PERIOD"            # 節次不在 1–9、a、b、c 範圍
INVALID_TIME_SLOTS = "INVALID_TIME_SLOTS"    # 時段格式錯誤或清單為空
DUPLICATE_SLOT = "DUPLICATE_SLOT"            # 同一門課/活動的時段重複
CLASSROOM_NOT_FOUND = "CLASSROOM_NOT_FOUND"  # 指定的教室不存在
CAPACITY_EXCEEDS_ROOM = "CAPACITY_EXCEEDS_ROOM"  # 課程人數上限超過指定教室容量
COURSE_NOT_FOUND = "COURSE_NOT_FOUND"        # 學生的已選課程不存在
COURSE_HAS_STUDENTS = "COURSE_HAS_STUDENTS"  # 欲刪除的課程仍有學生選修
CLASSROOM_IN_USE = "CLASSROOM_IN_USE"        # 欲刪除的教室仍有課程或活動使用中
INVALID_STUDENT_COURSES = "INVALID_STUDENT_COURSES"  # 學生選課清單有重複課程
SAVE_FAILED = "SAVE_FAILED"                  # 自動存檔或手動存檔失敗

# F2 衝堂與選課限制
TIME_CONFLICT = "TIME_CONFLICT"              # 時段衝堂（與已選課程衝堂）
ROOM_CONFLICT = "ROOM_CONFLICT"              # 教室時段衝堂
ACTIVITY_CONFLICT = "ACTIVITY_CONFLICT"      # 活動時段衝突
CREDIT_LIMIT_EXCEEDED = "CREDIT_LIMIT_EXCEEDED"  # 超過學分上限
COURSE_FULL = "COURSE_FULL"                  # 課程人數已達上限（無剩餘名額）

# F3 課表與空閒時段
STUDENT_NOT_FOUND = "STUDENT_NOT_FOUND"      # 查無該學生
NO_FREE_SLOTS = "NO_FREE_SLOTS"              # 指定區間無可用空閒時段

# F4 校園活動與場地
NO_AVAILABLE_ROOM = "NO_AVAILABLE_ROOM"      # 無合適或空閒之教室
CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"      # 報名人數超過上限
ACTIVITY_NOT_FOUND = "ACTIVITY_NOT_FOUND"    # 找不到該活動

# F5 課程篩選
CONFLICTING_CRITERIA = "CONFLICTING_CRITERIA"  # 篩選條件衝突或矛盾
MIN_CREDITS_UNMET = "MIN_CREDITS_UNMET"      # 無法滿足最低學分需求

# F7 / F8 排課最佳化與搜尋
NO_FEASIBLE_SCHEDULE = "NO_FEASIBLE_SCHEDULE"  # 找不到可行排課方案

# F9 校園路徑
NO_PATH_FOUND = "NO_PATH_FOUND"              # 找不到可行移動路徑
INVALID_LOCATION = "INVALID_LOCATION"        # 地點或節點無效

# F10 動態重排
REPLAN_FAILED = "REPLAN_FAILED"              # 動態重新規劃失敗

# ======================================================================
# 二、規格與業務常數 (Specification & Business Constants)
# ======================================================================
ALLOW_ZERO_CREDITS = False  # 學分是否允許為 0（預設必須為正整數）
DEFAULT_MAX_CREDITS = 25    # 學生學分上限預設值（規格書：25）

# 時段規格
VALID_DAYS = range(1, 8)    # 星期 1–7
VALID_PERIODS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c")

# ======================================================================
# 三、檔案與儲存常數 (File & Storage Constants)
# ======================================================================
COURSE_DATA_DIRECTORY = "Courses"          # 依課程代號分開存放課程資料
STUDENT_DATA_DIRECTORY = "Students"        # 依學號分開存放學生資料
CLASSROOM_FILE = "Classroom.json"          # 教室固定資料檔名
CAMPUS_GRAPH_FILE = "CampusGraph.json"     # 校園圖固定資料檔名

# ======================================================================
# 四、資料模型欄位定義 (Schema & Field Constants)
# ======================================================================
COURSE_FIELDS = (
    "title", "credits", "required", "teacher", "classroom_id",
    "capacity", "time_slots",
)
STUDENT_FIELDS = ("name", "department", "max_credits", "enrolled_courses")

# 讀檔時若單筆資料缺少這些鍵（視為資料損毀），將自動略過該筆
REQUIRED_KEYS = {
    "classrooms": ("classroom_id", "capacity"),
    "courses": (
        "course_id", "title", "credits", "required", "teacher",
        "classroom_id", "capacity", "time_slots",
    ),
    "students": (
        "student_id", "name", "department", "max_credits",
        "enrolled_courses",
    ),
    "activities": ("activity_id", "title", "classroom_id", "time_slots"),
}

# ======================================================================
# 五、使用者介面與顯示對照 (UI & Message Mappings)
# ======================================================================
DAY_NAMES = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "日"}
KIND = {"course": "課程", "student": "學生", "classroom": "教室"}
ID_LABEL = {"course": "課程代號", "student": "學號", "classroom": "教室代號"}
ACTION = {"add": "新增", "update": "修改", "delete": "刪除"}

# 錯誤碼 → 錯誤原因（通用提示文字）
ERROR_REASONS = {
    INVALID_DAY: "星期必須為 1–7",
    INVALID_PERIOD: "節次必須為 1–9、a、b、c",
    INVALID_TIME_SLOTS: "時段格式錯誤，請用「星期-節次」並以逗號分隔，例如 2-3,2-4,4-a",
    DUPLICATE_SLOT: "同一門課的時段不可重複",
    CLASSROOM_NOT_FOUND: "找不到指定的教室",
    COURSE_NOT_FOUND: "已選課程中有不存在的課程",
    INVALID_STUDENT_COURSES: "已選課程清單不可重複",
    SAVE_FAILED: "存檔失敗，這次的修改只存在記憶體中，關閉程式後會消失",
    TIME_CONFLICT: "時段衝突（與已選課程衝堂）",
    ROOM_CONFLICT: "教室時段已被佔用",
    ACTIVITY_CONFLICT: "時段與已參加活動衝突",
    CREDIT_LIMIT_EXCEEDED: "加選後學分超過學分上限",
    COURSE_FULL: "課程人數已額滿",
    STUDENT_NOT_FOUND: "查無該學生資料",
    NO_FREE_SLOTS: "指定區間內無可用空閒時段",
    NO_AVAILABLE_ROOM: "無符合容量、設備或時段之可用教室",
    CAPACITY_EXCEEDED: "人數超過場地或活動上限",
    ACTIVITY_NOT_FOUND: "找不到該活動",
    CONFLICTING_CRITERIA: "篩選條件矛盾無法滿足",
    MIN_CREDITS_UNMET: "無法湊足最低學分需求",
    NO_FEASIBLE_SCHEDULE: "未找到滿足條件之可行課表組合",
    NO_PATH_FOUND: "找不到兩地點間之移動路徑",
    INVALID_LOCATION: "指定地點不存在於校園地圖中",
    REPLAN_FAILED: "動態重新規劃課表失敗",
}

# INVALID_FIELD 依實體種類給不同提示
INVALID_FIELD_REASONS = {
    "course": "資料格式錯誤（代號、名稱、教師不可空白；必選修請輸入「必」或「選」）",
    "student": "資料格式錯誤（學號、姓名、系級不可空白）",
    "classroom": "資料格式錯誤（教室代號不可空白）",
}
