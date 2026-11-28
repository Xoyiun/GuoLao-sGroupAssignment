"""F7 多條件最佳課表搜尋模組 (Schedule Optimizer)。

本副程式負責依學生必修課、候選選修課與偏好搜尋排課組合：
- 搜尋滿足學分上下限與零衝堂之課表組合

介面規範：
- 輸入參數皆有明確之型別與規格。
- 回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

from Constants import INVALID_FIELD, NO_FEASIBLE_SCHEDULE, OK, VALID_PERIODS
import CourseDataManager as courseDataManager
from TimeSlotUtils import GetWeekday, TimeSlotsOverlap
from Timetable import count_gap_periods

EARLY_PERIOD = "1"  # 早八
HALF_DAY_PERIODS = (  # 集中上課時段：一天分成上午、下午、晚上三個區段
    {"1", "2", "3", "4"},
    {"5", "6", "7", "8", "9"},
    {"a", "b", "c"},
)


# 評分公式（F7 需求規格第五節）：score = Σ 方向 × 權重 × 指標
# 方向 +1 表示越多越好（加分），−1 表示越少越好（扣分）。新增偏好只要在這裡多加一列。
SCORE_TERMS = {
    # 指標名稱: (方向, 預設權重)
    "credits": (+1, 1.0),
    "campus_days": (-1, 2.0),
    "gap_periods": (-1, 1.0),
    "early_periods": (-1, 1.5),
    "half_day_blocks": (-1, 0.5),
    "preferred_ratio": (+1, 5.0),
}
DEFAULT_WEIGHTS = {name: weight for name, (_, weight) in SCORE_TERMS.items()}


def IsWeightValue(value):
    """權重必須是 ≥ 0 的數字（bool 不算數字）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def ValidateWeights(weights):
    """None 表示全用預設；否則必須是 {已知的權重名稱: ≥ 0 的數字}，只需填要調整的項目。"""
    if weights is None:
        return True
    return isinstance(weights, dict) and all(
        name in DEFAULT_WEIGHTS and IsWeightValue(value) for name, value in weights.items()
    )


def ScoreSchedule(metrics, weights=None):
    """依偏好指標與權重計算方案分數，取到小數第 2 位；weights 只需填要調整的項目。"""
    merged = {**DEFAULT_WEIGHTS, **(weights or {})}
    score = sum(direction * merged[name] * metrics[name] for name, (direction, _) in SCORE_TERMS.items())
    return round(score, 2)


def OccupiedPeriodsByWeekday(courses):
    """{星期: {有課的節次, ...}}；活動的日期時段換算成星期。"""
    occupied = {}
    for course in courses:
        for slot in course.get("time_slots", []):
            occupied.setdefault(GetWeekday(slot["day"]), set()).add(slot["period"])
    return occupied


def CalculateScheduleMetrics(planCourses, enrolledCourses=(), preferredCourses=()):
    """計算一個方案的偏好指標（定義見 F7 需求規格第四節）。

    輸入：
        planCourses: 方案中新排入的課程字典清單
        enrolledCourses: 學生已選的課程字典清單（到校天數、空堂等看整週，所以要一起算）
        preferredCourses: 偏好課程代號清單
    回傳：
        {"credits", "campus_days", "gap_periods", "early_periods", "half_day_blocks", "preferred_ratio"}
    """
    occupied = OccupiedPeriodsByWeekday(list(planCourses) + list(enrolledCourses))
    dayRows = [
        [period if period in dayPeriods else None for period in VALID_PERIODS]
        for dayPeriods in occupied.values()
    ]

    planIds = {course["course_id"] for course in planCourses}
    preferred = list(preferredCourses)
    preferredRatio = (
        sum(courseId in planIds for courseId in preferred) / len(preferred) if preferred else 0
    )

    return {
        "credits": sum(course["credits"] for course in planCourses),
        "campus_days": len(occupied),
        "gap_periods": sum(count_gap_periods(row) for row in dayRows),  # 與 F3 共用空堂定義
        "early_periods": sum(EARLY_PERIOD in dayPeriods for dayPeriods in occupied.values()),
        "half_day_blocks": sum(
            bool(dayPeriods & block) for dayPeriods in occupied.values() for block in HALF_DAY_PERIODS
        ),
        "preferred_ratio": preferredRatio,
    }


def HasTimeConflict(selected, enrolledCourses):
    """方案中的課程與已選課程衝堂，或方案中的課程彼此衝堂，回傳 True。"""
    if any(TimeSlotsOverlap(course.get("time_slots", []), enrolled.get("time_slots", []))
           for course in selected for enrolled in enrolledCourses):
        return True
    return any(TimeSlotsOverlap(first.get("time_slots", []), second.get("time_slots", []))
               for index, first in enumerate(selected) for second in selected[index + 1:])


