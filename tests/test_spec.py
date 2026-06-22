import pytest

from app.parsing import CSVParseError, ParsedCSV
from app.spec import ChartSpec, PanelSpec, validate_spec


def _spec() -> ChartSpec:
    return ChartSpec(
        title="T", x_title="X", x_eng=True, x_log=False,
        panels=[PanelSpec("增益", True, False), PanelSpec("相位", False, True)],
        assign={"gain": 0, "phase": 1, "noise": None},
    )


def test_to_from_json_roundtrip():
    spec = _spec()
    restored = ChartSpec.from_json(spec.to_json())
    assert restored == spec


def test_from_json_normalizes_types():
    # 字符串/数字布尔与整型下标都应被归一
    raw = (
        '{"title":"T","x_title":"X","x_eng":1,"x_log":0,'
        '"panels":[{"y_title":"Y","y_eng":0,"y_log":1}],'
        '"assign":{"a":"0","b":null}}'
    )
    spec = ChartSpec.from_json(raw)
    assert spec.x_eng is True and spec.x_log is False
    assert spec.panels[0].y_eng is False and spec.panels[0].y_log is True
    assert spec.assign == {"a": 0, "b": None}


def _parsed() -> ParsedCSV:
    return ParsedCSV(
        x_label="freq", x=[1.0, 2.0, 3.0],
        y_labels=["gain", "phase", "noise"],
        ys=[[1.0, 2.0, 3.0], [-1.0, 0.5, 2.0], [10.0, 20.0, 30.0]],
    )


def test_validate_ok():
    spec = ChartSpec("T", "X", True, False,
                     [PanelSpec("a", True, False), PanelSpec("b", True, False)],
                     {"gain": 0, "phase": 1, "noise": None})
    validate_spec(spec, _parsed())  # 不抛异常


def test_validate_empty_panels():
    spec = ChartSpec("T", "X", True, False, [],
                     {"gain": None, "phase": None, "noise": None})
    with pytest.raises(CSVParseError):
        validate_spec(spec, _parsed())


def test_validate_assign_keys_mismatch():
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, False)],
                     {"gain": 0})  # 少了 phase/noise
    with pytest.raises(CSVParseError):
        validate_spec(spec, _parsed())


def test_validate_panel_index_out_of_range():
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, False)],
                     {"gain": 0, "phase": 5, "noise": None})
    with pytest.raises(CSVParseError):
        validate_spec(spec, _parsed())


def test_validate_all_hidden():
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, False)],
                     {"gain": None, "phase": None, "noise": None})
    with pytest.raises(CSVParseError):
        validate_spec(spec, _parsed())


def test_validate_log_panel_with_nonpositive():
    # phase 含 -1，归到对数面板 0 → 报错
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, True)],
                     {"gain": 0, "phase": 0, "noise": None})
    with pytest.raises(CSVParseError):
        validate_spec(spec, _parsed())


def test_validate_log_panel_positive_ok():
    # 对数面板只含全正的 gain/noise，phase 隐藏 → 通过
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, True)],
                     {"gain": 0, "phase": None, "noise": 0})
    validate_spec(spec, _parsed())


def test_validate_x_log_nonpositive():
    parsed = ParsedCSV("f", [0.0, 1.0, 2.0], ["gain"], [[1.0, 2.0, 3.0]])
    spec = ChartSpec("T", "X", True, True, [PanelSpec("a", True, False)], {"gain": 0})
    with pytest.raises(CSVParseError):
        validate_spec(spec, parsed)
