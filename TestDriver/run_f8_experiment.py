"""F8 效能實驗：對 8、12、16、20 門候選課程執行窮舉法與回溯法，輸出 Markdown 表格。

每組重複 repeats 次取時間中位數；每個演算法每次最多執行 time_limit 秒，逾時如實記為「未完成」。
執行：uv run python TestDriver/run_f8_experiment.py [repeats] [time_limit]
"""

import json
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "CampusPlanner", "Code"))

import SearchCompare as searchCompare  # noqa: E402


def Main(repeats=5, timeLimit=10.0):
    print(f"# 執行時間：{time.strftime('%Y-%m-%d %H:%M')}；Python {platform.python_version()}；"
          f"{platform.system()} {platform.machine()}；重複 {repeats} 次取中位數；時間上限 {timeLimit} 秒")
    print()
    print("| 候選數 | 窮舉節點 | 窮舉時間（秒） | 窮舉狀態 | 回溯節點 | 回溯時間（秒） | 回溯狀態 | 可行解（窮舉／回溯） | 一致 |")
    print("| ---: | ---: | ---: | :--- | ---: | ---: | :--- | ---: | :--- |")
    for count in (8, 12, 16, 20):
        with open(os.path.join(HERE, "TestInput", "F8", f"candidates_{count:02d}.json"), encoding="utf-8") as dataFile:
            dataset = json.load(dataFile)
        rows = searchCompare.RunExperiment(dataset, repeats=repeats if count <= 16 else 1, timeLimit=timeLimit)
        brute, back = rows["brute_force"], rows["backtracking"]
        state = {True: "完成", False: "未完成（逾時）"}
        consistent = {True: "是", False: "否", None: "無法判定"}[rows["consistent"]]
        print(f"| {count} | {brute['nodes']:,} | {brute['median_seconds']:.4f} | {state[brute['completed']]} "
              f"| {back['nodes']:,} | {back['median_seconds']:.4f} | {state[back['completed']]} "
              f"| {brute['solutions']:,}／{back['solutions']:,} | {consistent} |")


if __name__ == "__main__":
    arguments = sys.argv[1:]
    Main(int(arguments[0]) if arguments else 5, float(arguments[1]) if len(arguments) > 1 else 10.0)