def IsNonNegativeInteger(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def BuildSearchProblem(database: dict, studentId: str, preferences: dict) -> tuple[bool, str, dict]:
    """把搜尋偏好整理成搜尋問題；F7 最佳課表搜尋與 F8 演算法比較共用同一份條件。

    回傳 (ok, code, problem)，problem 為：
        {"required": [必修課程], "candidates": [候選課程], "enrolled": [已選課程],
         "min_credits": int, "max_credits": int, "blocked": [不可上課時段],
         "preferred_ids": [偏好課程代號], "weights": 權重或 None}
    已選的課已經在課表上，不再排入方案（D16）；候選課程去掉重複、必修與已選。
    格式錯誤、學生或必修課不存在回傳 (False, INVALID_FIELD, {})。
    """
    if not isinstance(preferences, dict):
        return False, INVALID_FIELD, {}
    student = courseDataManager.FindStudent(database, studentId)
    if not student:
        return False, INVALID_FIELD, {}

    minCredits = preferences.get("min_credits", 9)
    maxCredits = preferences.get("max_credits", student.get("max_credits", 25))
    required = preferences.get("required_courses", [])
    candidateIds = preferences.get("candidate_courses", [])
    preferredIds = preferences.get("preferred_courses", [])
    weights = preferences.get("weights")
    if not all(isinstance(value, list) for value in (required, candidateIds, preferredIds)):
        return False, INVALID_FIELD, {}
    if not ValidateWeights(weights) or not IsNonNegativeInteger(minCredits) or not IsNonNegativeInteger(maxCredits):
        return False, INVALID_FIELD, {}

    requiredCourses = [courseDataManager.FindCourse(database, courseId) for courseId in required]
    if any(course is None for course in requiredCourses):
        return False, INVALID_FIELD, {}
    enrolledIds = set(student.get("enrolled_courses", []))
    skipIds = set(required) | enrolledIds
    candidates = []
    for courseId in dict.fromkeys(candidateIds):
        course = courseDataManager.FindCourse(database, courseId)
        if course is not None and courseId not in skipIds:
            candidates.append(course)

    return True, OK, {
        "required": [course for course in requiredCourses if course["course_id"] not in enrolledIds],
        "candidates": candidates,
        "enrolled": [course for course in (courseDataManager.FindCourse(database, courseId)
                                           for courseId in student.get("enrolled_courses", []))
                     if course is not None],
        "min_credits": minCredits,
        "max_credits": maxCredits,
        "blocked": preferences.get("blocked_slots", []),
        "preferred_ids": preferredIds,
        "weights": weights,
    }


def IsFeasibleSelection(problem: dict, selected: list[dict]) -> bool:
    """selected（必修＋選到的候選）是否符合所有必要條件：學分上下限、禁止時段、額滿、衝堂。"""
    total = sum(course["credits"] for course in selected)
    if total < problem["min_credits"] or total > problem["max_credits"]:
        return False
    if any(TimeSlotsOverlap(course.get("time_slots", []), problem["blocked"]) for course in selected):
        return False
    if any(courseDataManager.RemainingSeats(course) <= 0 for course in selected):
        return False
    return not HasTimeConflict(selected, problem["enrolled"])


def SearchOptimalSchedules(database: dict, studentId: str, preferences: dict) -> tuple[bool, str, list[dict]]:
    """依偏好條件搜尋最佳可行課表組合。

    輸入：
        database: 標準資料庫字典
        studentId: 學號
        preferences: 偏好字典（完整說明見 F7 需求規格第三節）：
            - min_credits: int (最低學分)
            - max_credits: int (最高學分)
            - required_courses: list[str] (指定必排課程清單)
            - candidate_courses: list[str] (候選選修課程清單)
            - blocked_slots: list[dict] (不可上課時段)
            - preferred_courses: list[str] (偏好課程清單)
            - weights: dict (評分權重，只需填要調整的項目)
    回傳：
        (ok, code, schedule_plans):
        - 成功：(True, OK, [{"courses": [cid, ...], "total_credits": int, "score": float,
                             "metrics": {...}}, ...])，依分數由高到低、同分依課程代號
        - 無可行課表：(False, NO_FEASIBLE_SCHEDULE, [])
        - 格式錯誤：(False, INVALID_FIELD, [])
    """
    ok, code, problem = BuildSearchProblem(database, studentId, preferences)
    if not ok:
        return False, code, []

    candidates = problem["candidates"]
    plans = []
    for mask in range(1 << len(candidates)):
        selected = problem["required"] + [
            candidates[index] for index in range(len(candidates)) if mask & (1 << index)
        ]
        if not IsFeasibleSelection(problem, selected):
            continue
        metrics = CalculateScheduleMetrics(selected, problem["enrolled"], problem["preferred_ids"])
        plans.append({
            "courses": [course["course_id"] for course in selected],
            "total_credits": metrics["credits"],
            "score": ScoreSchedule(metrics, problem["weights"]),
            "metrics": metrics,
        })
    if not plans:
        return False, NO_FEASIBLE_SCHEDULE, []
    plans.sort(key=lambda plan: (-plan["score"], plan["courses"]))
    return True, OK, plans
