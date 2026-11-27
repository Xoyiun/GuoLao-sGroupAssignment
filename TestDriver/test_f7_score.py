"""F7 偏好評分的自動化測試（迭代 4 以 TDD 開發：先寫這些測試，再實作）。

對應需求：週報/迭代4/Group/F7需求規格.md 第四、五節與驗收測試 T01–T05。
執行：python -m pytest -m f7 -v
"""

import pytest

import ScheduleOptimizer as optimizer

pytestmark = pytest.mark.f7


def Course(courseId, slots, credits=3):
    """組一門課；slots 寫成 [(星期, 節次), ...]。"""
    return {
        "course_id": courseId,
        "credits": credits,
        "time_slots": [{"day": day, "period": period} for day, period in slots],
    }


# ======================================================================
# T01、T02：偏好指標
# ======================================================================
def test_MetricsCountDaysGapsEarlyAndBlocks():
    """星期一第 1、2、5 節（早八、空堂 2 節、上午＋下午）＋星期三晚上第 a 節（已選課程）。"""
    plan = [Course("A", [(1, "1"), (1, "2")], credits=3), Course("B", [(1, "5")], credits=2)]
    enrolled = [Course("E", [(3, "a")], credits=1)]

    metrics = optimizer.CalculateScheduleMetrics(plan, enrolled)

    assert metrics["credits"] == 5            # 只算方案中新排入的課
    assert metrics["campus_days"] == 2        # 星期一、星期三
    assert metrics["gap_periods"] == 2        # 星期一第 3、4 節
    assert metrics["early_periods"] == 1      # 星期一第 1 節
    assert metrics["half_day_blocks"] == 3    # 星期一上午、星期一下午、星期三晚上


def test_MetricsPreferredRatio():
    """偏好比例 = 方案中的偏好課程數 ÷ 偏好課程總數；沒有偏好課程時為 0。"""
    plan = [Course("A", [(1, "5")]), Course("B", [(2, "5")])]

    assert optimizer.CalculateScheduleMetrics(plan, [], ["A", "C"])["preferred_ratio"] == 0.5
    assert optimizer.CalculateScheduleMetrics(plan, [], ["A", "B"])["preferred_ratio"] == 1.0
    assert optimizer.CalculateScheduleMetrics(plan, [])["preferred_ratio"] == 0


# ======================================================================
# T03–T05：評分公式與權重
# ======================================================================
def test_ScoreUsesDefaultWeights():
    """1.0×學分 − 2.0×到校天數 − 1.0×空堂 − 1.5×早八 − 0.5×半天區段 + 5.0×偏好比例。"""
    metrics = {"credits": 9, "campus_days": 2, "gap_periods": 1, "early_periods": 1,
               "half_day_blocks": 3, "preferred_ratio": 0.5}
    # 9 − 4 − 1 − 1.5 − 1.5 + 2.5 = 3.5
    assert optimizer.ScoreSchedule(metrics) == 3.5


def test_WeightsChangeRanking():
    """預設權重避開早八，LATE 第一；把早八權重設 0 後兩案同分，依代號 EARLY 第一（需求規格第五節）。"""
    early = optimizer.CalculateScheduleMetrics([Course("EARLY", [(1, "1"), (1, "2")])])
    late = optimizer.CalculateScheduleMetrics([Course("LATE", [(1, "5"), (1, "6")])])

    assert (optimizer.ScoreSchedule(early), optimizer.ScoreSchedule(late)) == (-1.0, 0.5)
    noEarlyPenalty = {"early_periods": 0}
    assert optimizer.ScoreSchedule(early, noEarlyPenalty) == optimizer.ScoreSchedule(late, noEarlyPenalty) == 0.5


@pytest.mark.parametrize("weights", [
    {"early_periods": -1},        # 負數
    {"campus_days": "很多"},       # 不是數字
    {"campus_days": True},        # bool 不算數字
    {"lunch_break": 1},           # 不存在的權重名稱
    ["campus_days"],              # 不是字典
])
def test_InvalidWeightsRejected(weights):
    assert optimizer.ValidateWeights(weights) is False


def test_ValidWeightsAccepted():
    assert optimizer.ValidateWeights(None) is True
    assert optimizer.ValidateWeights({"campus_days": 0, "credits": 2.5}) is True
