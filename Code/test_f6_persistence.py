"""F6 JSON 持久化與容錯載入測試。"""

import copy
import json
import os
import shutil

import pytest

import data_manager
import f1_manager as f1
from data_manager import DataManager

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, "04_data_format.json")


def new_course(**overrides):
    course = {
        "course_id": "NEW101",
        "title": "測試課程",
        "credits": 3,
        "required": False,
        "teacher": "測試教授",
        "classroom_id": "TR-310",
        "capacity": 30,
        "time_slots": [{"day": 1, "period": "1"}],
    }
    course.update(overrides)
    return course


def load_seed_data():
    with open(SEED, encoding="utf-8") as file:
        return json.load(file)


@pytest.mark.persistence
def test_save_goes_to_save_path_and_seed_untouched(tmp_path):
    """存檔寫到工作檔，種子檔不變；重新載入後資料仍在。"""
    seed_copy = tmp_path / "seed.json"
    shutil.copy(SEED, seed_copy)
    seed_bytes = seed_copy.read_bytes()
    work = tmp_path / "work.json"

    manager = f1.F1Manager(str(seed_copy), save_path=str(work))
    assert manager.add_course(new_course()) == (True, f1.OK)

    assert seed_copy.read_bytes() == seed_bytes
    assert any(course["course_id"] == "NEW101" for course in json.loads(work.read_text("utf-8"))["courses"])
    reloaded = f1.F1Manager(str(work), save_path=str(work))
    assert f1.find_course(reloaded.data, "NEW101") is not None


@pytest.mark.persistence
def test_default_save_path_never_overwrites_seed(tmp_path):
    """未指定 save_path 時寫入同資料夾的 db.json，種子檔保持不變。"""
    seed_copy = tmp_path / "seed.json"
    shutil.copy(SEED, seed_copy)
    seed_bytes = seed_copy.read_bytes()

    manager = f1.F1Manager(str(seed_copy))
    assert manager.add_course(new_course()) == (True, f1.OK)

    work = tmp_path / "db.json"
    assert seed_copy.read_bytes() == seed_bytes
    assert work.exists()
    reloaded = f1.F1Manager(str(work), save_path=str(work))
    assert f1.find_course(reloaded.data, "NEW101") is not None


@pytest.mark.persistence
def test_autosave_off_writes_nothing(tmp_path):
    """autosave=False 時，新增資料不會產生任何檔案。"""
    work = tmp_path / "work.json"
    manager = f1.F1Manager(SEED, save_path=str(work), autosave=False)
    assert manager.add_course(new_course()) == (True, f1.OK)
    assert not work.exists()


@pytest.mark.persistence
def test_successful_change_keeps_existing_getter_reference_live():
    manager = f1.F1Manager(SEED, autosave=False)
    courses = manager.get_courses()

    assert manager.add_course(new_course()) == (True, f1.OK)
    assert courses is manager.get_courses()
    assert f1.find_course({"courses": courses}, "NEW101") is not None


@pytest.mark.persistence
def test_bad_record_skipped_and_logged(tmp_path):
    """缺欄位、非物件與欄位型別錯誤資料都略過並留下錯誤紀錄。"""
    raw = load_seed_data()
    raw["courses"].append({"course_id": "MISSING_FIELDS"})
    raw["courses"].append("not a dict")
    bad_type = copy.deepcopy(raw["courses"][0])
    bad_type["credits"] = "four"
    bad_index = len(raw["courses"])
    raw["courses"].append(bad_type)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    manager = DataManager(str(path))

    assert len(manager.get_courses()) == 20
    assert len(manager.load_errors) == 3
    assert any(
        f"courses[{bad_index}]" in error and "型別" in error
        for error in manager.load_errors
    )


@pytest.mark.persistence
@pytest.mark.parametrize(
    ("section", "field", "bad_value"),
    [
        ("classrooms", "capacity", True),
        ("courses", "time_slots", "Monday 1"),
        ("students", "enrolled_courses", "CS101"),
        ("activities", "time_slots", [{"day": "Friday", "period": "1"}]),
    ],
)
def test_records_with_invalid_field_types_are_skipped(tmp_path, section, field, bad_value):
    raw = load_seed_data()
    broken = copy.deepcopy(raw[section][0])
    broken[field] = bad_value
    raw[section].append(broken)
    path = tmp_path / f"bad-{section}.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    manager = DataManager(str(path))

    assert len(manager.data[section]) == len(raw[section]) - 1
    assert len(manager.load_errors) == 1
    assert f"{section}[{len(raw[section]) - 1}]" in manager.load_errors[0]


@pytest.mark.persistence
def test_corrupted_file_is_backed_up_and_not_overwritten(tmp_path):
    """整個 JSON 損毀時要備份並拒絕覆寫原檔。"""
    path = tmp_path / "broken.json"
    original = "{ this is not json"
    path.write_text(original, encoding="utf-8")

    manager = DataManager(str(path))

    assert manager.corrupted and manager.get_courses() == []
    assert manager.save() is False
    assert path.read_text(encoding="utf-8") == original
    assert (tmp_path / "broken.json.corrupt.bak").exists()


@pytest.mark.persistence
def test_missing_file_loads_empty_database(tmp_path):
    manager = DataManager(str(tmp_path / "missing.json"))
    assert manager.get_courses() == [] and not manager.corrupted


@pytest.mark.persistence
def test_replace_failure_preserves_original_and_cleans_temp_file(tmp_path, monkeypatch):
    path = tmp_path / "db.json"
    path.write_text(json.dumps(load_seed_data(), ensure_ascii=False), encoding="utf-8")
    original = path.read_bytes()
    manager = DataManager(str(path))
    manager.data["metadata"]["version"] = "updated"

    def fail_replace(_source, _destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(data_manager.os, "replace", fail_replace)

    assert manager.save() is False
    assert path.read_bytes() == original
    assert not (tmp_path / "db.json.tmp").exists()


@pytest.mark.persistence
def test_json_serialization_failure_preserves_original_and_cleans_temp_file(tmp_path):
    path = tmp_path / "db.json"
    path.write_text(json.dumps(load_seed_data(), ensure_ascii=False), encoding="utf-8")
    original = path.read_bytes()
    manager = DataManager(str(path))
    manager.data["metadata"]["not_json_serializable"] = object()

    assert manager.save() is False
    assert path.read_bytes() == original
    assert not (tmp_path / "db.json.tmp").exists()


@pytest.mark.persistence
def test_autosave_failure_rolls_back_memory_and_keeps_disk_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "db.json"
    shutil.copy(SEED, path)
    original = path.read_bytes()
    manager = f1.F1Manager(str(path))
    before = copy.deepcopy(manager.data)

    def fail_replace(_source, _destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(data_manager.os, "replace", fail_replace)

    assert manager.add_course(new_course()) == (False, "SAVE_FAILED")
    assert manager.data == before
    assert path.read_bytes() == original
    assert not (tmp_path / "db.json.tmp").exists()
