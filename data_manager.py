
import json
import os


class DataManager:

  def __init__(self, json_path="04_data_format.json"): #__init__用來接收輸入
    self.json_path = json_path
    self.data = self._load_data() 

  def _load_data(self): #_代表私有函數
    """私有方法：載入 JSON 資料 (含 F6 容錯載入)"""
    if not os.path.exists(self.json_path):
      print(
          f"找不到檔案 {self.json_path}，初始化空白資料庫結構。"
      )
      return {
          "courses": [],
          "students": [],
          "classrooms": [],
          "activities": [],
          "campus_graph": {"nodes": [], "edges": []},
      }

    try:
      with open(self.json_path, "r", encoding="utf-8") as f:
        return json.load(f)
    except json.JSONDecodeError:
      print(f"檔案 {self.json_path} 格式損毀，開啟備份或跳過損毀資料。")
      return {
          "courses": [],
          "students": [],
          "classrooms": [],
          "activities": [],
          "campus_graph": {"nodes": [], "edges": []},
      }

  def save(self):
    """將記憶體中的最新資料寫回硬碟中的 JSON 檔案 (F6 功能)"""
    try:
      with open(self.json_path, "w", encoding="utf-8") as f:
        json.dump(self.data, f, ensure_ascii=False, indent=2)
      return True
    except Exception as e:
      print(f"存檔失敗: {e}")
      return False

  def get_courses(self):
    """取得所有課程清單 (F1, F2, F5, F7, F8 用)"""
    return self.data.get("courses", [])

  def get_students(self):
    """取得所有學生資料 (F1, F2, F3 用)"""
    return self.data.get("students", [])

  def get_classrooms(self):
    """取得所有教室資料 (F4 用)"""
    return self.data.get("classrooms", [])

  def get_activities(self):
    """取得所有校園活動資料 (F4 用)"""
    return self.data.get("activities", [])

  def get_campus_graph(self):
    """取得校園地圖 Graph 節點與邊 (F9 用)"""
    return self.data.get("campus_graph", {})

  
  def add_course(self, course_dict):
    """新增一門課程並自動存檔 (F1)"""
    self.data["courses"].append(course_dict)
    self.save()

  def update_student_courses(self, student_id, new_course_list):
    """更新學生的選課清單並自動存檔 (F1, F2)"""
    for student in self.data.get("students", []):
      if student["student_id"] == student_id:
        student["enrolled_courses"] = new_course_list
        self.save()
        return True
    return False


data_manager = DataManager()