"""資料存取層：只負責讀檔與存檔，不含任何業務規則（功能 F6）。

- 不建立全域實例，由呼叫端自行建立 StorageManager 後傳入。
- 資料一律按 ID 分檔：Courses/{course_id}.json、Students/{student_id}.json，
  教室與校園圖放在同資料夾的 Classroom.json、CampusGraph.json。
- 讀取的資料夾（dataDirectory）與寫回的資料夾（savePath）可分開，避免弄髒測資。
- 依 Reference/Formate 正規化動態資料，並合併獨立的教室與校園圖固定資料。
- 副程式只負責執行讀寫與狀態回傳（True/False），不主動印出介面文字。
"""

import copy
import json
import os
import shutil

from Constants import (
    CAMPUS_GRAPH_FILE,
    CLASSROOM_FILE,
    COURSE_DATA_DIRECTORY,
    REQUIRED_KEYS,
    STUDENT_DATA_DIRECTORY,
    VALID_PERIODS,
)
from TimeSlotUtils import IsValidTimeSlotDay


def AdaptCourseReferenceData(rawData):
    """將 Courses/ 讀到的參考格式課程（含 event 活動）轉成程式內部的課程資料。"""
    adaptedData = dict(rawData)
    errors = []
    adaptedData["courses"] = []
    for index, course in enumerate(rawData.get("course", [])):
        adaptedCourse = AdaptReferenceCourse(course, index, errors)
        if adaptedCourse is not None:
            adaptedData["courses"].append(adaptedCourse)
    return adaptedData, errors


def AdaptReferenceCourse(course, index, errors):
    if not isinstance(course, dict):
        return course

    item = dict(course)
    courseType = item.pop("type", None)
    if courseType == "Required":
        item["required"] = True
    elif courseType in ("unRequired", "Optional", "event"):
        item["required"] = False
    elif courseType is not None:
        errors.append(
            f"course[{index}] type 必須是 Required、unRequired、Optional 或 event，已略過"
        )
        return None
    if courseType is not None:
        item["course_type"] = courseType
    if "name" in item:
        item["title"] = item.pop("name")
    if "classroom" in item:
        item["classroom_id"] = item.pop("classroom")
    return item


def LoadSupplementaryData(rawData, directory):
    """從資料夾中的固定資料檔補入教室與校園圖。"""
    errors = []

    graphPath = os.path.join(directory, CAMPUS_GRAPH_FILE)
    try:
        with open(graphPath, "r", encoding="utf-8") as file:
            graphData = json.load(file)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
        errors.append(f"固定資料檔 {graphPath} 無法讀取：{error}")
    else:
        graph = graphData.get("campus_graph") if isinstance(
            graphData, dict) else None
        if not isinstance(graph, dict):
            errors.append(f"固定資料檔 {graphPath} 缺少 campus_graph 物件")
        else:
            rawData["campus_graph"] = graph

    classroomPath = os.path.join(directory, CLASSROOM_FILE)
    try:
        with open(classroomPath, "r", encoding="utf-8") as file:
            classroomData = json.load(file)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
        errors.append(f"固定資料檔 {classroomPath} 無法讀取：{error}")
    else:
        records = classroomData.get("classroom") if isinstance(
            classroomData, dict) else None
        if not isinstance(records, list):
            errors.append(f"固定資料檔 {classroomPath} 缺少 classroom 清單")
        else:
            graph = rawData.get("campus_graph", {})
            nodes = graph.get("nodes", []) if isinstance(
                graph, dict) else []
            buildingNames = {
                node.get("node_id"): node.get("name", "")
                for node in nodes
                if isinstance(node, dict) and isinstance(node.get("node_id"), str)
            }
            rawData["classrooms"] = [
                AdaptReferenceClassroom(room, buildingNames)
                for room in records
            ]

    return rawData, errors


def AdaptReferenceClassroom(room, buildingNames):
    """將 Reference/Formate 的教室欄位補成內部資料模型。"""
    if not isinstance(room, dict):
        return room

    classroomId = room.get("room_id")
    roomPrefix = classroomId.split("-", 1)[0] if isinstance(classroomId, str) else ""
    buildingId = roomPrefix if roomPrefix in buildingNames else ""
    return {
        "classroom_id": classroomId,
        "building_id": buildingId,
        "building_name": buildingNames.get(buildingId, ""),
        "capacity": room.get("capacity"),
        "equipment": room.get("equipment"),
    }


# ---- 欄位格式檢查：只擋「型別錯了會讓程式當掉」的資料；其他業務規則由資料管理層檢查 ----
def IsInteger(value):
    """bool 也是 int 的子類別，要排除 True/False。"""
    return isinstance(value, int) and not isinstance(value, bool)


def IsNonemptyString(value):
    return isinstance(value, str) and value.strip() != ""


def IsBoolean(value):
    return isinstance(value, bool)


def IsStringList(value):
    return isinstance(value, list) and all(isinstance(value, str) for value in value)


