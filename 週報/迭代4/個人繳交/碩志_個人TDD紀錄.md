# 碩志 迭代四個人工作紀錄與 TDD 紀錄

**專案名稱：** GuoLao-sGroupAssignment
**紀錄期間：** 2026 年 11 月 25 日至 11 月 28 日
**工作者：** 碩志（GitHub：weif3383-cloud，分支 `C`）
**團隊角色：** C Steve（副組長）；負責 F2、F5、F7

---

## 一、本週負責工作與完成內容

| 工作 | 完成內容 |
| :--- | :--- |
| 重新檢視 F7 初版 | 檢視組長 11/23 的 `ScheduleOptimizer.py`：分數只等於總學分、沒有偏好與權重、必修課已選時找不到方案（D16） |
| F7 需求規格 | 定義五項偏好指標、評分公式、預設權重與理由、權重如何影響推薦結果、10 項驗收測試（[F7需求規格.md](../Group/F7需求規格.md)） |
| TDD 開發 | 五輪 Red → Green → Refactor，每階段各一個 commit 並保留測試輸出（[TDD紀錄.md](../Group/TDD紀錄.md)） |
| 系統 v1.1 | CLI 新增選單 18「最佳課表搜尋」 |
| 文件 | 系統需求設計規格書 V4.0、迭代四團隊週報 |

### 遭遇問題與解決方式

| 問題 | 解決方式 |
| :--- | :--- |
| 寫 CLI 測試時，手算發現 CS201、CS203 兩案預設同分（−3.5），排序結果取決於搜尋順序 | 在需求中明訂「同分依課程代號排序」，並寫進測試 |
| 規範要求「說明不同權重如何影響推薦結果」，但只寫文字很難驗證 | 設計 EARLY／LATE 兩個方案，用測試證明「早八權重 0」時排序會改變 |
| F7 的空堂算法跟 F3 各寫一份 | Refactor 時改呼叫 F3 的 `count_gap_periods`，由回歸測試確認 F3 沒受影響 |

---

## 二、個人 TDD 紀錄：第 3 輪「搜尋依偏好分數排序」

以下是一個完整的 Requirement → Test → Red → Green → Refactor → Regression Test 案例。其餘四輪見團隊的 [TDD紀錄.md](../Group/TDD紀錄.md)。

### Requirement

F7 需求規格第三、六節：`SearchOptimalSchedules` 要接受 `preferred_courses`（偏好課程）與 `weights`（權重），每個方案附上 `metrics`（偏好指標），並依偏好分數排序；權重或偏好課程格式錯誤時回傳 `INVALID_FIELD`。

### Test（commit `cee0af6`）

在 `TestDriver/test_f7.py` 新增 T06–T08。情境：EARLY（星期一第 1–2 節）、LATE（星期一第 5–6 節）各 3 學分，學分上下限都是 3，所以只能選一門。

```python
def test_SearchRanksByPreferenceScore():
    """T06：預設避開早八 → LATE 第一；早八權重 0 → 同分依代號 EARLY 第一；EARLY 設為偏好課程 → EARLY 第一。"""
    ok, code, plans = optimizer.SearchOptimalSchedules(PreferenceDatabase(), "S1", OneOfTwo())
    assert (ok, code) == (True, OK)
    assert [plan["courses"] for plan in plans] == [["LATE"], ["EARLY"]]
    assert [plan["score"] for plan in plans] == [0.5, -1.0]
    ...
```

期望分數先手算：LATE = 3 − 2×1（到校 1 天）− 0.5×1（半天區段 1）= 0.5；EARLY 多一個早八，再扣 1.5 = −1.0。

### Red

```text
FAILED TestDriver/test_f7.py::test_SearchRanksByPreferenceScore - AssertionEr...
FAILED TestDriver/test_f7.py::test_SearchCountsEnrolledCoursesInMetrics - Key...
FAILED TestDriver/test_f7.py::test_SearchRejectsInvalidPreferences[extra0] - ...
FAILED TestDriver/test_f7.py::test_SearchRejectsInvalidPreferences[extra1] - ...
FAILED TestDriver/test_f7.py::test_SearchRejectsInvalidPreferences[extra2] - ...
5 failed, 2 passed
```

失敗原因符合預期：搜尋仍以總學分當分數（兩案都是 3.0）、沒有 `metrics`、也不檢查權重。原本的 2 個測試仍通過，表示新測試沒有破壞既有行為。

### Green（commit `ead035a`）

只做讓測試通過的最少修改：

1. 讀取 `preferred_courses`、`weights`，格式錯誤就回傳 `INVALID_FIELD`。
2. 找到可行組合後，呼叫第 1、2 輪完成的 `CalculateScheduleMetrics` 與 `ScoreSchedule`，把分數與指標放進方案。

