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

def find_course_in_timeable(timeable, course_id):
    """回傳有目標課程的位置（星期、節次)"""
    result=[]
    for day_index, row in enumerate(timeable):
        for period_index, cell in enumerate(row):
            if cell==course_id:
                result.append((day_index + 1,PERIODS[period_index]))
    return result

def summarize_timeable(timeable, db, student_id):
   """回傳每天的節數、總學分數，以及空堂數。"""
   for row in timeable:
       daily_period_counts=[len(row)-row.count(None)]
   student=next((s for s in db["students"] if s["student_id"]==student_id),None)
   
   total_credits=0
   if student is not None:
       selected_ids=set(student["enrolled_courses"])
       for course in db["courses"]:
           if course["course_id"] in selected_ids:
               total_credits+=course["credits"]
   
   free_period_count= sum(
       cell is None
       for row in timeable
       for cell in row
   )

   return{
       "daily_period_counts":daily_period_counts,
       "total_credits":total_credits,
       "free_period_count":free_period_count,
   }

def find_free_slots(timeable, day, start_period, end_period, min_length=1):
    """在指定的某一天及範圍內，尋找連續的空堂區間


    回傳由 (開始節次, 結束節次) 組成的數對清單。
     範例：[("3", "5"), ("8", "8")]"""

    if not 1<=day<=7:
        raise ValueError("day must be between 1 and 7")
    
    if start_period not in PERIODS or end_period not in PERIODS:
        raise ValueError("invalid period")

    start_index=PERIODS.index(start_period)
    end_index=PERIODS.index(end_period)

    if start_index>end_index:
        raise ValueError("start_period must not be after end_period")

    row=timeable(day-1)
    free_slots=[]
    run_start=None

    for i in range(start_index, end_index+1):
        if row[i] is None:
            if run_start is None:
                run_start=i
        elif run_start is not None:
            run_length=i-run_start
            if run_length>=min_length:
                free_slots.append((PERIODS[run_start], PERIODS[i-1]))
                run_start=None

    #處理空檔持續到最後一節的情況
    if run_start is not None:
        run_length=end_index-run_start+1
        if run_length>=min_length:
            free_slots.append((PERIODS[run_start],PERIODS[end_index]))

    return free_slots

def query_timeable(timeable, day=None, period=None, course_id=None):
    """依星期、節次及／或課程代碼查詢課表格子。

    可以傳入單一條件，也可以組合多個條件。
    回傳結果為 (星期, 節次, 課程代碼) 的清單。"""

    if day is not None and not 1<=day<=7:
        raise ValueError("day must be between 1 and 7")
    if period is not None and period not in PERIODS:
        raise ValueError("invalid period")

    results=[]

    for day_index, row in enumerate(timeable):
        current_day=day_index+1

        if day is not None and current_day != day:
            continue

        for period_index, course in enumerate(row):
            current_period=PERIODS[period_index]

            if course is None:
                continue
            if period is not None and current_period !=period:
                continue
            if course_id is not None and course !=course_id:
                continue
            results.append((current_day, current_period, course))

    return results






    


   

       