def IsTimeSlotList(value):
    """接受星期值或時間戳 day，並確認節次格式正確。"""
    return isinstance(value, list) and all(
        isinstance(timeSlot, dict)
        and IsValidTimeSlotDay(timeSlot.get("day"))
        and timeSlot.get("period") in VALID_PERIODS
        for timeSlot in value
    )


# 有出現就要檢查格式的欄位（必填欄位是否存在仍由 REQUIRED_KEYS 檢查）
FIELDCHECKS = {
    "classrooms": {
        "classroom_id": IsNonemptyString, "capacity": IsInteger, "equipment": IsStringList,
    },
    "courses": {
        "course_id": IsNonemptyString, "title": IsNonemptyString, "credits": IsInteger, "required": IsBoolean,
        "teacher": IsNonemptyString, "classroom_id": IsNonemptyString, "capacity": IsInteger,
        "enrolled_count": IsInteger, "time_slots": IsTimeSlotList,
    },
    "students": {
        "student_id": IsNonemptyString, "name": IsNonemptyString, "department": IsNonemptyString,
        "grade": IsInteger, "max_credits": IsInteger, "enrolled_courses": IsStringList,
    },
}


def CreateEmptyDatabase():
    """回傳一份全新的空資料庫結構。"""
    return {
        "metadata": {},
        "classrooms": [],
        "courses": [],
        "students": [],
        "campus_graph": {"nodes": [], "edges": []},
    }


def NormalizeDatabase(rawData):
    """把讀進來的原始資料整理成標準結構，壞的單筆資料跳過。

    回傳 (database, errors)；errors 為字串清單，說明哪些資料被略過。
    """
    errors = []
    database = CreateEmptyDatabase()
    rawData, adaptationErrors = AdaptCourseReferenceData(rawData)
    errors.extend(adaptationErrors)
    if isinstance(rawData.get("campus_graph"), dict):
        database["campus_graph"] = rawData["campus_graph"]

    for section, keys in REQUIRED_KEYS.items():
        records = rawData.get(section, [])
        if not isinstance(records, list):
            errors.append(f"{section} 不是清單，已略過")
            continue
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                errors.append(f"{section}[{index}] 不是物件，已略過")
                continue
            missing = [fieldName for fieldName in keys if fieldName not in record]
            if missing:
                errors.append(f"{section}[{index}] 缺少欄位 {missing}，已略過")
                continue
            invalidFields = [
                fieldName
                for fieldName, check in FIELDCHECKS[section].items()
                if fieldName in record and not check(record[fieldName])
            ]
            if invalidFields:
                errors.append(
                    f"{section}[{index}] 欄位格式錯誤 {invalidFields}，已略過"
                )
                continue
            database[section].append(record)
    return database, errors


def LoadEntityDirectory(path):
    """從 Courses/ 與 Students/ 的 ID.json 檔案讀取資料。"""
    rawData = {"course": [], "students": []}
    errors = []
    for directoryName, section, idField in (
        (COURSE_DATA_DIRECTORY, "course", "course_id"),
        (STUDENT_DATA_DIRECTORY, "students", "student_id"),
    ):
        sectionPath = os.path.join(path, directoryName)
        if not os.path.isdir(sectionPath):
            continue
        for fileName in sorted(os.listdir(sectionPath)):
            if not fileName.lower().endswith(".json"):
                continue
            filePath = os.path.join(sectionPath, fileName)
            try:
                with open(filePath, "r", encoding="utf-8") as dataFile:
                    record = json.load(dataFile)
            except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
                errors.append(f"資料檔 {filePath} 無法讀取：{error}")
                # 下次存檔會清掉沒載入的檔案，先備份；.bak 不是 .json，之後讀檔也會略過
                try:
                    shutil.copy2(filePath, filePath + ".corrupt.bak")
                except OSError:
                    pass
                continue
            if not isinstance(record, dict):
                errors.append(f"資料檔 {filePath} 不是物件，已略過")
                continue
            recordId = record.get(idField)
            if not isinstance(recordId, str) or fileName != f"{recordId}.json":
                errors.append(f"資料檔 {filePath} 的 ID 與檔名不一致，已略過")
                continue
            rawData[section].append(record)
    return rawData, errors


def LoadDatabase(path):
    """從資料夾載入資料庫：Courses/、Students/ 的 ID.json，加上 Classroom.json、CampusGraph.json。

    回傳 (database, errors)。
    - 資料夾不存在：空資料庫
    - 單一檔案無法讀取或單筆資料格式錯誤：略過該筆並寫入 errors，其他資料照常載入
    """
    if not os.path.isdir(path):
        return CreateEmptyDatabase(), [f"找不到資料夾 {path}，使用空資料庫"]
    rawData, errors = LoadEntityDirectory(path)
    rawData, companionErrors = LoadSupplementaryData(rawData, path)
    database, normalizationErrors = NormalizeDatabase(rawData)
    return database, errors + companionErrors + normalizationErrors


def IsSafeRecordId(recordId):
    return (
        isinstance(recordId, str)
        and bool(recordId)
        and recordId not in (".", "..")
        and os.path.basename(recordId) == recordId
        and "/" not in recordId
        and "\\" not in recordId
    )


