

MARKERS = {
    "normal": "F1 正常案例（10 個）",
    "boundary": "F1 邊界案例（11 個）",
    "error": "F1 錯誤案例（10 個）",
    "extra": "補充案例（參數化與較細的檢查，不計入 30 個）",
    "persistence": "存檔與容錯載入（F6 相關，不計入 30 個）",
    "acceptance": "F1 驗收條件（資料量）",
}


def pytest_configure(config):
    for name, description in MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {description}")
