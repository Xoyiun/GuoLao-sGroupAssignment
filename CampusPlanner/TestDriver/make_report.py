#!/usr/bin/env python3
"""把 pytest 測試結果做成單一 HTML 報告，方便給小組員看。

用法（在 test_f1.py 所在的資料夾執行）：
    python make_report.py                       # 執行 test_f1.py 並產生 report_f1.html
    python make_report.py test_f2.py            # 換成別的測試檔，輸出 report_f2.html
    python make_report.py -o 我的報告.html      # 指定輸出檔名
    python make_report.py --from-xml r.xml      # 不重跑，直接用既有的 junit XML

報告內容：
    - 全部測試的通過數與通過率
    - 核心 30 個（正常、邊界、錯誤各 10）的進度
    - 每個測試的中文說明（取自測試函式的 docstring）與結果
    - 失敗測試的錯誤訊息（可展開）

說明與分類的來源：
    分類 = 測試函式上的 @pytest.mark.normal / boundary / error / extra / persistence / acceptance
    說明 = 測試函式的第一行 docstring
需要安裝 pytest（只有在不使用 --from-xml 時）。
"""

import argparse
import ast
import datetime
import html
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

# (標記, 顯示名稱, 說明, 目標函式數；None 表示不計入核心)
CATEGORIES = [
    ("normal", "正常案例", "合法輸入，預期成功", 10),
    ("boundary", "邊界案例", "剛好在合法範圍邊緣，預期成功或行為正確", 10),
    ("error", "錯誤與衝突案例", "違規輸入，預期被拒絕並回傳正確的錯誤碼", 10),
    ("extra", "補充案例", "更多數值與較細的規則（不計入核心 30 個）", None),
    ("persistence", "存檔與容錯載入", "F6 相關（不計入核心 30 個）", None),
    ("acceptance", "驗收條件", "F1 資料量驗收（不計入核心 30 個）", None),
]
CORE = [c for c in CATEGORIES if c[3] is not None]
STATUSLABEL = {"passed": "通過", "failed": "失敗", "skipped": "略過", "notrun": "未執行"}
STATUSICON = {"passed": "✓", "failed": "✗", "skipped": "–", "notrun": "?"}


# ----------------------------------------------------------------------
# 讀取測試檔的標記與說明（不需要 import 測試檔，也不需要 pytest）
# ----------------------------------------------------------------------
def ParseTests(path):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    tests = []
    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
            continue
        marks = []
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Attribute)
                and target.value.attr == "mark"
                and isinstance(target.value.value, ast.Name)
                and target.value.value.id == "pytest"
                and target.attr != "parametrize"
            ):
                marks.append(target.attr)
        doc = (ast.get_docstring(node) or "").strip().splitlines()
        desc = doc[0] if doc else node.name[len("test_"):].replace("_", " ")
        tests.append({"name": node.name, "marks": marks, "desc": desc})
    return tests


# ----------------------------------------------------------------------
# 讀取 pytest 的 junit XML 結果
# ----------------------------------------------------------------------
def ParseResults(xmlPath):
    root = ET.parse(xmlPath).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    meta = {
        "timestamp": suite.get("timestamp", "") if suite is not None else "",
        "hostname": suite.get("hostname", "") if suite is not None else "",
    }
    byFunc = {}
    for tc in root.iter("testcase"):
        full = tc.get("name", "")
        base = full.split("[", 1)[0]
        status, message = "passed", ""
        for child in tc:
            if child.tag in ("failure", "error"):
                status = "failed"
                message = ((child.get("message") or "") + "\n" + (child.text or "")).strip()
            elif child.tag == "skipped":
                status = "skipped"
        byFunc.setdefault(base, []).append(
            {"case": full, "status": status, "time": float(tc.get("time") or 0), "message": message}
        )
    return byFunc, meta


def FuncStatus(cases):
    if not cases:
        return "notrun"
    if any(c["status"] == "failed" for c in cases):
        return "failed"
    if all(c["status"] == "skipped" for c in cases):
        return "skipped"
    return "passed"


