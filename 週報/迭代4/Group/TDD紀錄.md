# 迭代 4 TDD 紀錄：F7 多條件最佳課表搜尋

**流程：** Requirement → Test → Red → Green → Refactor → Regression Test
**負責人：** C Steve
**需求來源：** [`F7需求規格.md`](F7需求規格.md)（commit `d56679c`，在寫任何測試之前提交）
**測試輸出原檔：** [`TDD紀錄/`](TDD紀錄/) 資料夾，每個階段一個檔案

每一輪都依序提交三個 commit：先提交**會失敗的測試**（Red），再提交**剛好讓測試通過的最少量程式**（Green），最後提交**不改變行為的整理**，並附上完整回歸測試結果（Refactor）。commit 的先後順序可在 Git 紀錄中查證，測試一定比實作先提交。

---

## 總覽

| 輪次 | 需求 | 測試 | Red | Green | Refactor ＋ 回歸 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 偏好指標：到校天數、空堂、早八、半天區段、偏好比例 | T01、T02 | `83dcbac`：2 failed | `ad9dce5`：2 passed | `b258792`：222 passed |
| 2 | 評分公式、預設權重、權重驗證 | T03–T05 | `62ee3fa`：8 failed | `4596a77`：10 passed | `3604548`：230 passed |
| 3 | 搜尋結果依偏好分數排序並附上指標 | T06–T08 | `cee0af6`：5 failed | `ead035a`：7 passed | `a409913`：235 passed |
| 4 | CLI 選單 18 最佳課表搜尋（系統 v1.1） | T09 | `69afd81`：5 failed | `0515d30`：5 passed | `5f5fc90`：240 passed |
| 5 | 缺陷 D16：必修課已選時找不到方案 | T10 | `3bc4dec`：1 failed | `eef8cec`：8 passed | `5deceff`：241 passed |

---

## 第 1 輪：偏好指標

**Requirement：** 需求規格第四節。每個方案以「學生已選課程＋方案中的課程」計算五項偏好指標；學分只算方案中新排入的課。

**Test（T01、T02，[`test_f7_score.py`](../../../TestDriver/test_f7_score.py)）：**

```python
def test_MetricsCountDaysGapsEarlyAndBlocks():
    """星期一第 1、2、5 節（早八、空堂 2 節、上午＋下午）＋星期三晚上第 a 節（已選課程）。"""
    plan = [Course("A", [(1, "1"), (1, "2")], credits=3), Course("B", [(1, "5")], credits=2)]
    enrolled = [Course("E", [(3, "a")], credits=1)]
    metrics = optimizer.CalculateScheduleMetrics(plan, enrolled)
    assert metrics["credits"] == 5            # 只算方案中新排入的課
    assert metrics["campus_days"] == 2        # 星期一、星期三
    assert metrics["gap_periods"] == 2        # 星期一第 3、4 節
    assert metrics["early_periods"] == 1      # 星期一第 1 節
    assert metrics["half_day_blocks"] == 3    # 星期一上午、星期一下午、星期三晚上
```

**Red（[`1_Red.txt`](TDD紀錄/1_Red.txt)）：**

```text
E   AttributeError: module 'ScheduleOptimizer' has no attribute 'CalculateScheduleMetrics'
FAILED TestDriver/test_f7_score.py::test_MetricsCountDaysGapsEarlyAndBlocks
FAILED TestDriver/test_f7_score.py::test_MetricsPreferredRatio - AttributeErr...
2 failed in 0.03s
```

**Green（[`1_Green.txt`](TDD紀錄/1_Green.txt)）：** 寫一個 `CalculateScheduleMetrics`，在函式裡直接列出 12 個節次、用三組集合判斷上午／下午／晚上，空堂用「第一節到最後一節的節數 − 有課的節數」計算。結果：`2 passed`。

**Refactor（[`1_Refactor_回歸.txt`](TDD紀錄/1_Refactor_回歸.txt)）：**

| 問題 | 整理方式 |
| :--- | :--- |
| 函式內自己列了一份節次清單，跟 `Constants.VALID_PERIODS` 重複 | 改用 `VALID_PERIODS` |
| 空堂算法跟 F3 的 `count_gap_periods` 各寫一份，以後可能算出不同結果 | 改為呼叫 F3 的 `count_gap_periods` |
| 早八節次、半天區段寫死在迴圈裡 | 抽成模組常數 `EARLY_PERIOD`、`HALF_DAY_PERIODS`，並抽出 `OccupiedPeriodsByWeekday` |

回歸測試：`222 passed`。

---

## 第 2 輪：評分公式與權重

**Requirement：** 需求規格第五節。分數 = 1.0×學分 − 2.0×到校天數 − 1.0×空堂 − 1.5×早八 − 0.5×半天區段 + 5.0×偏好比例；權重須為 ≥ 0 的數字，名稱須存在。

**Test（T03–T05）：** 預設權重算出 3.5；EARLY／LATE 兩案在預設權重下為 −1.0／0.5，早八權重設為 0 後都變成 0.5；負數、文字、bool、不存在的名稱、不是字典都要被拒絕。

**Red（[`2_Red.txt`](TDD紀錄/2_Red.txt)）：** `8 failed, 2 passed`（新的 8 項因為 `ScoreSchedule`、`ValidateWeights` 不存在而失敗，第 1 輪的 2 項仍通過）。

