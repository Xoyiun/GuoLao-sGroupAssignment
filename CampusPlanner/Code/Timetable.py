"""F3 個人課表產生、查詢、統計與空閒時段搜尋。"""

from TimeSlotUtils import GetWeekday

PERIODS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c")


def build_timetable(db, student_id):
    """建立 7x12 list 課表；格子內容為課程／活動代碼，空格為 None。"""
    student = next(
        (item for item in db.get("students", []) if item.get("student_id") == student_id),
        None,
    )
    if student is None:
        return None

    timetable = [[None for _ in PERIODS] for _ in range(7)]
    selected_ids = set(student.get("enrolled_courses", []))

    def place_slots(record):
        for slot in record.get("time_slots", []):
            day = GetWeekday(slot.get("day"))
            period = slot.get("period")
            if not isinstance(day, int) or not 1 <= day <= 7 or period not in PERIODS:
                continue

            row_index = day - 1
            period_index = PERIODS.index(period)
            # 不覆蓋先排入的內容；衝堂檢查由 F2 負責。
            if timetable[row_index][period_index] is None:
                timetable[row_index][period_index] = record.get("course_id")

    # 先排課程，避免活動資料覆蓋課程格。
    for course in db.get("courses", []):
        if course.get("type") == "event":
            continue
        if course.get("course_id") in selected_ids:
            place_slots(course)

    # 活動記錄在 courses 資料清單中，但只加入此學生參加的活動。
    for activity in db.get("courses", []):
        if activity.get("course_type") != "event":
            continue
        if student_id in activity.get("student_ids", []):
            place_slots(activity)

    return timetable

def find_course_in_timetable(timetable, course_id):
    """回傳目標課程／活動所在的 (星期, 節次) 清單。"""
    results = []
    for day_index, row in enumerate(timetable):
        for period_index, cell in enumerate(row):
            if cell == course_id:
                results.append((day_index + 1, PERIODS[period_index]))
    return results


def summarize_timetable(timetable, db, student_id):
    """回傳每日佔用節數、總學分數與空堂數。"""
    student = next(
        (item for item in db.get("students", []) if item.get("student_id") == student_id),
        None,
    )
    if student is None:
        return None

    selected_ids = set(student.get("enrolled_courses", []))
    total_credits = sum(
        course.get("credits", 0)
        for course in db.get("courses", [])
        if course.get("course_id") in selected_ids and course.get("type") != "event"
    )
    daily_period_counts = [sum(cell is not None for cell in row) for row in timetable]
    free_period_count = sum(cell is None for row in timetable for cell in row)

    return {
        "daily_period_counts": daily_period_counts,
        "total_credits": total_credits,
        "free_period_count": free_period_count,
    }


def find_free_slots(timetable, day, start_period, end_period, min_length=1):
    """尋找指定星期及節次範圍內長度至少 min_length 的連續空堂。"""
    if not isinstance(day, int) or isinstance(day, bool) or not 1 <= day <= 7:
        raise ValueError("day must be between 1 and 7")
    if start_period not in PERIODS or end_period not in PERIODS:
        raise ValueError("invalid period")
    if not isinstance(min_length, int) or isinstance(min_length, bool) or min_length < 1:
        raise ValueError("min_length must be at least 1")

    start_index = PERIODS.index(start_period)
    end_index = PERIODS.index(end_period)
    if start_index > end_index:
        raise ValueError("start_period must not be after end_period")

    row = timetable[day - 1]
    free_slots = []
    run_start = None

    for index in range(start_index, end_index + 1):
        if row[index] is None:
            if run_start is None:
                run_start = index
        elif run_start is not None:
            if index - run_start >= min_length:
                free_slots.append((PERIODS[run_start], PERIODS[index - 1]))
            run_start = None

    if run_start is not None and end_index - run_start + 1 >= min_length:
        free_slots.append((PERIODS[run_start], PERIODS[end_index]))

    return free_slots


def query_timetable(timetable, day=None, period=None, course_id=None):
    """依星期、節次及課程／活動代碼查詢課表。"""
    if day is not None and (
        not isinstance(day, int) or isinstance(day, bool) or not 1 <= day <= 7
    ):
        raise ValueError("day must be between 1 and 7")
    if period is not None and period not in PERIODS:
        raise ValueError("invalid period")

    results = []
    for day_index, row in enumerate(timetable):
        current_day = day_index + 1
        if day is not None and current_day != day:
            continue
        for period_index, cell in enumerate(row):
            current_period = PERIODS[period_index]
            if cell is None:
                continue
            if period is not None and current_period != period:
                continue
            if course_id is not None and cell != course_id:
                continue
            results.append((current_day, current_period, cell))

    return results