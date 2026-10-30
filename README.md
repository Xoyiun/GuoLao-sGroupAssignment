# 郭佬的小組作業 (GuoLao's Group Assignment)

本專案採用現代化 Python 套件管理工具 [uv](https://github.com/astral-sh/uv) 進行專案環境管理與套件依賴控制。

---

## 🚀 快速開始 (Quick Start)

### 1. 初次安裝 uv（全域僅需執行一次）

若你的電腦尚未安裝 `uv`，請先選擇對應作業系統的指令安裝：

- **Windows (PowerShell)**:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **macOS / Linux**:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

---

### 2. 初始化專案環境 (Clone 後第一次執行)

複製專案後，進入專案根目錄並執行一鍵同步指令：

```bash
git clone https://github.com/Xoyiun/GuoLao-sGroupAssignment.git

# 自動建立 .venv、下載指定 Python 版本並同步安裝所有套件
uv sync
```

---

### 3. 日常開發與遠端同步 (Git Pull / Merge Workflow)

當遠端倉庫有更新，或組員新增/修改了套件依賴（`pyproject.toml` / `uv.lock` 變更）時，請執行以下步驟：

#### 步驟 A：拉取與合併遠端最新程式碼
```bash

# 若在自己的功能分支，合併主分支更新：
git fetch origin
git merge origin/main
```

#### 步驟 B：同步本機虛擬環境
合併程式碼後，執行 `uv sync`，`uv` 會自動依據新的 `uv.lock` 修正 `.venv` 內的套件（補上新套件、自動移除已廢棄套件）：
```bash
uv sync
```

---

### 4. 開發常用指令指南

在 `uv` 架構下，不需要手動切換或啟用 `.venv`，所有操作皆可直接透過 `uv` 指令執行：

* **執行主程式**：
  ```bash
  #目前還沒有想好實現，暫時沒用
  uv run main
  ```

* **新增第三方套件**：
  ```bash
  uv add 套件名稱
  # 範例：uv add requests pandas
  ```

* **新增開發用套件 (Dev Dependencies)**：
  ```bash
  uv add --dev pytest ruff
  ```

* **移除套件**：
  ```bash
  uv remove 套件名稱
  ```

---

### 5. CampusPlanner 資料檔

動態資料依 ID 分檔保存：課程位於 `CampusPlanner/UserData/Courses/{course_id}.json`，學生位於 `CampusPlanner/UserData/Students/{student_id}.json`。測試驅動與測試輸入已遷移至根目錄的 `TestDriver.py`、`TestDriver/` 與 `TestDriver/TestInput`。教室與校園圖仍分別保存在 `Classroom.json` 和 `CampusGraph.json`。

活動資料會依 `CampusPlanner/Reference/Formate/Course.json` 的 `event` 格式轉為課程，使用活動 ID 作為 `course_id`、學分為 0、教師預設為 `NPC`。活動時段的日期使用 Unix 時間戳；目前測試資料的日期為 2026-09-27、2026-10-06、2026-10-18，時間皆為台北時區 00:00。

只支援 ID 分檔格式：舊的整份 JSON 種子檔（`04_data_format.json`）與 `db.json` 已不再讀取。程式直接讀寫 `CampusPlanner/UserData`；某個資料檔損毀時會略過該檔並備份成 `{檔名}.corrupt.bak`，其他資料照常載入。

---
⚠️ **注意**：`.venv/` 資料夾已加入 `.gitignore`，**請勿將 `.venv` 推送到 Git**。

#### CI 快速匯入空白 UserData

`Main.py` 提供隱藏的 `import` 指令，不會出現在互動選單中。來源資料夾必須包含
`Classroom.json`、`CampusGraph.json`、`Courses/`、`Students/`：

```powershell
python CampusPlanner/Code/Main.py import <來源資料夾> [目標UserData資料夾]
```

未指定目標資料夾時，預設匯入至 `CampusPlanner/UserData`。預設會先驗證所有
JSON 檔案，再覆寫整個目標資料夾。若只要覆寫單一資料區塊，可使用：

```powershell
python CampusPlanner/Code/Main.py import --only classroom <來源資料夾> [目標UserData資料夾]
```

`--only` 支援 `classroom`、`campusgraph`、`courses`、`students`，也可用逗號指定多個區塊。

#### 執行測試

測試驅動位於專案根目錄，可直接執行完整測試或傳入 pytest 參數：

```powershell
python TestDriver.py
python TestDriver.py -m normal -v
```