結果：`7 passed`。

### Refactor（commit `a409913`）

| Green 版本的問題 | 整理後 |
| :--- | :--- |
| 已選課程清單在每個組合的迴圈裡都重查一次 | 移到迴圈外只查一次 |
| 衝堂判斷用兩層 `break`，不容易看懂 | 抽成 `HasTimeConflict(selected, enrolledCourses)` |
| `from ConflictChecker import CheckEnrollmentConflicts` 沒有使用 | 移除 |
| 函式說明沒寫新欄位 | 補上 `blocked_slots`、`preferred_courses`、`weights` 與 `metrics` |

### Regression Test

```text
uv run python TestDriver.py
235 passed
```

整理前後的行為完全相同，全系統測試都通過。

---

## 三、程式理解說明：`ScoreSchedule(metrics, weights=None)`

* **Input：** 偏好指標 `metrics`（學分、到校天數、空堂、早八、半天區段、偏好比例），以及要調整的權重 `weights`（可省略）。
* **Process：** 先用預設權重補齊沒填的項目，再依 `SCORE_TERMS` 對照表逐項計算「方向 × 權重 × 指標」並加總。學分與偏好比例是加分，其他四項是扣分。
* **Output：** 分數，取到小數第 2 位。
* **Boundary / Error Case：**
  * 權重只填一部分時，其他項目用預設值。
  * 權重的合法性由 `ValidateWeights` 先檢查：負數、文字、`True`／`False`、不存在的名稱都會被拒絕。
  * 浮點數加總可能出現 0.30000000000000004 這類誤差，所以四捨五入到小數第 2 位，避免同分的方案被判成不同分。

---

## 四、Code Review 紀錄

| 對象 | 原開發者 | 發現的問題 | 處理 |
| :--- | :--- | :--- | :--- |
| `ScheduleOptimizer.py` 初版（`cb63dfc`） | A 索云 | 1. 分數 = 總學分，規範要求的五項偏好與權重都沒有<br>2. 必修課學生已選時，被判定跟自己衝堂而找不到方案（D16）<br>3. 已選課程在每個組合都重查一次<br>4. 有未使用的匯入 | 以 TDD 第 1～5 輪修正 |

本週我的 F7 修改尚待 F minnn（我的監督者）在 Pull Request 檢視。

---

## 五、Git 紀錄

| Commit | 內容 |
| :--- | :--- |
| `d56679c` | F7 需求規格（先於任何測試） |
| `83dcbac`、`ad9dce5`、`b258792` | 第 1 輪：偏好指標 |
| `62ee3fa`、`4596a77`、`3604548` | 第 2 輪：評分公式與權重 |
| `cee0af6`、`ead035a`、`a409913` | 第 3 輪：搜尋依偏好分數排序 |
| `69afd81`、`0515d30`、`5f5fc90` | 第 4 輪：CLI 選單 18 |
| `3bc4dec`、`eef8cec`、`5deceff` | 第 5 輪：修正 D16 |

---

## 六、AI 協作紀錄

| 問題 | Prompt | AI 建議摘要 | 採納／拒絕與理由 | 驗證方式 |
| :--- | :--- | :--- | :--- | :--- |
| 下週要交什麼 | 你看一下下一周我們要繳甚麼 幫我完成 全部交給你處理 不用問我意見 | 依規範判斷為迭代 4；指出 F7 沒有偏好評分；提議先交需求規格，再每輪分三個 commit 走 TDD | 採納：符合規範的 TDD 流程與「不得事後補寫測試」 | Git 紀錄中每輪的測試 commit 都早於實作 |
| F7 初版是否有缺陷 | （同一對話）實際呼叫 F7 確認行為 | 必修課已選時回傳 `NO_FEASIBLE_SCHEDULE` | 採納，列為 D16 | 先寫重現測試（1 failed），修正後通過 |
| 節次排序 | （11/19 影片大綱對話） | 說節次照字串排序會出錯 | **拒絕**：數字字元的編碼小於小寫字母，字串排序本來就正確 | 以字元編碼與實際排序結果驗證 |

---

## 七、心得

TDD 最大的差別是「先想清楚答案」。寫第 4 輪 CLI 測試時，要先手算每個方案的分數，才發現兩個方案同分，排序結果其實沒有定義；如果先寫程式，這個問題只會在某次執行結果「剛好不一樣」時才被發現。另外，每輪的 Refactor 都有完整回歸測試保護，所以我敢把 F7 改成呼叫 F3 的函式，不用擔心改壞別人的功能。
