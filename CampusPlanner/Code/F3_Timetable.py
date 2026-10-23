PERIODS = ("1", "2", "3", "4", "5", "6","7","8","9","a","b","c")

def build_timetable(db, student_id):
     """建立並回傳 7 天 × 12 節的課表矩陣."""
     timeable=[[None for _ in PERIODS]for _ in range (7)]

    #查詢學生
     student=next((s for s in db["students"] if s["student_id"]==student_id),None)
     if student is None:
        return None
    #取得學生選的每門課 
     selected_ids=student["enrolled_courses"]
     for course in db["courses"]:
        if course["course_id"] not in selected_ids:
            continue
    #把課程的所有節次標記到課表矩陣中
     for slot in course["time_slots"]:
         day_index=slot["day"]-1
         period_index=PERIODS.index(slot["period"])
         timeable[day_index][period_index]=course["course_id"]
     return timeable
               
