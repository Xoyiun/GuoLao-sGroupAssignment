# 影片 I-6 示範：舊程式跑新 F2 測試 vs. 現在的程式
# 在專案根目錄執行：powershell -ExecutionPolicy Bypass -File 影片I\demo_old_vs_new.ps1
#
# 做法：
#   1. 開一個暫存 worktree，切到 5de6cf4（F2 驗收修正，test_f2.py 第一次出現，共 8 項）
#   2. 只把 ConflictChecker.py 換回組長的初版 15feb67
#   3. 用「新測試」跑「舊程式」→ 預期 3 failed, 5 passed
#   4. 回到目前的分支跑現在的 test_f2.py → 預期 14 passed
#   5. 刪除暫存 worktree（不會動到你的工作目錄）

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$repo = (git rev-parse --show-toplevel).Trim()
$old = Join-Path $env:TEMP "f2-old-demo"

if (Test-Path $old) { git -C $repo worktree remove --force $old | Out-Null }
git -C $repo worktree add --detach $old 5de6cf4 | Out-Null
git -C $old checkout 15feb67 -- CampusPlanner/Code/ConflictChecker.py

Write-Host ""
Write-Host "===== 修改前：15feb67 的 ConflictChecker.py + 5de6cf4 的 test_f2.py =====" -ForegroundColor Yellow
Push-Location $old
uv run python -m pytest CampusPlanner/TestDriver/test_f2.py -v -p no:cacheprovider --tb=line
Pop-Location

Write-Host ""
Write-Host "===== 修改後：目前分支的 ConflictChecker.py + test_f2.py =====" -ForegroundColor Green
Push-Location $repo
uv run python -m pytest TestDriver/test_f2.py -v -p no:cacheprovider
Pop-Location

git -C $repo worktree remove --force $old
