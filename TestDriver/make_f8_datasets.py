"""產生 F8 效能實驗資料：TestInput/F8/candidates_08.json、_12、_16、_20。

規則固定（不使用亂數），重新執行會得到相同的檔案：
- 候選課程 C01、C02…：星期 = 1 + (i mod 5)；開始節次依 (i // 5) mod 3 輪流取第 2、5、7 節；
  i mod 3 == 0 時連續 2 節（2 學分），否則連續 3 節（3 學分）
- i mod 7 == 6 的課程額滿（人數 30／30）
- 必修 REQ：星期一第 a、b 節，2 學分；學生已選 ENR：星期五第 1 節，1 學分
- 學分範圍 9–15
同一天時段重疊的課彼此衝堂（例如 C01 與 C06、C11、C16），額滿與衝堂讓回溯法有東西可剪。

執行：python TestDriver/make_f8_datasets.py
"""

import json
import os

PERIODS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c")
STARTS = ("2", "5", "7")
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TestInput", "F8")


def Course(courseId, day, periods, credits, enrolledCount=0):
    return {
        "course_id": courseId, "title": courseId, "credits": credits, "required": False,
        "teacher": "T", "classroom_id": f"R{courseId}", "capacity": 30, "enrolled_count": enrolledCount,
        "time_slots": [{"day": day, "period": period} for period in periods],
    }


def Candidate(index):
    day = 1 + index % 5
    length = 2 if index % 3 == 0 else 3
    start = PERIODS.index(STARTS[(index // 5) % 3])
    return Course(f"C{index + 1:02d}", day, PERIODS[start:start + length], length,
                  enrolledCount=30 if index % 7 == 6 else 0)


def Dataset(count):
    candidates = [Candidate(index) for index in range(count)]
    return {
        "description": f"F8 效能實驗：{count} 門候選課程（產生規則見 make_f8_datasets.py）",
        "student_id": "S1",
        "database": {
            "courses": [Course("REQ", 1, ("a", "b"), 2), Course("ENR", 5, ("1",), 1), *candidates],
            "students": [{"student_id": "S1", "name": "實驗生", "department": "資工系",
                          "max_credits": 25, "enrolled_courses": ["ENR"]}],
        },
        "preferences": {
            "required_courses": ["REQ"],
            "candidate_courses": [course["course_id"] for course in candidates],
            "min_credits": 9,
            "max_credits": 15,
        },
    }


if __name__ == "__main__":
    os.makedirs(OUTPUT, exist_ok=True)
    for count in (8, 12, 16, 20):
        path = os.path.join(OUTPUT, f"candidates_{count:02d}.json")
        with open(path, "w", encoding="utf-8", newline="\n") as dataFile:
            json.dump(Dataset(count), dataFile, ensure_ascii=False, indent=2)
        print(path)
