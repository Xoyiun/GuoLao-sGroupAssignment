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
    # 載入後課程類型存在 course_type（檔案裡的 type 會在 F6 載入時轉換）。
    for course in db.get("courses", []):
        if course.get("course_type") == "event":
            continue
        if course.get("course_id") in selected_ids:
            place_slots(course)

    # 活動也存在 courses 清單中；學生報名的活動記在 enrolled_courses。
    for activity in db.get("courses", []):
        if activity.get("course_type") != "event":
            continue
        if activity.get("course_id") in selected_ids:
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
        if course.get("course_id") in selected_ids and course.get("course_type") != "event"
    )
    daily_period_counts = [sum(cell is not None for cell in row) for row in timetable]
    free_period_count = sum(cell is None for row in timetable for cell in row)

    return {
        "daily_period_counts": daily_period_counts,
        "total_credits": total_credits,
        "free_period_count": free_period_count,
        "gap_period_count": sum(count_gap_periods(row) for row in timetable),
    }


def count_gap_periods(row):
    """一天中第一個和最後一個有課的節次之間，沒有課的節數（即「空堂」）；沒課或只有一段課為 0。"""
    busy = [index for index, cell in enumerate(row) if cell is not None]
    if not busy:
        return 0
    return sum(row[index] is None for index in range(busy[0], busy[-1] + 1))


def find_free_slots_between(timetable, start_day, start_period, end_day, end_period, min_length=1):
    """跨日查詢：從 (start_day, start_period) 到 (end_day, end_period) 之間，長度至少 min_length 的連續空堂。

    連續空堂不跨越午夜，每天分開計算；第一天從 start_period 開始、最後一天到 end_period 為止，
    中間的日子查整天。回傳 [(星期, 開始節次, 結束節次), ...]。
    """
    for day in (start_day, end_day):
        if not isinstance(day, int) or isinstance(day, bool) or not 1 <= day <= 7:
            raise ValueError("day must be between 1 and 7")
    if start_period not in PERIODS or end_period not in PERIODS:
        raise ValueError("invalid period")
    if (start_day, PERIODS.index(start_period)) > (end_day, PERIODS.index(end_period)):
        raise ValueError("start must not be after end")

    results = []
    for day in range(start_day, end_day + 1):
        first = start_period if day == start_day else PERIODS[0]
        last = end_period if day == end_day else PERIODS[-1]
        for free_start, free_end in find_free_slots(timetable, day, first, last, min_length):
            results.append((day, free_start, free_end))
    return results


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