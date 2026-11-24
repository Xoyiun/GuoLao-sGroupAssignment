"""F5 多條件課程篩選與可行性檢查模組 (Course Filter)。

- FilterCourses：依條件篩選候選課程。
- CheckCourseFeasibility：除了篩選，還判斷條件是否可行，一次列出所有不可行的原因。

篩選條件 criteria（都可省略）：
    - required_ids: list[str]    必修清單，一定要納入（不受偏好星期限制）
    - wished_ids: list[str]      希望修習的課程；有填時只從必修與這些課程中挑選
    - enrolled_ids: list[str]    學生原本已選的課程，額滿也不影響
    - min_credits / max_credits: int  最低／最高學分
    - blocked_slots: list[dict]  不可上課時段 [{"day": int, "period": str}, ...]
    - preferred_days: list[int]  偏好的上課星期
    - has_seats: bool            是否只保留有名額的課程（只用於 FilterCourses）

回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

from itertools import combinations

from Constants import (
    CONFLICTING_CRITERIA,
    COURSE_FULL,
    INVALID_FIELD,
    MIN_CREDITS_UNMET,
    NOT_FOUND,
    OK,
    VALID_DAYS,
)
import CourseDataManager as courseDataManager
from TimeSlotUtils import GetWeekday, TimeSlotsOverlap


def IsValidCriteria(criteria: dict) -> bool:
    """檢查篩選條件的型別與範圍。"""
    if not isinstance(criteria, dict):
        return False
    for key in ("required_ids", "wished_ids", "enrolled_ids"):
        ids = criteria.get(key, [])
        if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
            return False
    for key in ("min_credits", "max_credits"):
        credits = criteria.get(key)
        if credits is not None and (not isinstance(credits, int) or isinstance(credits, bool) or credits < 0):
            return False
    days = criteria.get("preferred_days", [])
    if not isinstance(days, (list, tuple, set)) or not all(
        isinstance(day, int) and not isinstance(day, bool) and day in VALID_DAYS for day in days
    ):
        return False
    blocked = criteria.get("blocked_slots", [])
    if not isinstance(blocked, list) or (blocked and not courseDataManager.ValidateTimeSlots(blocked)[0]):
        return False
    return criteria.get("has_seats") in (None, True, False)


def ExclusionReasons(course: dict, criteria: dict, checkSeats: bool) -> list[str]:
    """列出一門課不符合的所有條件："blocked"、"not_preferred_day"、"full"；都符合則為空清單。"""
    reasons = []
    slots = course.get("time_slots", [])
    if TimeSlotsOverlap(slots, criteria.get("blocked_slots", [])):
        reasons.append("blocked")
    preferredDays = criteria.get("preferred_days", [])
    isRequired = course["course_id"] in criteria.get("required_ids", [])
    if preferredDays and not isRequired and not any(GetWeekday(slot["day"]) in preferredDays for slot in slots):
        reasons.append("not_preferred_day")
    alreadyEnrolled = course["course_id"] in criteria.get("enrolled_ids", [])
    if checkSeats and not alreadyEnrolled and courseDataManager.RemainingSeats(course) <= 0:
        reasons.append("full")
    return reasons


def CoursesInScope(database: dict, criteria: dict) -> list[dict]:
    """可以考慮的課程：不含活動；有填希望課程時，只留必修與希望課程。"""
    wished = criteria.get("wished_ids", [])
    scope = set(wished) | set(criteria.get("required_ids", []))
    return [
        course for course in database.get("courses", [])
        if course.get("course_type") != "event" and (not wished or course["course_id"] in scope)
    ]


def FilterCourses(database: dict, criteria: dict) -> tuple[bool, str, list[dict]]:
    """依多條件篩選候選課程。

    回傳：
        (ok, code, candidate_courses):
        - 成功：(True, OK, [course_dict, ...])
        - 條件格式錯誤：(False, INVALID_FIELD, [])
        - 必修不符合條件或不存在：(False, CONFLICTING_CRITERIA, [])
        - 候選學分合計低於最低學分：(False, MIN_CREDITS_UNMET, [])
    學分只做合計的初步檢查；要連衝堂一起檢查請用 CheckCourseFeasibility。
    """
    if not IsValidCriteria(criteria):
        return False, INVALID_FIELD, []
    checkSeats = criteria.get("has_seats") is True
    candidates = [
        course for course in CoursesInScope(database, criteria)
        if not ExclusionReasons(course, criteria, checkSeats)
    ]
    if set(criteria.get("required_ids", [])) - {course["course_id"] for course in candidates}:
        return False, CONFLICTING_CRITERIA, []
    if sum(course["credits"] for course in candidates) < (criteria.get("min_credits") or 0):
        return False, MIN_CREDITS_UNMET, []
    return True, OK, candidates


def ConflictGroups(courses: list[dict]) -> list[list[dict]]:
    """把課程依「直接或間接互相衝堂」分組；不同組的課程一定不會衝堂。"""
    groups = []
    for course in courses:
        merged, others = [course], []
        for group in groups:
            if any(TimeSlotsOverlap(course["time_slots"], member["time_slots"]) for member in group):
                merged += group
            else:
                others.append(group)
        groups = others + [merged]
    return groups


def GroupCreditTotals(courses: list[dict]) -> set[int]:
    """一組課程中，互不衝堂的選法能湊出的所有學分總和（含都不選的 0）。"""
    if not courses:
        return {0}
    first, rest = courses[0], courses[1:]
    compatible = [course for course in rest if not TimeSlotsOverlap(first["time_slots"], course["time_slots"])]
    return GroupCreditTotals(rest) | {first["credits"] + total for total in GroupCreditTotals(compatible)}


def MaxReachableCredits(required: list[dict], candidates: list[dict], maxCredits: int | None) -> int:
    """必修全選、其他課互不衝堂，且不超過最高學分時，最多能選幾學分。"""
    requiredCredits = sum(course["credits"] for course in required)
    requiredIds = {course["course_id"] for course in required}
    optional = [
        course for course in candidates
        if course["course_id"] not in requiredIds
        and not any(TimeSlotsOverlap(course["time_slots"], item["time_slots"]) for item in required)
    ]
    totals = {requiredCredits}
    for group in ConflictGroups(optional):
        groupTotals = GroupCreditTotals(group)
        totals = {
            total + extra for total in totals for extra in groupTotals
            if extra == 0 or maxCredits is None or total + extra <= maxCredits
        }
    return max(totals)


def CheckCourseFeasibility(database: dict, criteria: dict) -> tuple[bool, str, dict]:
    """篩選候選課程並檢查條件是否可行；全部檢查完才回傳，不修改資料。

    回傳：(ok, code, report)，code 為第一項問題的代碼（可行時為 OK）。
    report = {
        "candidates": [course, ...]                 符合條件的候選課程
        "excluded": [(課程代號, [原因, ...]), ...]  被排除的課程與全部原因
        "reachable_credits": int                    不衝堂且不超過最高學分時最多能選的學分
        "problems": [{"type": 代碼, ...}, ...]      依序為查無課程、條件矛盾、必修額滿、最低學分不足
    }
    """
    report = {"candidates": [], "excluded": [], "reachable_credits": 0, "problems": []}
    if not IsValidCriteria(criteria):
        return False, INVALID_FIELD, report

    requiredIds = list(dict.fromkeys(criteria.get("required_ids", [])))
    wishedIds = list(dict.fromkeys(criteria.get("wished_ids", [])))
    minCredits, maxCredits = criteria.get("min_credits"), criteria.get("max_credits")
    problems = report["problems"]
    scope = CoursesInScope(database, criteria)
    byId = {course["course_id"]: course for course in scope}

    for courseId in dict.fromkeys(requiredIds + wishedIds):
        if courseId not in byId:
            problems.append({"type": NOT_FOUND, "course_id": courseId})

    reasonsById = {}
    for course in scope:
        reasons = ExclusionReasons(course, criteria, checkSeats=True)
        reasonsById[course["course_id"]] = reasons
        if reasons:
            report["excluded"].append((course["course_id"], reasons))
        else:
            report["candidates"].append(course)

    required = [byId[courseId] for courseId in requiredIds if courseId in byId]
    if minCredits is not None and maxCredits is not None and minCredits > maxCredits:
        problems.append({"type": CONFLICTING_CRITERIA, "reason": "credit_range",
                         "min_credits": minCredits, "max_credits": maxCredits})
    for course in required:
        if "blocked" in reasonsById[course["course_id"]]:
            problems.append({"type": CONFLICTING_CRITERIA, "reason": "required_blocked",
                             "course_id": course["course_id"]})
    for first, second in combinations(required, 2):
        slots = TimeSlotsOverlap(first["time_slots"], second["time_slots"])
        if slots:
            problems.append({"type": CONFLICTING_CRITERIA, "reason": "required_overlap",
                             "course_ids": [first["course_id"], second["course_id"]], "slots": slots})
    requiredCredits = sum(course["credits"] for course in required)
    if maxCredits is not None and requiredCredits > maxCredits:
        problems.append({"type": CONFLICTING_CRITERIA, "reason": "required_credits",
                         "required_credits": requiredCredits, "max_credits": maxCredits})
    for course in required:
        if "full" in reasonsById[course["course_id"]]:
            problems.append({"type": COURSE_FULL, "course_id": course["course_id"]})

    usableRequired = [course for course in required if not reasonsById[course["course_id"]]]
    report["reachable_credits"] = MaxReachableCredits(usableRequired, report["candidates"], maxCredits)
    if minCredits is not None and report["reachable_credits"] < minCredits:
        problems.append({"type": MIN_CREDITS_UNMET, "min_credits": minCredits,
                         "reachable_credits": report["reachable_credits"]})

    if problems:
        return False, problems[0]["type"], report
    return True, OK, report
