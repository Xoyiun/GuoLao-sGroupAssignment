"""資料存取層：只負責讀檔與存檔，不含任何業務規則（功能 F6）。

- 不建立全域實例，由呼叫端自行建立 StorageManager 後傳入。
- 種子資料（jsonPath）與工作資料（savePath）可分開，避免弄髒測資。
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
    DEFAULT_WORK_FILE,
    REQUIRED_KEYS,
    SEED_FILE,
    STUDENT_DATA_DIRECTORY,
    VALID_PERIODS,
)
from TimeSlotUtils import IsValidTimeSlotDay


def AdaptCourseReferenceData(rawData):
    """將參考格式課程與活動欄位轉成程式內部的課程資料。"""
    if not isinstance(rawData, dict):
        return rawData, []

    adaptedData = dict(rawData)
    errors = []
    sourceCourseRecords = rawData.get("course")
    if sourceCourseRecords is not None:
        if not isinstance(sourceCourseRecords, list):
            errors.append("course 不是清單，已略過")
            sourceCourseRecords = []
        adaptedData["courses"] = []
        for index, course in enumerate(sourceCourseRecords):
            adaptedCourse = AdaptReferenceCourse(course, index, errors)
            if adaptedCourse is not None:
                adaptedData["courses"].append(adaptedCourse)
    else:
        adaptedData.setdefault("courses", [])

    activityRecords = rawData.get("activities", [])
    if not isinstance(activityRecords, list):
        errors.append("activities 不是清單，已略過")
        activityRecords = []
    activityIds = set()
    adaptedActivities = []
    for index, activity in enumerate(activityRecords):
        adaptedActivity = AdaptActivityCourse(activity, index, errors)
        adaptedActivities.append(adaptedActivity)
        if isinstance(adaptedActivity, dict) and isinstance(
            adaptedActivity.get("course_id"), str
        ):
            activityIds.add(adaptedActivity["course_id"])
    adaptedData["courses"].extend(adaptedActivities)
    adaptedData["activities"] = []

    students = adaptedData.get("students", [])
    if isinstance(students, list):
        activityIds.update(
            course["course_id"]
            for course in adaptedData["courses"]
            if isinstance(course, dict) and course.get("course_type") == "event"
        )
        for student in students:
            if not isinstance(student, dict):
                continue
            enrolledCourses = student.setdefault("enrolled_courses", [])
            enrolledActivities = student.pop("enrolled_activities", [])
            if isinstance(enrolledCourses, list) and isinstance(enrolledActivities, list):
                enrolledCourses.extend(
                    activityId for activityId in enrolledActivities
                    if activityId in activityIds and activityId not in enrolledCourses
                )
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


def AdaptActivityCourse(activity, index, errors):
    if not isinstance(activity, dict):
        return activity
    activityId = activity.get("activity_id")
    if not isinstance(activityId, str) or not activityId.strip():
        errors.append(f"activities[{index}] 缺少有效 activity_id，已略過")
        return activity
    item = {
        "course_id": activityId,
        "title": activity.get("title"),
        "credits": 0,
        "required": False,
        "teacher": activity.get("teacher", "NPC"),
        "capacity": activity.get("capacity"),
        "classroom_id": activity.get("classroom_id"),
        "time_slots": activity.get("time_slots"),
        "enrolled_count": activity.get("enrolled_count", 0),
        "course_type": "event",
    }
    for fieldName, value in activity.items():
        if fieldName not in {
            "activity_id", "title", "classroom_id", "capacity",
            "enrolled_count", "time_slots", "teacher",
        }:
            item[fieldName] = copy.deepcopy(value)
    return item


def LoadSupplementaryData(rawData, path):
    """從種子資料旁的固定資料檔補入教室與校園圖。"""
    errors = []
    if not isinstance(rawData, dict):
        return rawData, errors

    directory = (
        os.path.abspath(path)
        if os.path.isdir(path)
        else os.path.dirname(os.path.abspath(path))
    )

    if "campus_graph" not in rawData:
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

    if "classrooms" not in rawData:
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
    buildingId = classroomId.split("-", 1)[0] if isinstance(classroomId, str) else ""
    return {
        "classroom_id": classroomId,
        "building_id": room.get("building_id") or buildingId,
        "building_name": room.get("building_name")
        or buildingNames.get(buildingId, ""),
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
        "enrolled_activities": IsStringList,
    },
    "activities": {
        "activity_id": IsNonemptyString, "title": IsNonemptyString, "classroom_id": IsNonemptyString,
        "time_slots": IsTimeSlotList,
    },
}


def CreateEmptyDatabase():
    """回傳一份全新的空資料庫結構。"""
    return {
        "metadata": {},
        "classrooms": [],
        "courses": [],
        "students": [],
        "activities": [],
        "campus_graph": {"nodes": [], "edges": []},
    }


def NormalizeDatabase(rawData):
    """把讀進來的原始資料整理成標準結構，壞的單筆資料跳過。

    回傳 (database, errors)；errors 為字串清單，說明哪些資料被略過。
    """
    errors = []
    database = CreateEmptyDatabase()
    if not isinstance(rawData, dict):
        errors.append("最上層不是物件，改用空資料庫")
        return database, errors

    rawData, adaptationErrors = AdaptCourseReferenceData(rawData)
    errors.extend(adaptationErrors)
    if isinstance(rawData.get("metadata"), dict):
        database["metadata"] = rawData["metadata"]
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
    """從 ID 分檔目錄或舊版 JSON 載入資料庫。

    回傳 (database, errors, corrupted)。
    - 分檔目錄：讀取 Courses/ 與 Students/，固定資料由同目錄補入
    - 舊版 JSON：繼續支援單一種子檔或 db.json
    - 檔案不存在：空資料庫，corrupted=False
    - 檔案損毀或無法讀取：空資料庫，corrupted=True
    - 單筆壞資料：略過並寫入 errors
    """
    if os.path.isdir(path):
        courseDirectory = os.path.join(path, COURSE_DATA_DIRECTORY)
        studentDirectory = os.path.join(path, STUDENT_DATA_DIRECTORY)
        if os.path.isdir(courseDirectory) or os.path.isdir(studentDirectory):
            rawData, errors = LoadEntityDirectory(path)
            rawData, companionErrors = LoadSupplementaryData(rawData, path)
            database, normalizationErrors = NormalizeDatabase(rawData)
            return database, errors + companionErrors + normalizationErrors, False

        legacyPath = next(
            (
                os.path.join(path, fileName)
                for fileName in (DEFAULT_WORK_FILE, SEED_FILE)
                if os.path.isfile(os.path.join(path, fileName))
            ),
            None,
        )
        if legacyPath is None:
            return CreateEmptyDatabase(), [f"找不到資料檔：{path}"], False
        path = legacyPath
    if not os.path.exists(path):
        return CreateEmptyDatabase(), [f"找不到檔案 {path}，使用空資料庫"], False
    try:
        with open(path, "r", encoding="utf-8") as dataFile:
            rawData = json.load(dataFile)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
        return CreateEmptyDatabase(), [f"檔案 {path} 無法讀取：{error}"], True
    rawData, companionErrors = LoadSupplementaryData(rawData, path)
    database, errors = NormalizeDatabase(rawData)
    errors[:0] = companionErrors
    return database, errors, False


def SaveDatabase(database, path):
    """將資料分別寫入 ID.json；單一檔案仍採原子取代方式。"""
    if os.path.isdir(path):
        return SaveEntityDirectory(database, path)

    temporaryFilePath = path + ".tmp"
    try:
        with open(temporaryFilePath, "w", encoding="utf-8") as dataFile:
            json.dump(database, dataFile, ensure_ascii=False, indent=2)
        os.replace(temporaryFilePath, path)
        return True
    except OSError:
        return False


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
    temporaryFilePath = filePath + ".tmp"
    with open(temporaryFilePath, "w", encoding="utf-8") as dataFile:
        json.dump(record, dataFile, ensure_ascii=False, indent=2)
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
            "building_id": classroom.get("building_id", ""),
            "building_name": classroom.get("building_name", ""),
            "capacity": classroom["capacity"],
            "equipment": classroom.get("equipment", []),
        })
        records.append(record)
    return records


def SaveEntityDirectory(database, path):
    """原子更新 ID.json 資料夾，並移除已刪除資料對應的舊檔。"""
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

    def __init__(self, jsonPath="04_data_format.json", savePath=None, autosave=True):
        self.jsonPath = jsonPath
        self.defaultSavePath = savePath is None
        if savePath is None:
            sourceDirectory = (
                os.path.abspath(jsonPath)
                if os.path.isdir(jsonPath)
                else os.path.dirname(os.path.abspath(jsonPath))
            )
            savePath = os.path.join(sourceDirectory, DEFAULT_WORK_FILE)
        self.savePath = savePath
        self.autosave = autosave
        self.data, self.loadErrors, self.corrupted = LoadDatabase(jsonPath)
        if self.corrupted:
            corruptedPath = jsonPath
            if os.path.isdir(jsonPath):
                corruptedPath = next(
                    (
                        os.path.join(jsonPath, fileName)
                        for fileName in (DEFAULT_WORK_FILE, SEED_FILE)
                        if os.path.isfile(os.path.join(jsonPath, fileName))
                    ),
                    "",
                )
            if corruptedPath and os.path.isfile(corruptedPath):
                shutil.copy2(corruptedPath, corruptedPath + ".corrupt.bak")

    def Save(self):
        """寫回 savePath；若載入時檔案損毀且目標是原檔或預設路徑，拒絕存檔並回傳 False。"""
        sameFile = os.path.abspath(
            self.savePath) == os.path.abspath(self.jsonPath)
        if self.corrupted and (sameFile or self.defaultSavePath):
            return False
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
        return [*self.data["activities"], *eventCourses]

    def GetCampusGraph(self):
        return self.data["campus_graph"]
