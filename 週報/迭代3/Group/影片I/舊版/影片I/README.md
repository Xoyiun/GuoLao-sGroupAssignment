# 影片 I 附件：F2「加選時一次找出所有衝突」

所有內容都能追溯到 GitHub 上的 commit。

## 文件

| 檔案 | 內容 |
| --- | --- |
| `逐字稿.md` | 逐段講稿（講者：索云、Steve、晴） |
| `投影片.html` | 15 頁投影片，瀏覽器開啟，← → 換頁 |
| `demo_old_vs_new.ps1` | I-6 示範：舊程式跑新 F2 測試，再跑目前的程式 |
| `投影片.pptx`、`投影片.pdf` | 同一份投影片的 PowerPoint（備忘稿附逐字稿）與 PDF 版 |
| `AI對話節錄_20261028.md` | I-4 兩輪對話的原始紀錄（投影片 6、7 依此重現） |

## 程式版本（`程式/`）

| 檔案 | 來源 | 用在 |
| --- | --- | --- |
| `1_修改前_ConflictChecker_15feb67.py` | commit `15feb67`（10/21 初版） | I-3 原始解法 |
| `2_F2修正_ConflictChecker_5de6cf4.py` | commit `5de6cf4`（F2 驗收修正） | I-4、I-6 |
| `3_目前_ConflictChecker.py` | 分支 `C` 目前版本（加上加選、退選） | I-6 |
| `4_test_f2_5de6cf4_8項.py` | commit `5de6cf4` 的 `test_f2.py` | I-6 舊程式跑新測試 |
| `5_test_f2_目前_14項.py` | 目前的 `TestDriver/test_f2.py`（新增 2 項排序測試） | I-5、I-6 |
| `6_CS102_修改前.json`、`7_CS102_修改後.json` | commit `c2b43a9` 前後 | I-5 資料撞期 |
| `8_MA101.json` | commit `c2b43a9` 前 | I-5 資料撞期 |
| `9_ConflictChecker_修改前後.diff` | `15feb67` → 目前 | I-6 |

## 實驗數據（`實驗數據/`）

| 檔案 | 內容 | 結果 |
| --- | --- | --- |
| `1_舊程式跑新測試_vs_目前.txt` | `demo_old_vs_new.ps1` 的完整輸出 | 舊：3 failed, 5 passed；新：14 passed |
| `2_全部測試.txt` | `uv run python -m pytest -q` | 159 passed |
| `3_CLI加選示範.txt` | 選單 15：S10902 加選 GE101、重複加選 CS102 | 一次列出 2 個衝突；重複加選回報「已經選過這門課」 |

## Prompt 與 AI 協作紀錄

- `週報/迭代2/個人繳交/碩志_個人工作紀錄.md` 第七節
- 團隊週報缺陷 D04–D07：`週報/迭代2/迭代2團隊週報.md`
