

MARKERS = {
    "normal": "F1 正常案例（10 個）",
    "boundary": "F1 邊界案例（11 個）",
    "error": "F1 錯誤案例（10 個）",
    "extra": "補充案例（參數化與較細的檢查，不計入 30 個）",
    "persistence": "存檔與容錯載入（F6 相關，不計入 30 個）",
    "acceptance": "F1 驗收條件（資料量）",
    "cli": "main.py 命令列介面（test_main.py，不計入 30 個）",  # 新增：main.py 的測試標記
}


def pytest_configure(config):
    for name, description in MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {description}")
