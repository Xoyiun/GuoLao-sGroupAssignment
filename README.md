# 郭老師的分組作業 (GuoLao's Group Assignment)

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

### 5. 執行自動化測試

在專案根目錄執行以下指令。第一次執行或依賴有更新時，先同步環境：

```bash
uv sync
```

接著可依需求執行：

```bash
# 執行全部測試
uv run pytest

# 只執行 F6 的 JSON 存檔與容錯載入測試
uv run pytest Code/test_f6_persistence.py -v

# 依測試標記執行 F1 分類或 F6 持久化案例
uv run pytest -m normal -v
uv run pytest -m boundary -v
uv run pytest -m error -v
uv run pytest -m extra -v
uv run pytest -m persistence -v
uv run pytest -m acceptance -v

# 查詢有哪些測試與標記，不執行測試
uv run pytest --collect-only -q
```

F6 測試使用 pytest 的 `tmp_path` 在暫存目錄建立 JSON 檔，涵蓋正常存檔、種子檔保護、缺漏或型別錯誤資料、損毀檔案備份、原子寫入失敗，以及自動存檔失敗時的回復。這些測試檔與專案種子資料隔離；pytest 會管理暫存目錄並清理較舊的測試目錄。

---
⚠️ **注意**：`.venv/` 資料夾已加入 `.gitignore`，**請勿將 `.venv` 推送到 Git**。
