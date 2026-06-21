from app.storage import Storage, Chart


def test_save_and_get(tmp_path):
    store = Storage(tmp_path)
    chart = store.save_chart(
        "abc123xyz0", "标题", "X", "Y", True, False, False, True, b"x,y\n1k,3.3\n"
    )
    assert isinstance(chart, Chart)
    assert chart.id == "abc123xyz0"
    assert chart.x_eng is True
    assert chart.y_eng is False
    assert chart.x_log is False
    assert chart.y_log is True

    fetched = store.get_chart("abc123xyz0")
    assert fetched is not None
    assert fetched.title == "标题"
    assert fetched.y_log is True
    assert store.read_csv("abc123xyz0") == b"x,y\n1k,3.3\n"


def test_get_missing_returns_none(tmp_path):
    store = Storage(tmp_path)
    assert store.get_chart("nope") is None


def test_exists(tmp_path):
    store = Storage(tmp_path)
    assert store.exists("abc") is False
    store.save_chart("abc", "t", "x", "y", True, True, False, False, b"x,y\n1k,3.3\n")
    assert store.exists("abc") is True


def test_list_charts_desc(tmp_path):
    store = Storage(tmp_path)
    store.save_chart("id1", "first", "x", "y", True, True, False, False, b"x,y\n1k,3.3\n")
    store.save_chart("id2", "second", "x", "y", True, True, False, False, b"x,y\n1k,3.3\n")
    charts = store.list_charts()
    assert [c.id for c in charts] == ["id2", "id1"]


def test_persistence_across_instances(tmp_path):
    Storage(tmp_path).save_chart("keep", "t", "x", "y", True, True, False, False, b"x,y\n1k,3.3\n")
    assert Storage(tmp_path).get_chart("keep") is not None
