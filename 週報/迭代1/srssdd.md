# 校園選課與課表規劃系統
## 系統需求設計規格書 V1.0
### Software Requirements Specification (SRS) / Software Design Document (SDD)

* A 索云（組長）
* B 阿福
* C Steve
* D 竹
* E 晴
* F minnn

**Department of Computer Science & Information Engineering**  
**National Taipei University of Technology**  
**2026/10/18**

> **修改紀錄（2026-10-19）：** 配合專案改用 `CampusPlanner` 架構，F1 程式由 `Code/` 搬到 `CampusPlanner/Code/` 並在檔名加上 F 編號：`f1_manager.py` → `F1_DataManager.py`、`data_manager.py` → `F6_StorageManager.py`、`main.py` → `Main.py`；測試搬到 `CampusPlanner/TestDriver/`，種子資料搬到 `CampusPlanner/UserData/`。函式名稱、參數與回傳值都沒有改變，本報告的路徑、架構圖、呼叫範例與測試執行方式已同步更新。
>
> **修改紀錄（2026-10-20）：** 修正兩個缺陷（見 3.3 節缺陷紀錄）。時段規格常數 `VALID_DAYS`、`VALID_PERIODS` 從 `F1_DataManager.py` 改放到 `F6_StorageManager.py`，讓 F6 讀檔時也能用同一份規格；`F1_DataManager.py` 會從 F6 匯入，原本的 `f1.VALID_PERIODS` 寫法照樣能用。`add_classroom` 的設備清單改為每一項都必須是文字。測試由 101 項增加為 112 項。

---

## 目錄 (Table of Contents)