**Green（[`2_Green.txt`](TDD紀錄/2_Green.txt)）：** `ScoreSchedule` 把六項加減一一寫出；`ValidateWeights` 用迴圈逐一檢查。結果：`10 passed`。

**Refactor（[`2_Refactor_回歸.txt`](TDD紀錄/2_Refactor_回歸.txt)）：** 公式中的加減號散在六行裡，新增偏好時容易漏改。改成 `SCORE_TERMS` 對照表（指標 → 方向、預設權重），分數用同一個迴圈計算，`DEFAULT_WEIGHTS` 由對照表產生；權重檢查抽出 `IsWeightValue`。回歸測試：`230 passed`。

---

## 第 3 輪：搜尋依偏好分數排序

**Requirement：** 需求規格第三、六節。`SearchOptimalSchedules` 接受 `preferred_courses`、`weights`，每個方案附上 `metrics`，依分數排序；格式錯誤回傳 `INVALID_FIELD`。

**Test（T06–T08，[`test_f7.py`](../../../TestDriver/test_f7.py)）：** EARLY、LATE 只能選一門時，預設 LATE 第一；早八權重 0 時同分依代號 EARLY 第一；EARLY 設為偏好課程時 EARLY 第一；已選星期三的課時到校天數算 2 天；權重或偏好課程格式錯誤回報 `INVALID_FIELD`。

**Red（[`3_Red.txt`](TDD紀錄/3_Red.txt)）：** `5 failed, 2 passed`。失敗原因是搜尋仍以總學分當分數、沒有 `metrics`，也不檢查權重：

```text
E   AssertionError: assert (True, 'OK', ...score': 3.0}]) == (False, 'INVALID_FIELD', [])
```

**Green（[`3_Green.txt`](TDD紀錄/3_Green.txt)）：** 讀取兩個新欄位並驗證；在找到可行組合後呼叫 `CalculateScheduleMetrics`、`ScoreSchedule`。結果：`7 passed`。

**Refactor（[`3_Refactor_回歸.txt`](TDD紀錄/3_Refactor_回歸.txt)）：** 已選課程原本在每個組合都重查一次，移到迴圈外只查一次；兩層 `break` 的衝堂判斷抽成 `HasTimeConflict`；移除未使用的匯入；說明文件補上新欄位與 `metrics`。回歸測試：`235 passed`。

---

## 第 4 輪：CLI 選單 18（系統 v1.1）

**Requirement：** 需求規格第二節「CLI」：使用者輸入必修、候選、學分、禁止時段、偏好課程與權重，列出分數最高的前三個方案與各項指標。

**Test（T09，[`test_main.py`](../../../TestDriver/test_main.py) 的 5 項 `test_OptimizeSchedule…`）：** 期望值先手算再寫進測試。S10901 已選 CS101、MA102（星期一 2–4、6–8 節），候選 ENG101、CS203、CS201，學分 3–3 → 只有 CS201、CS203 兩案，都是到校 2 天、空堂 1 節、半天區段 3，預設 −3.5 分；把 CS203 設為偏好課程後 CS203 變成 1.5 分排第一。

**Red（[`4_Red.txt`](TDD紀錄/4_Red.txt)）：** `5 failed`（選單沒有 18）。

**Green（[`4_Green.txt`](TDD紀錄/4_Green.txt)）：** 新增 `OptimizeScheduleFlow` 與選單項目。結果：`5 passed`。

**Refactor（[`4_Refactor_回歸.txt`](TDD紀錄/4_Refactor_回歸.txt)）：** 權重文字解析抽成 `ParseWeights`，與其他 `Parse*` 放在輸入解析區；方案指標輸出抽成 `FormatPlanMetrics`。回歸測試：`240 passed`。

實際執行結果見 [`系統v1.1_選單18示範.txt`](系統v1.1_選單18示範.txt)。

---

## 第 5 輪：修正缺陷 D16

**發現經過：** 檢視組長 11/23 版 F7（`cb63dfc`）時，用測試資料實際呼叫：

```text
S10901 已選 CS101，必修 CS101、候選 CS201
→ (False, 'NO_FEASIBLE_SCHEDULE', [])
```

必修課已經選了，卻被拿去跟「已選的自己」比對而判定衝堂，任何方案都不可行。

**Test（T10）：** `test_SearchTreatsEnrolledRequiredCourseAsSatisfied`：已選課程 E 被列為必修，候選 LATE，學分 3–3 → 應得到方案 `["LATE"]`。

**Red（[`5_Red.txt`](TDD紀錄/5_Red.txt)）：** `1 failed, 7 passed`。

**Green（[`5_Green.txt`](TDD紀錄/5_Green.txt)）：** 必修與候選中已選的課不再排入方案。結果：`8 passed`。

**Refactor（[`5_Refactor_回歸.txt`](TDD紀錄/5_Refactor_回歸.txt)）：** 候選課程「去重」與「排除已選」合併成一步；額滿檢查原本特別排除已選課程，現在已選課程不會出現在方案裡，這個條件變成多餘，予以移除。回歸測試：`241 passed`。

---

## 反思

1. 第 4 輪的期望值先手算，寫測試時就發現兩案預設同分，因此特別加了「同分依課程代號排序」的需求，避免結果看起來隨機。
2. 第 1 輪的 Refactor 讓 F7 與 F3 共用空堂算法；如果沒有回歸測試，很難放心把 F7 改成呼叫別人的函式。
3. 第 5 輪是先寫重現缺陷的測試再修，修好後這個測試會留在回歸測試裡，防止同一個問題再出現。
