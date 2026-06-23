import pytest
from app.parsing import read_csv_bytes, decode_bytes, ParsedCSV, CSVParseError


def _csv(text: str, encoding: str = "utf-8") -> bytes:
    return text.encode(encoding)


def test_read_valid_multi_y():
    raw = _csv("freq,gain,phase\n1000,3.3,0.1\n2000,6.6,0.2\n")
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
    raw = _csv("x,y\n1000,3.3\n2000,47x\n")
    with pytest.raises(CSVParseError) as exc:
        read_csv_bytes(raw)
    msg = str(exc.value)
    assert "47x" in msg
    assert "第 3 行" in msg
    assert "第 2 列" in msg


def test_reject_empty_cell():
    raw = _csv("x,y\n1000,3.3\n2000,\n")
    with pytest.raises(CSVParseError):
        read_csv_bytes(raw)


def test_reject_not_csv():
    with pytest.raises(CSVParseError):
        read_csv_bytes(b"\x00\x01\x02 not text at all")


def test_reject_undecodable_bytes():
    with pytest.raises(CSVParseError):
        read_csv_bytes(b"\x80\x81\x82\xff\xfe")
