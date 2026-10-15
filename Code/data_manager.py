"""資料存取層：只負責讀檔與存檔，不含任何業務規則 (F6)。

- 不建立全域實例，由呼叫端自行建立 DataManager 後傳入。
- 種子資料 (json_path) 與工作資料 (save_path) 可分開，避免弄髒測資。
"""

import json
import os
import shutil

# 每個區段中，一筆紀錄至少要有的鍵；缺少者視為壞資料並跳過
REQUIRED_KEYS = {
    "classrooms": ("classroom_id", "capacity"),
    "courses": ("course_id", "title", "credits", "classroom_id", "capacity", "time_slots"),
    "students": ("student_id", "name", "max_credits", "enrolled_courses"),
    "activities": ("activity_id", "title", "classroom_id", "time_slots"),
}


def empty_db():
    """回傳一份全新的空資料庫結構。"""
    return {
        "metadata": {},
        "classrooms": [],
        "courses": [],
        "students": [],
        "activities": [],
        "campus_graph": {"nodes": [], "edges": []},
    }


def normalize_db(raw):
    """把讀進來的原始資料整理成標準結構，壞的單筆資料跳過。

    回傳 (db, errors)；errors 為字串清單，說明哪些資料被略過。
    """
    errors = []
    db = empty_db()
    if not isinstance(raw, dict):
        errors.append("最上層不是物件，改用空資料庫")
        return db, errors

    if isinstance(raw.get("metadata"), dict):
        db["metadata"] = raw["metadata"]
    if isinstance(raw.get("campus_graph"), dict):
        db["campus_graph"] = raw["campus_graph"]

    for section, keys in REQUIRED_KEYS.items():
        records = raw.get(section, [])
        if not isinstance(records, list):
            errors.append(f"{section} 不是清單，已略過")
            continue
        for i, rec in enumerate(records):
            if not isinstance(rec, dict):
                errors.append(f"{section}[{i}] 不是物件，已略過")
                continue
            missing = [k for k in keys if k not in rec]
            if missing:
                errors.append(f"{section}[{i}] 缺少欄位 {missing}，已略過")
                continue
            db[section].append(rec)
    return db, errors


def load_db(path):
    """從 JSON 載入資料庫。

    回傳 (db, errors, corrupted)。
    - 檔案不存在：空資料庫，corrupted=False
    - 檔案損毀或無法讀取：空資料庫，corrupted=True
    - 單筆壞資料：略過並寫入 errors
    """
    if not os.path.exists(path):
        return empty_db(), [f"找不到檔案 {path}，使用空資料庫"], False
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        return empty_db(), [f"檔案 {path} 無法讀取：{e}"], True
    db, errors = normalize_db(raw)
    return db, errors, False


def save_db(db, path):
    """原子寫入：先寫暫存檔再取代，避免寫到一半留下半個檔案。回傳 bool。"""
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        return True
    except OSError as e:
        print(f"存檔失敗: {e}")
        return False


class DataManager:
    """持有一份 db 並負責讀寫檔。業務規則請放在 f1_manager 的純函式。"""

    def __init__(self, json_path="04_data_format.json", save_path=None, autosave=True):
        self.json_path = json_path
        self.save_path = save_path or json_path
        self.autosave = autosave
        self.data, self.load_errors, self.corrupted = load_db(json_path)
        if self.corrupted and os.path.exists(json_path):
            # 損毀的原檔先備份，避免之後存檔把它覆蓋成空資料
            shutil.copy2(json_path, json_path + ".corrupt.bak")

    def save(self):
        """寫回 save_path；若載入時檔案損毀且 save_path 就是原檔，拒絕覆蓋。"""
        if self.corrupted and self.save_path == self.json_path:
            print("原檔損毀，為避免覆蓋已拒絕存檔（請指定其他 save_path）")
            return False
        return save_db(self.data, self.save_path)

    def _autosave(self):
        return self.save() if self.autosave else True

    def get_courses(self):
        return self.data["courses"]

    def get_students(self):
        return self.data["students"]

    def get_classrooms(self):
        return self.data["classrooms"]

    def get_activities(self):
        return self.data["activities"]

    def get_campus_graph(self):
        return self.data["campus_graph"]
