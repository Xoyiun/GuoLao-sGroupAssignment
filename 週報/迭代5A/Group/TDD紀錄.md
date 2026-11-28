# 迭代 5A TDD 紀錄：F8 搜尋演算法比較

**流程：** Requirement → Test → Red → Green → Refactor → Regression Test
**需求來源：** [`F8演算法說明.md`](F8演算法說明.md)（commit `248cfdd`，在寫任何測試之前提交）
**測試輸出原檔：** [`TDD紀錄/`](TDD紀錄/) 資料夾

---

## 總覽

| 輪次 | 需求 | 測試 | Red | Green | Refactor ＋ 回歸 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 準備 | F7、F8 共用同一套可行性條件 | 既有 F7 測試 | — | — | `3b6dda3`：241 passed |
| 1 | 窮舉法 | S01、S02 | `9889e10`：2 failed | `b2e1bc8`：2 passed | `e11e8af`：242 passed |
| 2 | 回溯法與剪枝 | S03、S04 | `3dc70c9`：2 failed | `9710d80`：4 passed | `c40f20a`：244 passed |
| 3 | 時間上限、比較報告、與 F7 一致、錯誤輸入 | S05–S07、S09 | `63cc910`：5 failed | `59b300d`：12 passed | `2f9d701`：252 passed |
| 4 | 8、12、16 門實驗資料與實驗函式 | S08、S10 | `ee0ea6d`：4 failed | `1b809e9`：第一次 1 failed，修正測試假設後 16 passed | `5520cf7`：256 passed |

---

## 準備性 Refactor：共用可行性條件

迭代 4 檢視架構時發現：F8 另寫了一份可行性判斷，而且沒有檢查「與已選課程衝堂」，跟 F7 不一致。開始 F8 之前，先把 F7 的條件抽成 `BuildSearchProblem`（整理輸入）與 `IsFeasibleSelection`（判斷可行），F7 改用它們。行為不變，由既有的 F7 測試把關：`241 passed`（[`0_準備Refactor_回歸.txt`](TDD紀錄/0_準備Refactor_回歸.txt)）。

## 第 1 輪：窮舉法

**Test（S01、S02，[`test_f8.py`](../../../TestDriver/test_f8.py)）：** 期望值先手算。4 門候選（A、B 互相衝堂；A、B、E 各 3 學分、C 2 學分），學分 3–6 → 8 個可行解、16 個節點。另一題確認與已選課衝堂、禁止時段、額滿的課都被排除。

**Red（[`1_Red.txt`](TDD紀錄/1_Red.txt)）：** `AttributeError: module 'SearchCompare' has no attribute 'BruteForceSearch'`，`2 failed`。舊的 F8 測試是依舊介面寫的，這輪依新規格重寫。

**Green（[`1_Green.txt`](TDD紀錄/1_Green.txt)）：** 用位元遮罩逐一檢查子集合，呼叫 `IsFeasibleSelection`。`2 passed`。

**Refactor（[`1_Refactor_回歸.txt`](TDD紀錄/1_Refactor_回歸.txt)）：** 函式內的匯入移到檔案開頭；解的表示法抽成 `SolutionKey`。`242 passed`。

## 第 2 輪：回溯法

**Test（S03、S04）：** 節點數先手算再寫進測試：

* S03：同一個 4 門題目，回溯法要走 22 個節點（樹狀展開見演算法說明），比窮舉法的 16 個多。
* S04：8 門各 3 學分、彼此不衝堂、學分 3–6，回溯法只走「已選 ≤ 2 門」的狀態：Σ(i=0..8)[C(i,0)+C(i,1)+C(i,2)] = 129 個節點；窮舉法 256 個；可行解 C(8,1)+C(8,2) = 36 個。

**Red（[`2_Red.txt`](TDD紀錄/2_Red.txt)）：** `2 failed, 2 passed`。

**Green（[`2_Green.txt`](TDD紀錄/2_Green.txt)）：** 依序決定每門「不選／選」，加入後違反學分上限、禁止時段、額滿或衝堂就不往下走；目前學分加上剩餘學分仍達不到最低學分就停止。`4 passed`，節點數與手算的 22、129 完全相同。

**Refactor（[`2_Refactor_回歸.txt`](TDD紀錄/2_Refactor_回歸.txt)）：** 巢狀函式 `CanAdd` 提到模組層並改名 `CanAddCourse`；剩餘學分抽成 `SuffixCredits`；必修課的初始檢查改用同一個函式。`244 passed`。

## 第 3 輪：時間上限、比較報告、與 F7 一致、錯誤輸入

**Test（S05–S07、S09）：** 時間上限 0 秒時兩法都要回報未完成、一致性為 `None`；比較報告要有兩法的節點數、時間、解數與一致性；F7 找到的方案要與 F8 的可行解相同；學生或必修課不存在、學分為負時回報 `INVALID_FIELD`。

**Red（[`3_Red.txt`](TDD紀錄/3_Red.txt)）：** `5 failed, 7 passed`。S07（F7 與 F8 一致）寫好就通過，因為準備性 Refactor 已讓兩者共用條件；這也證明準備性 Refactor 達到了目的。

**Green（[`3_Green.txt`](TDD紀錄/3_Green.txt)）：** 兩法都加上 `timeLimit`，每走一個節點檢查一次；`CompareAlgorithms` 整個換成新規格。`12 passed`。

**Refactor（[`3_Refactor_回歸.txt`](TDD紀錄/3_Refactor_回歸.txt)）：** 移除舊版留下的 `combinations`、`copy`、`INVALID_FIELD` 匯入；逾時判斷抽成 `TimeIsUp`；更新模組說明。`252 passed`。

## 第 4 輪：實驗資料與實驗函式

**Test（S08、S10）：** 8、12、16 門的資料各自存在；兩法都完成、可行解一致；原本還要求「回溯法節點較少」。`RunExperiment` 重複執行並回傳時間中位數。

**Red（[`4_Red.txt`](TDD紀錄/4_Red.txt)）：** `4 failed, 12 passed`（資料檔與 `RunExperiment` 都還不存在）。

**Green 第一次（[`4_Green_第一次執行_假設錯誤.txt`](TDD紀錄/4_Green_第一次執行_假設錯誤.txt)）：**

```text
FAILED TestDriver/test_f8.py::test_ExperimentDatasetsAgree[8] - assert 279 < 256
1 failed, 15 passed
```

程式沒有錯，是**測試的假設錯了**：8 門時回溯法走了 279 個節點，比窮舉法的 256 個多（原因見演算法說明 4.3）。12、16 門時回溯法確實較少。因此修正需求為「12 門以上時回溯法節點較少」，8 門的結果如實記錄在效能實驗。

**Green 第二次（[`4_Green.txt`](TDD紀錄/4_Green.txt)）：** `16 passed`。

**Refactor（[`4_Refactor_回歸.txt`](TDD紀錄/4_Refactor_回歸.txt)）：** `RunExperiment` 改為「每次都一致才算一致，有一次無法判定就是無法判定」，並補上說明。`256 passed`。

---

## 反思

1. 先手算節點數讓我們發現：回溯法的節點數不一定比窮舉法少，兩者的節點定義本來就不同。如果先寫程式再補測試，很可能只會看到「回溯法比較快」，不會注意到小題目的反例。
2. 第 4 輪 Green 失敗時，我們沒有為了讓測試通過而改程式，而是先判斷「程式錯還是假設錯」，再修正需求並留下紀錄。
3. 準備性 Refactor 讓 F7、F8 共用同一套條件，第 3 輪的一致性測試因此不需要任何新程式就通過。
