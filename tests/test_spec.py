from app.spec import ChartSpec, PanelSpec


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
