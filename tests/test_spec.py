import pytest

from app.parsing import CSVParseError, ParsedCSV
from app.spec import (
    ChartSpec,
    PanelSpec,
    auto_panel_y_title,
    auto_titles,
    default_spec,
    filename_stem,
    validate_spec,
)


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


def test_apply_log_filter_y_panel_gaps_nonpositive():
    from app.spec import apply_log_filter
    # phase 含 -1，归到对数面板 0 → 现在剔除而非报错
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, True)],
                     {"gain": 0, "phase": 0, "noise": None})
    out, report = apply_log_filter(spec=spec, parsed=_parsed())
    # phase 第 0 个值 -1 被置空成缺口；gain 不变
    assert out.ys[_parsed().y_labels.index("phase")][0] is None
    assert out.ys[_parsed().y_labels.index("gain")] == [1.0, 2.0, 3.0]
    assert report.y_dropped is True
    assert report.x_dropped is False


def test_validate_log_panel_positive_ok():
    # 对数面板只含全正的 gain/noise，phase 隐藏 → 通过
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, True)],
                     {"gain": 0, "phase": None, "noise": 0})
    validate_spec(spec, _parsed())


def test_apply_log_filter_x_drops_nonpositive_rows():
    from app.spec import apply_log_filter
    parsed = ParsedCSV("f", [0.0, 1.0, 2.0], ["gain"], [[5.0, 2.0, 3.0]])
    spec = ChartSpec("T", "X", True, True, [PanelSpec("a", True, False)], {"gain": 0})
    out, report = apply_log_filter(parsed, spec)
    assert out.x == [1.0, 2.0]
    assert out.ys == [[2.0, 3.0]]       # y 同步对齐删除
    assert report.x_dropped is True
    assert report.y_dropped is False


def test_validate_empty_panel_rejected():
    # 2 面板但所有曲线都在面板 0 → 面板 1 空 → 应报错
    spec = ChartSpec("T", "X", True, False,
                     [PanelSpec("a", True, False), PanelSpec("b", True, True)],
                     {"gain": 0, "phase": 0, "noise": 0})
    with pytest.raises(CSVParseError):
        validate_spec(spec, _parsed())


def test_apply_log_filter_no_log_unchanged():
    from app.spec import apply_log_filter
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, False)],
                     {"gain": 0, "phase": 0, "noise": 0})
    out, report = apply_log_filter(_parsed(), spec)
    assert out.ys == _parsed().ys
    assert report.x_dropped is False and report.y_dropped is False


def test_apply_log_filter_nonlog_panel_keeps_nonpositive():
    from app.spec import apply_log_filter
    # phase(-1) 在非 log 面板 1 → 保留；面板 0 为 log 只含全正 gain
    spec = ChartSpec("T", "X", True, False,
                     [PanelSpec("a", True, True), PanelSpec("b", True, False)],
                     {"gain": 0, "phase": 1, "noise": None})
    out, report = apply_log_filter(_parsed(), spec)
    assert out.ys[_parsed().y_labels.index("phase")] == [-1.0, 0.5, 2.0]
    assert report.y_dropped is False


def test_apply_log_filter_all_positive_no_drop():
    from app.spec import apply_log_filter
    spec = ChartSpec("T", "X", True, True, [PanelSpec("a", True, True)],
                     {"gain": 0, "phase": None, "noise": 0})
    out, report = apply_log_filter(_parsed(), spec)
    assert report.x_dropped is False and report.y_dropped is False


def test_apply_log_filter_x_all_nonpositive_raises():
    from app.spec import apply_log_filter
    parsed = ParsedCSV("f", [0.0, -1.0], ["gain"], [[2.0, 3.0]])
    spec = ChartSpec("T", "X", True, True, [PanelSpec("a", True, False)], {"gain": 0})
    with pytest.raises(CSVParseError):
        apply_log_filter(parsed, spec)


def test_apply_log_filter_panel_all_nonpositive_raises():
    from app.spec import apply_log_filter
    parsed = ParsedCSV("f", [1.0, 2.0], ["gain"], [[0.0, -1.0]])
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, True)], {"gain": 0})
    with pytest.raises(CSVParseError):
        apply_log_filter(parsed, spec)