def ShortId(name):
    m = re.match(r"test_([a-z])(\d+)_", name)
    return f"{m.group(1).upper()}{m.group(2)}" if m else name[len("test_"):]


# ----------------------------------------------------------------------
# 組裝 HTML
# ----------------------------------------------------------------------
CSS = """
:root{--bg:#fafaf9;--fg:#1c1917;--muted:#6b6560;--card:#fff;--border:#e2dfdc;
--ok:#166534;--ok-bg:#dcfce7;--bad:#991b1b;--bad-bg:#fee2e2;--neutral-bg:#f0eeec;--accent:#1d4ed8;}
@media (prefers-color-scheme:dark){:root{--bg:#161412;--fg:#f2efec;--muted:#a8a29e;--card:#201d1b;
--border:#3a3532;--ok:#86efac;--ok-bg:#14301f;--bad:#fca5a5;--bad-bg:#3b1515;--neutral-bg:#2a2624;--accent:#93c5fd;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,"Segoe UI","Microsoft JhengHei","Noto Sans TC",sans-serif;line-height:1.55}
main{max-width:980px;margin:0 auto;padding:28px 16px 56px}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.15rem;margin:36px 0 4px}
.sub{color:var(--muted);font-size:.9rem;margin:0 0 20px}
.banner{padding:12px 16px;border-radius:10px;font-weight:600;margin:16px 0}
.banner.ok{background:var(--ok-bg);color:var(--ok)}.banner.bad{background:var(--bad-bg);color:var(--bad)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.card .label{color:var(--muted);font-size:.85rem}.card .num{font-size:1.7rem;font-weight:700;margin:2px 0}
.card .note{color:var(--muted);font-size:.8rem}
.bar{height:8px;background:var(--neutral-bg);border-radius:99px;overflow:hidden;margin-top:8px}
.fill{height:100%;background:var(--ok)}.fill.bad{background:var(--bad)}
.catdesc{color:var(--muted);font-size:.88rem;margin:0 0 10px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden;font-size:.92rem}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--border);vertical-align:top}
th{background:var(--neutral-bg);font-weight:600;font-size:.82rem;color:var(--muted)}
tr:last-child td{border-bottom:none}
td.id{white-space:nowrap;font-weight:600;width:1%}td.num{white-space:nowrap;color:var(--muted);width:1%}
.badge{display:inline-block;padding:2px 9px;border-radius:99px;font-size:.8rem;font-weight:600;white-space:nowrap}
.badge.passed{background:var(--ok-bg);color:var(--ok)}.badge.failed{background:var(--bad-bg);color:var(--bad)}
.badge.skipped,.badge.notrun{background:var(--neutral-bg);color:var(--muted)}
.fname{display:block;color:var(--muted);font-size:.78rem;font-family:ui-monospace,Consolas,monospace}
details{margin-top:6px}summary{cursor:pointer;color:var(--accent);font-size:.85rem}
pre{white-space:pre-wrap;word-break:break-word;background:var(--neutral-bg);padding:10px;border-radius:8px;font-size:.8rem;margin:6px 0 0}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0 0}
.filters button{border:1px solid var(--border);background:var(--card);color:var(--fg);padding:6px 14px;border-radius:99px;cursor:pointer;font-size:.88rem}
.filters button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
footer{margin-top:40px;color:var(--muted);font-size:.8rem}
@media (max-width:560px){th:nth-child(4),td.num{display:none}}
"""

JS = """
const buttons=document.querySelectorAll('.filters button');
buttons.forEach(b=>b.addEventListener('click',()=>{
  buttons.forEach(x=>x.setAttribute('aria-pressed',x===b));
  const f=b.dataset.filter;
  document.querySelectorAll('tbody tr').forEach(r=>{r.hidden=!(f==='all'||r.dataset.status===f);});
}));
"""


def Esc(s):
    return html.escape(str(s), quote=True)