def WriteJsonFile(record, filePath):
    """內容跟檔案現有的一樣就不寫（每次存檔不必重寫所有檔案）；要寫時先寫暫存檔再取代。"""
    content = json.dumps(record, ensure_ascii=False, indent=2)
    try:
        with open(filePath, "r", encoding="utf-8") as dataFile:
            if dataFile.read() == content:
                return
    except (OSError, UnicodeDecodeError):
        pass  # 檔案不存在或讀不了，就照常寫入
    temporaryFilePath = filePath + ".tmp"
    with open(temporaryFilePath, "w", encoding="utf-8") as dataFile:
        dataFile.write(content)
    os.replace(temporaryFilePath, filePath)


def CourseRecordForFile(course):
    courseType = course.get("course_type")
    if courseType not in ("Required", "unRequired", "Optional", "event"):
        courseType = "Required" if course.get("required") else "unRequired"
    internalFields = {
        "course_id", "title", "credits", "required", "teacher",
        "classroom_id", "capacity", "time_slots", "enrolled_count",
        "course_type",
    }
    record = {
        fieldName: copy.deepcopy(value)
        for fieldName, value in course.items()
        if fieldName not in internalFields
    }
    record.update({
        "course_id": course["course_id"],
        "name": course["title"],
        "credits": course["credits"],
        "type": courseType,
        "teacher": course["teacher"],
        "capacity": course["capacity"],
        "classroom": course["classroom_id"],
        "time_slots": course["time_slots"],
        "enrolled_count": course.get("enrolled_count", 0),
    })
    return record


def ClassroomRecordsForFile(classrooms):
    internalFields = {
        "classroom_id", "building_id", "building_name", "capacity", "equipment",
    }
    records = []
    for classroom in classrooms:
        record = {
            fieldName: copy.deepcopy(value)
            for fieldName, value in classroom.items()
            if fieldName not in internalFields
        }
        record.update({
            "room_id": classroom["classroom_id"],
            "capacity": classroom["capacity"],
            "equipment": classroom.get("equipment", []),
        })
        records.append(record)
    return records


def SaveDatabase(database, path):
    """把資料寫回資料夾：每筆一個 ID.json（原子取代），並移除已刪除資料對應的舊檔。回傳 bool。"""
    courseDirectory = os.path.join(path, COURSE_DATA_DIRECTORY)
    studentDirectory = os.path.join(path, STUDENT_DATA_DIRECTORY)
    try:
        os.makedirs(courseDirectory, exist_ok=True)
        os.makedirs(studentDirectory, exist_ok=True)
        recordsByDirectory = (
            (
                courseDirectory,
                (
                    (course["course_id"], CourseRecordForFile(course))
                    for course in database["courses"]
                ),
            ),
            (
                studentDirectory,
                (
                    (student["student_id"], student)
                    for student in database["students"]
                ),
            ),
        )
        for directory, records in recordsByDirectory:
            expectedFileNames = set()
            for recordId, record in records:
                if not IsSafeRecordId(recordId):
                    return False
                fileName = f"{recordId}.json"
                expectedFileNames.add(fileName)
                WriteJsonFile(record, os.path.join(directory, fileName))
            for fileName in os.listdir(directory):
                if fileName.lower().endswith(".json") and fileName not in expectedFileNames:
                    os.remove(os.path.join(directory, fileName))
        WriteJsonFile(
            {"classroom": ClassroomRecordsForFile(database["classrooms"])},
            os.path.join(path, CLASSROOM_FILE),
        )
        return True
    except OSError:
        return False


class StorageManager:
    """持有一份資料庫並負責讀寫檔案；業務規則由其他模組的純函式處理。"""

    def __init__(self, dataDirectory, savePath=None, autosave=True):
        """dataDirectory：要讀取的資料夾；savePath：要寫回的資料夾，沒指定就寫回 dataDirectory。"""
        self.dataDirectory = dataDirectory
        self.savePath = dataDirectory if savePath is None else savePath
        self.autosave = autosave
        self.data, self.loadErrors = LoadDatabase(dataDirectory)

    def Save(self):
        """寫回 savePath，回傳 bool。"""
        return SaveDatabase(self.data, self.savePath)

    def AutoSave(self):
        return self.Save() if self.autosave else True

    def GetCourses(self):
        return self.data["courses"]

    def GetStudents(self):
        return self.data["students"]

    def GetClassrooms(self):
        return self.data["classrooms"]

    def GetActivities(self):
        eventCourses = [
            {
                "activity_id": course["course_id"],
                "title": course["title"],
                "classroom_id": course["classroom_id"],
                "capacity": course["capacity"],
                "enrolled_count": course.get("enrolled_count", 0),
                "time_slots": course["time_slots"],
            }
            for course in self.data["courses"]
            if course.get("course_type") == "event"
        ]
        return eventCourses

    def GetCampusGraph(self):
        return self.data["campus_graph"]