def test_apply_log_filter_panel_one_col_allnonpositive_ok():
    from app.spec import apply_log_filter
    # gain 全 ≤0 但同面板 noise 有正数 → 不报错，gain 整列置空
    parsed = ParsedCSV("f", [1.0, 2.0], ["gain", "noise"], [[0.0, -1.0], [10.0, 20.0]])
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, True)],
                     {"gain": 0, "noise": 0})
    out, report = apply_log_filter(parsed, spec)
    assert out.ys[0] == [None, None]
    assert out.ys[1] == [10.0, 20.0]
    assert report.y_dropped is True


def test_validate_spec_partial_nonpositive_now_ok():
    from app.spec import validate_spec
    # x_log 含 0 但有正数剩余 → validate_spec 不再抛
    parsed = ParsedCSV("f", [0.0, 1.0, 2.0], ["gain"], [[5.0, 2.0, 3.0]])
    spec = ChartSpec("T", "X", True, True, [PanelSpec("a", True, False)], {"gain": 0})
    validate_spec(spec, parsed)  # 不抛异常


def test_validate_spec_all_nonpositive_still_raises():
    from app.spec import validate_spec
    parsed = ParsedCSV("f", [0.0, -1.0], ["gain"], [[2.0, 3.0]])
    spec = ChartSpec("T", "X", True, True, [PanelSpec("a", True, False)], {"gain": 0})
    with pytest.raises(CSVParseError):
        validate_spec(spec, parsed)


def _parsed_with_labels(y_labels):
    return ParsedCSV(
        x_label="freq",
        x=[1000.0, 2000.0],
        y_labels=y_labels,
        ys=[[1.0, 2.0] for _ in y_labels],
    )


def test_default_spec_single_panel_all_columns_assigned():
    parsed = _parsed_with_labels(["gain", "phase"])
    spec = default_spec(parsed, title="我的图", x_title="频率")
    assert spec.title == "我的图"
    assert spec.x_title == "频率"
    assert spec.x_eng is False and spec.x_log is False
    assert len(spec.panels) == 1
    assert spec.panels[0].y_title == "gain"  # 首个 Y 列名
    assert spec.panels[0].y_eng is False and spec.panels[0].y_log is False
    assert spec.assign == {"gain": 0, "phase": 0}  # 所有 Y 列进面板 0


def test_default_spec_passes_x_axis_flags():
    spec = default_spec(_parsed_with_labels(["y"]), title="t", x_title="x", x_eng=True, x_log=True)
    assert spec.x_eng is True and spec.x_log is True


def test_default_spec_result_passes_validation():
    parsed = _parsed_with_labels(["a", "b"])
    spec = default_spec(parsed, title="t", x_title="x")
    validate_spec(spec, parsed)  # 不抛异常即通过


def test_filename_stem_strips_extension():
    assert filename_stem("measure.csv") == "measure"
    assert filename_stem("a.b.csv") == "a.b"
    assert filename_stem("/tmp/我的 数据.XLSX") == "我的 数据"


def test_filename_stem_handles_missing_or_empty():
    assert filename_stem(None) == "chart"
    assert filename_stem("") == "chart"
    assert filename_stem(".csv") == "csv"  # 视作无扩展名主名
    assert filename_stem(".gitignore") == "gitignore"


def test_auto_titles_from_filename_and_header():
    parsed = ParsedCSV("freq", [1.0], ["gain"], [[1.0]])
    assert auto_titles("measure.csv", parsed) == ("measure", "freq")


def test_auto_titles_missing_filename_falls_back():
    parsed = ParsedCSV("时间", [1.0], ["y"], [[1.0]])
    assert auto_titles(None, parsed) == ("chart", "时间")


def test_auto_panel_y_title_uses_first_assigned_header():
    assign = {"gain": 0, "phase": 1, "noise": 1}
    y_labels = ["gain", "phase", "noise"]
    assert auto_panel_y_title(0, assign, y_labels) == "gain"
    assert auto_panel_y_title(1, assign, y_labels) == "phase"


def test_auto_panel_y_title_empty_panel_fallback():
    assign = {"gain": 0, "phase": None}
    # 面板 1 无曲线分配 -> 兜底 "Y"
    assert auto_panel_y_title(1, assign, ["gain", "phase"]) == "Y"
