"""【Claude 新增 10/16】pytest 共用設定：註冊 test_f1.py 用到的自訂標記。

沒註冊的話 pytest 會對每個 @pytest.mark.xxx 印出 PytestUnknownMarkWarning。
新增標記時請在 MARKERS 補一行。
"""

MARKERS = {
    "normal": "F1 正常案例（10 個）",
    "boundary": "F1 邊界案例（10 個）",
    "error": "F1 錯誤案例（10 個）",
    "extra": "補充案例（參數化與較細的檢查，不計入 30 個）",
    "persistence": "存檔與容錯載入（F6 相關，不計入 30 個）",
    "acceptance": "F1 驗收條件（資料量）",
}


def pytest_configure(config):
    for name, description in MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {description}")
