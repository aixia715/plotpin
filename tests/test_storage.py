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


def test_delete_removes_db_row_csv_and_cache(tmp_path):
    store = Storage(tmp_path)
    store.save_chart("del1", _spec(), b"x,gain\n1k,3.3\n")
    # 模拟已落盘的缓存图（缩略图 + 全尺寸 PNG/SVG）
    store.cache_path("del1", "thumb.png").write_bytes(b"thumb")
    store.cache_path("del1", "png").write_bytes(b"png")
    store.cache_path("del1", "svg").write_bytes(b"svg")

    assert store.delete_chart("del1") is True

    assert store.get_chart("del1") is None
    assert store.exists("del1") is False
    assert not store.csv_path("del1").exists()
    assert not store.cache_path("del1", "thumb.png").exists()
    assert not store.cache_path("del1", "png").exists()
    assert not store.cache_path("del1", "svg").exists()


def test_delete_missing_returns_false(tmp_path):
    assert Storage(tmp_path).delete_chart("nope") is False


def test_delete_only_targets_its_own_files(tmp_path):
    # 前缀相近的 id 不应被误删（del1 不能波及 del10）
    store = Storage(tmp_path)
    store.save_chart("del1", _spec(), b"x,gain\n1k,3.3\n")
    store.save_chart("del10", _spec(), b"x,gain\n1k,3.3\n")
    store.cache_path("del10", "png").write_bytes(b"png")

    store.delete_chart("del1")

    assert store.get_chart("del10") is not None
    assert store.csv_path("del10").exists()
    assert store.cache_path("del10", "png").exists()


def test_delete_rejects_non_alnum_id(tmp_path):
    # 防御纵深：合法 id 仅含 [A-Za-z0-9]（见 ids.new_id）。
    # 空串 / 路径遍历等非法 id 必须被拒，不得触碰任何文件。
    store = Storage(tmp_path)
    store.save_chart("good123", _spec(), b"x,gain\n1k,3.3\n")
    # cache 目录里的 dotfile：空 id 经 glob(".*") 不得误删
    (store.cache_dir / ".keep").write_bytes(b"k")
    # 数据目录外的文件：路径遍历 id 不得删到
    outside = tmp_path / "secret.csv"  # csv_dir/../secret.csv 指向此处
    outside.write_bytes(b"secret")

    for bad in ["", "../secret", "../../etc/passwd", "a/b", "中文", "a.b"]:
        assert store.delete_chart(bad) is False

    assert (store.cache_dir / ".keep").exists()
    assert outside.exists()
    assert store.get_chart("good123") is not None
