"""目前命令列入口的單元測試。

測試直接使用 ``Main`` 現行公開介面，不依賴已移除的舊版整份種子檔。
"""

import pytest

import Main as main


pytestmark = pytest.mark.cli


def test_input_parsers():
    assert main.ParseInt(" 42 ") == 42
    assert main.ParseInt("not-a-number") == "not-a-number"
    assert main.ParseBool("必修") is True
    assert main.ParseBool("選修") is False
    assert main.ParseBool("未知") is None
    assert main.ParseTimeSlots("1-2, 3-4") == [
        {"day": 1, "period": "2"},
        {"day": 3, "period": "4"},
    ]


def test_main_can_exit_without_interaction(tmp_path):
    output = []
    assert main.Main(ask=lambda _: "0", show=output.append, dataDir=str(tmp_path)) is None
    assert any("課程與學生資料管理" in line for line in output)


def test_import_command_copies_current_data_layout(tmp_path):
    target = tmp_path / "imported"
    result = main.Main(
        show=lambda _: None,
        dataDir=str(target),
        arguments=["import", "CampusPlanner/UserData", str(target)],
    )
    assert result is True
    assert (target / "Classroom.json").exists()
    assert (target / "CampusGraph.json").exists()
    assert (target / "Courses").is_dir()
    assert (target / "Students").is_dir()