- [1. 簡介 (Introduction)](#1-簡介-introduction)
  - [1.1 目標 (Purpose)](#11-目標-purpose)
  - [1.2 系統名稱 (Identification)](#12-系統名稱-identification)
  - [1.3 概觀 (Overview)](#13-概觀-overview)
- [2. 系統 (System)](#2-系統-system)
  - [2.1 系統描述 (System Description)](#21-系統描述-system-description)
    - [2.1.1 使用案例模型 (Use Case Model)](#211-使用案例模型-use-case-model)
    - [2.1.2 系統架構圖 (System Architecture Diagram)](#212-系統架構圖-system-architecture-diagram)
  - [2.2 系統資料 (System Data)](#22-系統資料-system-data)
    - [2.2.1 資料格式 (Data Format)](#221-資料格式-data-format)
- [3. 軟體設計 (Software Design)](#3-軟體設計-software-design)
  - [3.1 函式功能介面 (Functionality Interface)](#31-函式功能介面-functionality-interface)
  - [3.2 測試案例設計 (Test case design)](#32-測試案例設計-test-case-design)
  - [3.3 專案審查 (Iteration Review 1)](#33-專案審查-iteration-review-1)
- [4. 專案管理 (Project Management)](#4-專案管理-project-management)
  - [4.1 工作分解表 (Work Breakdown Structure)](#41-工作分解表-work-breakdown-structure)
  - [4.2 版本控管 (Version Control)](#42-版本控管-version-control)
  - [4.3 Code Review 紀錄](#43-code-review-紀錄)
- [Glossary](#glossary)
- [References](#references)
- [Appendix](#appendix)

---

## 1. 簡介 (Introduction)

### 1.1 目標 (Purpose)
本系統旨在以 Python 命令列介面提供校園課程、學生與教室資料管理，並依需求規劃選課衝突檢查、課表與活動安排、最佳化搜尋、校園路徑及動態重排等功能。各功能依需求規格與工作分解表分階段開發；本報告會區分目前已有程式與尚待實作項目。

### 1.2 系統名稱 (Identification)
校園選課與課表規劃系統 (Campus Course Registration and Timetable Planning System)

### 1.3 概觀 (Overview)
依需求規格，系統規劃 F1–F11：資料管理、衝突檢查、課表顯示、校園活動、課程篩選、資料持久化、最佳課表搜尋、演算法比較、路徑規劃、動態重新規劃及 AI 協作品質改善。目前可執行的主要內容為 F1 課程／學生／教室資料管理，以及 F6 的 JSON 載入與儲存基礎；其他功能仍在規劃或尚未實作。系統採模組化 Python CLI，並以自動化測試驗證現有功能。

---

## 2. 系統 (System)

### 2.1 系統描述 (System Description)
本系統為 Python 命令列程式，依需求規格提供課程、學生、教室資料的管理基礎，並規劃後續選課與課表相關功能。現有 CLI 以管理者操作流程為主，尚未實作帳號登入或角色權限區分。

目前程式位於 [`CampusPlanner/Code/`](../../CampusPlanner/Code/)：[`Main.py`](../../CampusPlanner/Code/Main.py) 負責 CLI 輸入解析、流程及訊息；[`F1_DataManager.py`](../../CampusPlanner/Code/F1_DataManager.py) 提供 F1 資料驗證、查詢與 CRUD 純函式，以及接上存檔的 `F1Manager`；[`F6_StorageManager.py`](../../CampusPlanner/Code/F6_StorageManager.py) 負責 JSON 載入、資料正規化與儲存。自動化測試位於 [`CampusPlanner/TestDriver/`](../../CampusPlanner/TestDriver/) 的 [`test_f1.py`](../../CampusPlanner/TestDriver/test_f1.py) 與 [`test_main.py`](../../CampusPlanner/TestDriver/test_main.py)。同資料夾中 F2–F5、F7–F10 的檔案（如 `F2_ConflictChecker.py`）目前是空檔，只先建立好各模組的位置，尚未實作。

#### 2.1.1 使用案例模型 (Use Case Model)
依 [`UseCase.md`](../../規格書與分工表/UseCase.md)，主要情境為 UC-01 新增課程、UC-02 依條件查詢課程、UC-03 修改／刪除資料及刪除限制。實作現況如下：

| 使用案例 | 主要流程與規則 | 實作狀態 |
| :--- | :--- | :--- |
| UC-01 新增課程 | 管理者輸入課程資料；系統檢查代號唯一、學分、容量、教室與時段後新增 | 已有 CLI 與 F1 函式 |
| UC-02 查詢課程 | 可依課程代號、教師、星期、必選修及是否尚有名額篩選；條件同時指定時採 AND | 已有 CLI 與 F1 函式；名額條件目前僅篩選有／無名額 |
| UC-03 修改／刪除 | 可修改課程與學生資料；已有學生選修的課程不可刪除 | 已有課程／學生 CRUD；教室僅支援新增、刪除及列出 |

課程刪除會同時檢查學生的已選課程及課程的 `enrolled_count`。目前 CLI 未提供完整的登入／角色驗證，且教室修改與條件查詢尚未實作。

#### 2.1.2 系統架構圖 (System Architecture Diagram)
現有實作的資料流如下：

```text
使用者
  ↓
Main.py（CLI：解析輸入、呼叫流程、顯示結果）
  ↓
F1_DataManager.py（F1 驗證與 CRUD；F1Manager 成功後觸發存檔）
  ↓
F6_StorageManager.py（讀取／正規化／原子寫入 JSON）
  ↓
CampusPlanner/UserData/04_data_format.json（種子資料）／db.json（工作資料）
```

功能完成表（狀態依作業規範分為：未開始、開發中、已完成、測試通過）：

| 功能 | 規劃內容 | 狀態 | 說明 |
| :--- | :--- | :--- | :--- |
| F1 | 課程與學生資料管理 | 測試通過 | 課程與學生 CRUD、五種課程查詢、教室新增／刪除／列出；112 項自動化測試通過。學生「系級」的年級尚未加入 |
| F2 | 多層次衝堂與選課檢查 | 未開始 | |
| F3 | 個人課表產生與空閒時段查詢 | 未開始 | |
| F4 | 校園活動與教室配置 | 未開始 | |
| F5 | 多條件課程篩選與可行性檢查 | 未開始 | |
| F6 | 資料儲存與系統測試 | 開發中 | JSON 載入／儲存與容錯載入已完成並有測試；跨模組的 30 項以上自動化測試待 F2 起各模組加入 |
| F7 | 多條件最佳課表搜尋 | 未開始 | |
| F8 | 搜尋演算法比較 | 未開始 | |
| F9 | 校園移動路徑規劃 | 未開始 | |
| F10 | 動態事件與課表重新規劃 | 未開始 | |
| F11 | AI 輔助測試與程式品質改善 | 未開始 | |

---

### 2.2 系統資料 (System Data)

#### 2.2.1 資料格式 (Data Format)

實際種子檔為 [`04_data_format.json`](../../CampusPlanner/UserData/04_data_format.json)，頂層包含 `classrooms`、`courses`、`students`、`activities` 與 `campus_graph`。目前程式所使用的主要欄位如下：

| 資料 | 欄位與格式 |
| :--- | :--- |
| 課程 | `course_id`、`title`、`credits`、`required`（布林值）、`teacher`、`classroom_id`、`capacity`、`enrolled_count`、`time_slots`（`{day, period}` 清單） |
| 學生 | `student_id`、`name`、`department`、`max_credits`、`enrolled_courses`（課程代號清單） |
| 教室 | `classroom_id`、`building_id`、`building_name`、`capacity`、`equipment`（設備清單） |
| 活動 | `activity_id`、`title`、`classroom_id`、`time_slots` 等活動資料 |
| 校園路網 | `campus_graph.nodes` 與 `campus_graph.edges`；邊可記錄步行時間 |

時段的 `day` 為 1–7，`period` 為字串 `"1"`–`"9"`、`"a"`、`"b"` 或 `"c"`；學分須為正整數，容量須至少為 1。規格要求課程代號、學號與教室代號不得重複；課程容量不得超過教室容量；已有學生選修的課程不得刪除。現行 F1 已驗證上述課程／學生／教室資料規則；活動相關驗證仍待 F4 實作。F6 讀檔時另外檢查每筆資料的欄位型別與時段範圍，格式錯誤的單筆資料會被略過並記錄原因，不會讓程式當掉。注意：目前實作欄位採 `title`、`required`、`classroom_id` 與物件型態的 `time_slots`，與部分舊格式文件使用的 `name`、`type`、`classroom` 及字串時段不同，實作以此處所列種子檔格式為準。

---

## 3. 軟體設計 (Software Design)

### 3.1 函式功能介面 (Functionality Interface)

F1 業務規則由 [`F1_DataManager.py`](../../CampusPlanner/Code/F1_DataManager.py) 的純函式處理，資料存取則由 [`F6_StorageManager.py`](../../CampusPlanner/Code/F6_StorageManager.py) 負責；CLI 不直接重複實作驗證規則。

| 項目 | 說明 |
| :--- | :--- |
| **主要函式** | `add_course(db, course)` |
| **輸入** | 標準資料庫字典 `db` 及符合 2.2.1 欄位格式的課程字典 `course` |
| **輸出** | `(ok, code)`；成功為 `(True, "OK")`，失敗為 `(False, 錯誤碼)` |
| **驗證** | 代號唯一、必填欄位、正整數學分、容量、教室存在與容量、時段範圍及時段不得重複 |
| **後置條件** | 成功時加入課程並將 `enrolled_count` 設為 0；失敗時不修改資料庫 |

常用函式另包括 `update_course`、`delete_course`、`query_courses`、`add_student`、`update_student`、`delete_student`、`query_students` 及教室新增／刪除函式。`F1Manager` 將成功的資料異動接至自動存檔。

#### 呼叫範例:
```python
from F6_StorageManager import empty_db
from F1_DataManager import add_classroom, add_course

db = empty_db()
add_classroom(db, {
    "classroom_id": "TR-310",
    "capacity": 60,
    "equipment": ["projector"],
})
ok, code = add_course(db, {
    "course_id": "CS101",
    "title": "計算機程式設計",
    "credits": 3,
    "required": True,
    "teacher": "王老師",
    "classroom_id": "TR-310",
    "capacity": 50,
    "time_slots": [{"day": 1, "period": "3"}],
})
# 預期：ok is True、code == "OK"，且課程的 enrolled_count 為 0
```

---

### 3.2 測試案例設計 (Test case design)
測試分為正常、邊界、錯誤、補充、持久化與 CLI 情境。[`test_f1.py`](../../CampusPlanner/TestDriver/test_f1.py) 的核心案例為 10 個正常、11 個邊界及 10 個錯誤案例，另有驗收、參數化補充及持久化測試；[`test_main.py`](../../CampusPlanner/TestDriver/test_main.py) 驗證 CLI 輸入、輸出與操作流程。

| 測試編號 | 測試類型 | 測試情境 | 預期結果 |
| :--- | :--- | :--- | :--- |
| **N01** | 正常 | 新增合法課程 | 回傳 `(True, OK)`，新增後人數為 0 |
| **B01** | 邊界 | 課程容量剛好為 1 | 新增成功 |
| **B04** | 邊界 | 時段涵蓋星期 1 與星期 7 | 新增成功 |
| **E01** | 錯誤 | 新增已存在的課程代號 | 回傳 `DUPLICATE_ID`，資料不變 |
| **E03** | 錯誤 | 節次超出 1–9、a、b、c | 回傳 `INVALID_PERIOD` |
| **E09** | 錯誤 | 刪除已有學生選修的課程 | 回傳 `COURSE_HAS_STUDENTS`，課程保留 |
| **CLI** | 整合 | CLI 新增已存在的課程代號 | 顯示重複代號錯誤訊息，不當機 |
| **F6** | 持久化 | 存檔內容損毀或含不完整資料 | 壞資料略過或備份損毀檔，載入流程可回報錯誤 |
| **F6** | 持久化 | 欄位都在但格式錯誤（如 `time_slots` 寫成字串 `"1-3"`、星期 9） | 該筆略過並記錄原因，之後查詢課程不當掉 |
| **X** | 補充 | 新增教室時設備清單含非文字項目（如 `[1, 2]`） | 回傳 `INVALID_FIELD`，教室不新增 |

執行方式（由專案根目錄執行；`pyproject.toml` 已設定測試資料夾與模組路徑）：
```text
uv run pytest -q
```
本次驗證結果：**112 passed**。

| 分類 | 數量 | 說明 |
| :--- | ---: | :--- |
| 正常 (normal) | 10 | F1 核心案例 |
| 邊界 (boundary) | 11 | F1 核心案例 |
| 錯誤 (error) | 10 | F1 核心案例 |
| 補充 (extra) | 36 | 參數化與較細的檢查 |
| 持久化 (persistence) | 14 | F6 存檔與容錯載入 |
| 驗收 (acceptance) | 1 | 20 門課程、15 名學生、5 間教室 |
| CLI (cli) | 30 | `test_main.py` 命令列介面 |
| **合計** | **112** | |

---

### 3.3 專案審查 (Iteration Review 1)

#### 本次 Iteration 完成哪些工作? (Completed Work)
1. 建立 F1 課程、學生與教室資料管理核心函式及 CLI 操作流程。
2. 課程與學生已有新增、修改、刪除及查詢；教室已有新增、刪除及列出。
3. 建立 JSON 資料載入、正規化、原子儲存、自動存檔與種子檔／工作檔分離機制。
4. 建立 F1 與 CLI 自動化測試；本次執行兩個測試檔共 **112 項通過**。
5. 將 F1 程式、測試與種子資料搬入 `CampusPlanner` 架構，模組檔名加上 F 編號。

#### 哪些工作尚未完成? (Incomplete Work)
1. 教室修改與條件式查詢尚未提供。
2. F6 規格包含 CSV／JSON；目前只實作 JSON 持久化。
3. F2–F5、F7–F10 尚未實作，F11 亦尚無對應程式功能。

#### 本次 Iteration 遇到哪些問題? (Problems)
1. **格式文件不一致:** 舊格式範例使用 `name`、`type`、`classroom` 與字串時段，現行種子檔及程式則採 `title`、`required`、`classroom_id` 及 `{day, period}` 時段物件；文件與實作需持續維持一致。
2. **範圍尚未完成:** 分工表涵蓋 F1–F11，目前可執行程式以 F1 及部分 F6 為主，其他功能須依分工逐步整合。
3. **原有測試沒抓到的缺陷:** 原本 101 項測試全部通過，但對照作業規範檢查時發現兩個會讓程式當掉的缺陷，原因都是測試只測了「欄位缺漏」，沒有測「欄位都在但格式錯誤」。詳見下方缺陷紀錄。

#### 缺陷紀錄 (Defect Log)

| 編號 | 發現日期 | 模組 | 問題 | 原因 | 處理方式 | Commit | 狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| D01 | 2026-10-20 | F6 | JSON 檔中某門課的 `time_slots` 寫成字串 `"1-3"` 時，載入不會報錯，之後依星期查詢課程就當掉（`TypeError`），違反 F6「不得因單一筆資料格式錯誤造成整個程式異常終止」 | `normalize_db` 只檢查欄位是否存在，不檢查型別 | 新增 `FIELD_CHECKS` 檢查各欄位型別與時段範圍，格式錯誤的單筆資料略過並記錄原因；補 8 項測試 | `5f346c9` | 已修正 |
| D02 | 2026-10-20 | F1 | `add_classroom` 接受 `equipment=[1, 2]`，之後列出教室時當掉（`TypeError`） | 只檢查 `equipment` 是清單，沒檢查每一項是文字 | 改為每一項都必須是文字，否則回傳 `INVALID_FIELD`；補 3 項測試 | `7f5985b` | 已修正 |

兩個缺陷補上的測試都確認過：在修正前的程式上會失敗，在修正後的程式上會通過。D02 從 CLI 輸入不會發生（CLI 切出來的設備一定是文字），只有其他模組直接呼叫函式時才會遇到。

#### 下一次 Iteration 如何改善? (Improvements)
1. 將現行 JSON schema 設為共用資料契約，更新舊格式文件及相關測試。
2. 補齊教室管理與 CSV 存取，再依工作分解表推進 F2–F11。
3. 每次整合前執行自動化測試，並以測試結果更新本節完成狀態。

---

## 4. 專案管理 (Project Management)

### 4.1 工作分解表 (Work Breakdown Structure)

依據 [`工作分解表v1.md`](../../規格書與分工表/工作分解表v1.md)，團隊角色與工作分配如下。本表為分工規劃，不代表各功能均已完成。

| 成員 | 角色 | 主要負責工作 |
| :--- | :--- | :--- |
| **A 索云（組長）** | 專案管理與系統整合 | WBS、Git 版控、F0 系統架構、CLI 整合、最終 Code Review |
| **B 阿福** | 需求分析與資料管理 | F1 需求與 UC01–06、F1 課程／學生 CRUD、F6 JSON／CSV 持久化與容錯載入 |
| **C Steve（副組長）** | 選課邏輯與搜尋演算法 | F2 衝突檢查、F5 多條件篩選、F7 最佳課表搜尋 |
| **D 竹** | 課表矩陣與活動配置 | F3 7×12 課表矩陣與空閒時段、F4 活動及教室設備配置 |
| **E 晴** | 地圖路徑與動態重排 | F9 BFS／Dijkstra 路徑、F10 動態事件最小異動重新規劃 |
| **F minnn** | 測試架構與品質監督 | F8 窮舉／回溯效能比較、F6 30+ 自動化測試架構、F11 AI 品質改善報告、TDD 流程 |

目前可見的程式及測試已涵蓋 F1 與部分 F6；實際完成狀態請以 3.3 節及後續測試結果更新。

---

### 4.2 版本控管 (Version Control)

專案遠端倉庫：[GuoLao-sGroupAssignment](https://github.com/Xoyiun/GuoLao-sGroupAssignment)。依 [`README.md`](../../README.md) 的協作流程，開發分支先 `git fetch origin`，再合併 `origin/main`；若 [`pyproject.toml`](../../pyproject.toml) 或 [`uv.lock`](../../uv.lock) 有更新，使用 `uv sync` 同步環境。[`.venv/`](../../.venv/) 不納入版控。每位成員在自己的分支開發，經 Pull Request 由組長 review 後合併進 `main`。

#### 本週 Git 紀錄（2026-10-12 至 10-20）

以下依各成員分支整理本週的主要 Commit 與 Merge；「F1 分工」依 [`工作分解表v1.md`](../../規格書與分工表/工作分解表v1.md) 判斷。

**A 索云（組長，分支 `Master`）** — F1 分工：工作分解表未分配 F1 開發；負責系統整合與最終 Code Review，本週協助 F1 測試與文件。

| Commit | 日期 | 內容 |
| :--- | :--- | :--- |
| `2759564` | 10/15 | 建立 `CampusPlanner` 各模組檔案，初始化專案結構 |
| `a003a9c` | 10/16 | 修正專案名稱，新增 `Student.json` 格式檔 |
| `da2acf2` | 10/17 | 新增 F1 課程、學生、教室管理的自動化測試 |
| `e2c2574` | 10/17 | 重構 DataManager／StorageManager，調整 pytest 設定 |
| `d17e538` | 10/19 | 更新專案結構與文件 |
| `65e7ae1` | 10/19 | 新增 F1 函式接口報告 |
| Merge | 10/17–10/19 | 合併 PR #21、#24、#25 進 `main` |

**B 阿福（分支 `B`）** — F1 分工：有。工作分解表分配需求規格 (F1)、F1 課程與學生 CRUD、F6 資料持久化。

| Commit | 日期 | 內容 |
| :--- | :--- | :--- |
| `dd57d8a` | 10/14 | 新增 `Code/f1_data_management.py`（F1 程式，183 行）；目前只在分支 `B`，尚未合併進 `main` |
| Merge | 10/13、10/19 | PR #20、#26：把 `main` 同步到分支 `B` |

**C Steve（副組長，分支 `C`）** — F1 分工：工作分解表分配 F2、F5、F7，未分配 F1；本週實際負責開發 F1 程式。

| Commit | 日期 | 內容 |
| :--- | :--- | :--- |
| `03be675`、`38dd680` | 10/15 | 完成 F1 核心程式、測試與 `make_report.py`（測試報告） |
| `c378791`、`30a86d6`、`51ab8a7`、`7c5e66b`、`05b0517`、`45fc50c` | 10/16–10/17 | 檢查 `data_manager.py`、修正 F1 錯誤並補上註解與測試 |
| `9ba5595` | 10/18 | 完成 F1 命令列介面 `main.py` 與 CLI 測試 |
| `0b4722e`、`89638a1`、`0da5479`、`8d13389` | 10/19 | F1 搬進 `CampusPlanner` 並加上 F 編號；更新函式接口報告與資料模型 |
| `5f346c9` | 10/20 | 修正缺陷 D01：F6 讀檔時檢查欄位格式 |
| `7f5985b` | 10/20 | 修正缺陷 D02：`add_classroom` 檢查設備清單 |
| `30e0602`、`00c99a8`、`2a4cdb0` | 10/20 | 更新 SRS、資料模型與個人工作紀錄 |
| PR | 10/17、10/19 | PR #21、#25：分支 `C` 合併進 `main` |

**D 竹（分支 `Zhu22`、`docs/week0-D`）** — 本組員 F1 沒有被分工（工作分解表分配 F3、F4）。本週沒有 Commit。

**E 晴（分支 `Zd`）** — 本組員 F1 沒有被分工（工作分解表分配 F9、F10；擔任成員 B 的監督者）。本週沒有新增內容的 Commit，只有 PR #22、#23、#27 同步分支。

**F minnn（分支 `minnn`）** — 本組員 F1 沒有被分工（工作分解表分配 F6 自動化測試架構、F8、F11）。

| Commit | 日期 | 內容 |
| :--- | :--- | :--- |
| `e297784` | 10/16 | 新增 F6 JSON 存檔測試 `test_f6_persistence.py`（207 行），並修改 `data_manager.py`、`f1_manager.py`；目前只在分支 `minnn`，尚未合併進 `main` |

---

### 4.3 Code Review 紀錄

依作業規範，每個核心模組至少要由一位非原開發者檢視。本週 F1 由組長索云 review：

| PR | 內容 | 原開發者 | Reviewer | 日期 | Review 結果 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| [#21](https://github.com/Xoyiun/GuoLao-sGroupAssignment/pull/21) | F1 核心程式、bug 修正與註解 | C Steve | A 索云 | 10/17 | Approved，合併進 `main` |
| [#25](https://github.com/Xoyiun/GuoLao-sGroupAssignment/pull/25) | F1 搬進 `CampusPlanner`、檔名加上 F 編號 | C Steve | A 索云 | 10/19 | 先提出意見：「就跟你說討論一下轉移，你現在轉移了其他報告的內容你要改嗎？」；之後 Approved 並合併。後續已將 SRS 與資料模型的路徑改為 `CampusPlanner` 版本 |

尚未進行的 Review：成員 B（`dd57d8a`）與成員 F（`e297784`）的程式尚未開 PR，也還沒有人 review。

---

## Glossary

* **CLI (Command Line Interface):** 命令列介面
* **SRS (Software Requirements Specification):** 軟體需求規格書
* **SDD (Software Design Document):** 軟體設計文件
* **CRUD (Create, Read, Update, Delete):** 資料新增、查詢、修改、刪除
* **JSON (JavaScript Object Notation):** 資料交換格式

---

## References

1. **GuoLao-sGroupAssignment GitHub Repository:**  
   [https://github.com/Xoyiun/GuoLao-sGroupAssignment](https://github.com/Xoyiun/GuoLao-sGroupAssignment)
2. **需求規格書與 Use Case:** [`需求規格書.md`](../../規格書與分工表/需求規格書.md)、[`UseCase.md`](../../規格書與分工表/UseCase.md)
3. **工作分解表:** [`工作分解表v1.md`](../../規格書與分工表/工作分解表v1.md)
4. **現行資料格式與程式:** [`04_data_format.json`](../../CampusPlanner/UserData/04_data_format.json)、[`F1_DataManager.py`](../../CampusPlanner/Code/F1_DataManager.py)、[`F6_StorageManager.py`](../../CampusPlanner/Code/F6_StorageManager.py)、[`Main.py`](../../CampusPlanner/Code/Main.py)
5. **自動化測試:** [`test_f1.py`](../../CampusPlanner/TestDriver/test_f1.py)、[`test_main.py`](../../CampusPlanner/TestDriver/test_main.py)

---

## Appendix

### 團隊討論照片

![本週團隊實體討論](團隊討論照片.jpg)