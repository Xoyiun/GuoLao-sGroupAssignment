"""資料存取層：只負責讀檔與存檔，不含任何業務規則 (F6)。

- 不建立全域實例，由呼叫端自行建立 DataManager 後傳入。
- 種子資料 (json_path) 與工作資料 (save_path) 可分開，避免弄髒測資。
"""

import json
import os
import shutil
# 讀檔時若單筆資料缺少這些鍵（視為資料損毀），將自動略過該筆，以確保系統穩定性。
REQUIRED_KEYS = {
    "classrooms": ("classroom_id", "capacity"), #這裡capacity指的是實體座位數
    "courses": (
        "course_id", "title", "credits", "required", "teacher",
        "classroom_id", "capacity", "time_slots", #這裡是多收幾個學生
    ),
    "students": (
        "student_id", "name", "department", "max_credits",
        "enrolled_courses",
    ),
    "activities": ("activity_id", "title", "classroom_id", "time_slots"),
}


def empty_db():
    """回傳一份全新的空資料庫結構。"""
    return {
        "metadata": {},  #不用看 寫version的
        "classrooms": [],
        "courses": [],
        "students": [],
        "activities": [],
        "campus_graph": {"nodes": [], "edges": []}, #後面的功能 目前不用看
    }#作用就是提供一個安全、標準的預設空資料庫骨架


def normalize_db(raw): #raw是從json檔案讀取出來 最乾淨的原始資料raw data
    """把讀進來的原始資料整理成標準結構，壞的單筆資料跳過。

    回傳 (db, errors)；errors 為字串清單，說明哪些資料被略過。
    """
    errors = []
    db = empty_db()
    if not isinstance(raw, dict):  #做個保護 如果json檔案被刪除或是有問題 則觸發
        errors.append("最上層不是物件，改用空資料庫")#isinstance 是做檢查一個物件是否為某個已知類型（Type）或類別（Class）的實例 這邊檢查的是raw是不是一個dict 
        return db, errors   #db是乾淨的資料 errors是其中找到的錯誤

    if isinstance(raw.get("metadata"), dict): #跟前面同理 如果是乾淨的資料都塞進db裡面
        db["metadata"] = raw["metadata"]   
    if isinstance(raw.get("campus_graph"), dict):
        db["campus_graph"] = raw["campus_graph"]

    for section, keys in REQUIRED_KEYS.items():   #很簡單的for迴圈去篩選重要的資料 不重要的忽略
        records = raw.get(section, [])  #record會拿到大陣列 
        if not isinstance(records, list):
            errors.append(f"{section} 不是清單，已略過")
            continue
        for i, rec in enumerate(records):   #enumerate 它會把清單裡的每一筆資料自動配對成 (編號, 資料) 的組合
            if not isinstance(rec, dict):
                errors.append(f"{section}[{i}] 不是物件，已略過")
                continue
            missing = [k for k in keys if k not in rec]
            if missing:
                errors.append(f"{section}[{i}] 缺少欄位 {missing}，已略過")
                continue
            db[section].append(rec)
    return db, errors


def load_db(path):  #跟normalize_db(raw)做連動 讀取json檔案給raw 把raw傳給normalize_db
    """從 JSON 載入資料庫。

    回傳 (db, errors, corrupted)。
    - 檔案不存在：空資料庫，corrupted=False
    - 檔案損毀或無法讀取：空資料庫，corrupted=True
    - 單筆壞資料：略過並寫入 errors
    """
    if not os.path.exists(path): #去確認這個檔案是否存在
        return empty_db(), [f"找不到檔案 {path}，使用空資料庫"], False 
    try:
        with open(path, "r", encoding="utf-8") as f: #如果成功找到的話就去打開做read 
            raw = json.load(f)                       #json.load()去翻譯json文字 翻譯成python可以看懂的字典和list
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e: #(JSON 格式解析錯誤,文字編碼錯誤,作業系統層級錯誤)
        return empty_db(), [f"檔案 {path} 無法讀取：{e}"], True
    db, errors = normalize_db(raw)
    return db, errors, False


def save_db(db, path):
    """原子寫入：先寫暫存檔再取代，避免寫到一半留下半個檔案。回傳 bool。"""
    tmp_path = path + ".tmp" #把我原本的檔案.json後面再取一個.tmp 做佔存
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2) #dump跟load相反 dump是把程式碼翻譯成json存回去 db是我要存進去的資料 f是目標位置
        os.replace(tmp_path, path)                         #ensure_ascii=False保證中文不會被翻譯成亂碼 indent = 2 自動排版
        return True
    except OSError as e:
        print(f"存檔失敗: {e}")
        return False


DEFAULT_WORK_FILE = "db.json"  # 沒指定 save_path 時預設寫入的工作檔檔名


class DataManager:
    """持有一份 db 並負責讀寫檔。業務規則請放在 F1_DataManager.py 的純函式。"""

    def __init__(self, json_path="04_data_format.json", save_path=None, autosave=True):  #拿完資料馬上備份 怕出問題時還有備份
        self.json_path = json_path
        self._default_save_path = save_path is None          # 記下是不是用預設值，save() 要用
        if save_path is None:
            save_path = os.path.join(os.path.dirname(os.path.abspath(json_path)), DEFAULT_WORK_FILE) #沒有寫save_path的時候預設路徑為db.json不會寫回種子檔
        self.save_path = save_path
        self.autosave = autosave
        self.data, self.load_errors, self.corrupted = load_db(json_path) #load_db把乾淨資料db拿出來
        if self.corrupted and os.path.exists(json_path): #確認檔案存在和檔案確實壞了 但是檔案本身沒問題是電腦看不懂(例如少了一個逗號或括號，導致 json.load() 解析失敗)
            # 損毀的原檔先備份，避免之後存檔把它覆蓋成空資料
            shutil.copy2(json_path, json_path + ".corrupt.bak")  #shutil 專門處理檔案操作的模組 copy2是copy增強版會把檔案的建立時間和最後修改時間等屬性一併完美複製過去
                                                                 #會把原本檔名加上.corrupt.bak 備份檔 .bak是約定俗成的附檔名
    def save(self):
        """寫回 save_path；若載入時檔案損毀，且 save_path 是原檔或是沒指定的預設值，拒絕存檔。"""
        same_file = os.path.abspath(self.save_path) == os.path.abspath(self.json_path)  
        if self.corrupted and (same_file or self._default_save_path):
            print("原檔損毀，為避免覆蓋已拒絕存檔（請指定其他 save_path）") 
            return False 
        return save_db(self.data, self.save_path)

    def _autosave(self):
        return self.save() if self.autosave else True   #f6會用到

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


    #辛苦了讀到這裡 先去休息一下吧還有很多lol
    #最後做個總結快速幫你複習 先創一個空表格做之後的保險 load_db會跟normalize_db做對應把乾淨的資料拿出來 每一個def都有寫保護機制不會汙染到種子檔
    #__init__是做拿資料並且備份防止資料汙染 DataManager裡面有f1_manager所需要的所有函式