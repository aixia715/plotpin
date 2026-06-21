import pytest
from app.parsing import read_csv_bytes, decode_bytes, ParsedCSV, CSVParseError


def _csv(text: str, encoding: str = "utf-8") -> bytes:
    return text.encode(encoding)


def test_read_valid_multi_y():
    raw = _csv("freq,gain,phase\n1k,3.3,100m\n2k,6.6,200m\n")
    parsed = read_csv_bytes(raw)
    assert isinstance(parsed, ParsedCSV)
    assert parsed.x_label == "freq"
    assert parsed.x == pytest.approx([1000.0, 2000.0])
    assert parsed.y_labels == ["gain", "phase"]
    assert parsed.ys[0] == pytest.approx([3.3, 6.6])
    assert parsed.ys[1] == pytest.approx([0.1, 0.2])


def test_decode_gbk_fallback():
    raw = "频率,增益\n1k,3.3\n".encode("gbk")
    text = decode_bytes(raw)
    assert "频率" in text


def test_reject_single_column():
    raw = _csv("only\n1k\n2k\n")
    with pytest.raises(CSVParseError):
        read_csv_bytes(raw)


def test_reject_bad_cell_reports_location():
    raw = _csv("x,y\n1k,3.3\n2k,47x\n")
    with pytest.raises(CSVParseError) as exc:
        read_csv_bytes(raw)
    msg = str(exc.value)
    assert "47x" in msg


def test_reject_empty_cell():
    raw = _csv("x,y\n1k,3.3\n2k,\n")
    with pytest.raises(CSVParseError):
        read_csv_bytes(raw)


def test_reject_not_csv():
    with pytest.raises(CSVParseError):
        read_csv_bytes(b"\x00\x01\x02 not text at all")


def _parsed():
    return ParsedCSV(
        x_label="x", x=[1.0, 10.0, 100.0],
        y_labels=["y"], ys=[[0.0, 5.0, 50.0]],
    )


def test_log_ok_when_all_positive():
    from app.parsing import check_log_positivity
    p = ParsedCSV("x", [1.0, 10.0], ["y"], [[2.0, 20.0]])
    check_log_positivity(p, True, True)  # 不抛异常


def test_log_rejects_nonpositive_y():
    from app.parsing import check_log_positivity
    with pytest.raises(CSVParseError):
        check_log_positivity(_parsed(), False, True)  # Y 含 0


def test_log_rejects_nonpositive_x():
    from app.parsing import check_log_positivity
    p = ParsedCSV("x", [0.0, 10.0], ["y"], [[2.0, 20.0]])
    with pytest.raises(CSVParseError):
        check_log_positivity(p, True, False)  # X 含 0


def test_no_check_when_log_off():
    from app.parsing import check_log_positivity
    check_log_positivity(_parsed(), False, False)  # 线性轴,含 0 也不报错
