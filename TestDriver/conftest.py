

MARKERS = {
    "normal": "F1 正常案例（10 個）",
    "boundary": "F1 邊界案例（11 個）",
    "error": "F1 錯誤案例（10 個）",
    "extra": "補充案例（參數化與較細的檢查，不計入 30 個）",
    "persistence": "存檔與容錯載入（F6 相關，不計入 30 個）",
    "acceptance": "F1 驗收條件（資料量）",
    "cli": "main.py 命令列介面（test_main.py，不計入 30 個）",  # 新增：main.py 的測試標記
    "f2": "F2 衝堂與選課檢查（test_f2.py）",
    "f3": "F3 個人課表與空閒時段（test_f3.py）",
    "f4": "F4 校園活動與教室配置（test_f4.py）",
    "f5": "F5 多條件課程篩選（test_f5.py）",
    "f7": "F7 多條件最佳課表搜尋（test_f7.py）",
    "f8": "F8 搜尋演算法比較（test_f8.py）",
    "f9": "F9 校園路徑規劃（test_f9.py）",
    "f10": "F10 動態重新規劃（test_f10.py）",
}


def pytest_configure(config):
    for name, description in MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {description}")