def BuildHtml(title, tests, byFunc, meta, testFile):
    # 分組
    groups = {key: [] for key, *_ in CATEGORIES}
    groups["uncategorized"] = []
    for t in tests:
        cases = byFunc.get(t["name"], [])
        t = dict(t, cases=cases, status=FuncStatus(cases))
        keys = [m for m in t["marks"] if m in groups] or ["uncategorized"]
        for k in keys:
            groups[k].append(t)

    allCases = [c for cases in byFunc.values() for c in cases]
    nCases = len(allCases)
    nPass = sum(1 for c in allCases if c["status"] == "passed")
    nFail = sum(1 for c in allCases if c["status"] == "failed")
    nSkip = sum(1 for c in allCases if c["status"] == "skipped")
    totalTime = sum(c["time"] for c in allCases)
    rate = (nPass / nCases * 100) if nCases else 0
    ok = nCases > 0 and nFail == 0

    out = []
    out.append(f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
               f'<meta name="viewport" content="width=device-width,initial-scale=1">'
               f'<title>{Esc(title)}</title><style>{CSS}</style></head><body><main>')
    out.append(f"<h1>{Esc(title)}</h1>")
    when = meta.get("timestamp") or datetime.datetime.now().isoformat(timespec="seconds")
    out.append(f'<p class="sub">測試檔：{Esc(os.path.basename(testFile))} ｜ 執行時間：{Esc(when[:19].replace("T", " "))}'
               f' ｜ 耗時 {totalTime:.2f} 秒</p>')

    if nCases == 0:
        out.append('<div class="banner bad">✗ 沒有讀到任何測試結果</div>')
    elif ok:
        out.append(f'<div class="banner ok">✓ 全部通過：{nPass} / {nCases} 個測試案例</div>')
    else:
        out.append(f'<div class="banner bad">✗ 有 {nFail} 個測試案例失敗（共 {nCases} 個）</div>')

    # 總覽卡片
    out.append('<div class="grid">')
    out.append(f'<div class="card"><div class="label">測試案例總數</div><div class="num">{nCases}</div>'
               f'<div class="note">通過 {nPass}・失敗 {nFail}・略過 {nSkip}</div></div>')
    out.append(f'<div class="card"><div class="label">通過率</div><div class="num">{rate:.0f}%</div>'
               f'<div class="bar"><div class="fill{" bad" if nFail else ""}" style="width:{rate:.1f}%"></div></div></div>')
    coreTotal = corePass = 0
    for key, name, d, target in CORE:
        funcs = groups[key]
        coreTotal += len(funcs)
        corePass += sum(1 for f in funcs if f["status"] == "passed")
    out.append(f'<div class="card"><div class="label">核心案例（正常＋邊界＋錯誤）</div>'
               f'<div class="num">{corePass} / {sum(c[3] for c in CORE)}</div>'
               f'<div class="note">目標：各類 10 個，共 30 個</div></div>')
    out.append("</div>")

    # 核心三類進度
    out.append("<h2>核心案例進度</h2>")
    out.append('<p class="catdesc">作業要求正常、邊界、錯誤各至少 10 個測試案例（此處以測試函式計）。</p>')
    out.append('<div class="grid">')
    for key, name, d, target in CORE:
        funcs = groups[key]
        passed = sum(1 for f in funcs if f["status"] == "passed")
        pct = min(passed / target * 100, 100)
        note = f"共 {len(funcs)} 個函式" + ("" if len(funcs) == target else f"（目標 {target}）")
        out.append(f'<div class="card"><div class="label">{Esc(name)}</div>'
                   f'<div class="num">{passed} / {target}</div>'
                   f'<div class="bar"><div class="fill{" bad" if passed < len(funcs) else ""}" style="width:{pct:.0f}%"></div></div>'
                   f'<div class="note">{Esc(note)}</div></div>')
    out.append("</div>")

    # 篩選
    out.append('<div class="filters" role="group" aria-label="篩選結果">'
               '<button data-filter="all" aria-pressed="true">全部</button>'
               '<button data-filter="passed" aria-pressed="false">只看通過</button>'
               '<button data-filter="failed" aria-pressed="false">只看失敗</button></div>')

    # 各類明細
    sections = list(CATEGORIES) + [("uncategorized", "未分類", "沒有標記的測試", None)]
    for key, name, desc, target in sections:
        funcs = groups[key]
        if not funcs:
            continue
        out.append(f"<h2>{Esc(name)}（{len(funcs)}）</h2>")
        out.append(f'<p class="catdesc">{Esc(desc)}</p>')
        out.append('<table><thead><tr><th>編號</th><th>測試內容與預期</th><th>結果</th><th>案例數</th></tr></thead><tbody>')
        for f in funcs:
            cases = f["cases"]
            n = len(cases)
            nOk = sum(1 for c in cases if c["status"] == "passed")
            counts = f"{nOk}/{n}" if n else "–"
            fails = [c for c in cases if c["status"] == "failed"]
            detail = ""
            if fails:
                body = "\n\n".join(f"[{c['case']}]\n{c['message']}" for c in fails)
                detail = f"<details><summary>查看失敗訊息</summary><pre>{Esc(body)}</pre></details>"
            out.append(
                f'<tr data-status="{f["status"]}"><td class="id">{Esc(ShortId(f["name"]))}</td>'
                f'<td>{Esc(f["desc"])}<span class="fname">{Esc(f["name"])}</span>{detail}</td>'
                f'<td><span class="badge {f["status"]}">{STATUSICON[f["status"]]} {STATUSLABEL[f["status"]]}</span></td>'
                f'<td class="num">{counts}</td></tr>'
            )
        out.append("</tbody></table>")

    out.append('<footer>案例數：同一個測試函式以多組參數執行時，會展開成多個案例（例如 6/6 代表 6 組參數全部通過）。'
               "本報告由 make_report.py 自動產生，重跑即可更新。</footer>")
    out.append(f"<script>{JS}</script></main></body></html>")
    return "".join(out)


