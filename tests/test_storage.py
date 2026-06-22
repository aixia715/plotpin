from app.spec import ChartSpec, PanelSpec
from app.storage import Chart, Storage


def _spec(title="标题") -> ChartSpec:
    return ChartSpec(title, "X", True, False,
                     [PanelSpec("Y", True, False)], {"gain": 0})


def test_save_and_get(tmp_path):
    store = Storage(tmp_path)
    chart = store.save_chart("abc123xyz0", _spec(), b"x,gain\n1k,3.3\n")
    assert isinstance(chart, Chart)
    assert chart.id == "abc123xyz0"
    assert chart.spec.panels[0].y_title == "Y"

    fetched = store.get_chart("abc123xyz0")
    assert fetched is not None
    assert fetched.title == "标题"
    assert fetched.spec == _spec()
    assert store.read_csv("abc123xyz0") == b"x,gain\n1k,3.3\n"


def test_get_missing_returns_none(tmp_path):
    assert Storage(tmp_path).get_chart("nope") is None


def test_exists(tmp_path):
    store = Storage(tmp_path)
    assert store.exists("abc") is False
    store.save_chart("abc", _spec(), b"x,gain\n1k,3.3\n")
    assert store.exists("abc") is True


def test_list_charts_desc(tmp_path):
    store = Storage(tmp_path)
    store.save_chart("id1", _spec("first"), b"x,gain\n1k,3.3\n")
    store.save_chart("id2", _spec("second"), b"x,gain\n1k,3.3\n")
    assert [c.id for c in store.list_charts()] == ["id2", "id1"]


def test_persistence_across_instances(tmp_path):
    Storage(tmp_path).save_chart("keep", _spec(), b"x,gain\n1k,3.3\n")
    assert Storage(tmp_path).get_chart("keep") is not None