# ----------------------------------------------------------------------
def RunPytest(testFile, xmlPath):
    """在測試檔所在資料夾執行 pytest，結果寫成 junit XML。有測試失敗時 pytest 回傳非 0，這是正常的。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", os.path.basename(testFile), "--junitxml", xmlPath, "-q"],
        cwd=os.path.dirname(os.path.abspath(testFile)),
        capture_output=True, env=env,
    )
    text = proc.stdout.decode("utf-8", errors="replace") + proc.stderr.decode("utf-8", errors="replace")
    if not os.path.exists(xmlPath) or os.path.getsize(xmlPath) == 0:
        raise RuntimeError("pytest 沒有產生結果檔。請確認已安裝 pytest（pip install pytest）。\n" + text[-1500:])
    return proc.returncode, text


def Main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="把 pytest 結果做成單一 HTML 報告")
    ap.add_argument("testFile", nargs="?", default="test_f1.py", help="測試檔（預設 test_f1.py）")
    ap.add_argument("-o", "--output", help="輸出的 HTML 檔名（預設 report_<測試檔名>.html）")
    ap.add_argument("--from-xml", dest="fromXml", help="直接讀既有的 junit XML，不重新執行測試")
    ap.add_argument("--title", help="報告標題")
    args = ap.parse_args()

    testFile = args.testFile
    if not os.path.exists(testFile):
        sys.exit(f"找不到測試檔：{testFile}")
    stem = os.path.splitext(os.path.basename(testFile))[0]
    output = args.output or f"report_{stem.replace('test_', '')}.html"
    title = args.title or f"{stem.replace('test_', '').upper()} 測試報告"

    tmpXml = None
    if args.fromXml:
        xmlPath = args.fromXml
    else:
        fd, tmpXml = tempfile.mkstemp(suffix=".xml")
        os.close(fd)
        xmlPath = tmpXml
        code, text = RunPytest(testFile, xmlPath)
    try:
        byFunc, meta = ParseResults(xmlPath)
    finally:
        if tmpXml and os.path.exists(tmpXml):
            os.remove(tmpXml)

    tests = ParseTests(testFile)
    page = BuildHtml(title, tests, byFunc, meta, testFile)
    with open(output, "w", encoding="utf-8") as f:
        f.write(page)

    cases = [c for v in byFunc.values() for c in v]
    failed = sum(1 for c in cases if c["status"] == "failed")
    print(f"已產生 {output}：{len(cases)} 個案例，失敗 {failed} 個")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    Main()
