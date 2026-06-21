import pytest
from app.eng_notation import (
    parse_number,
    format_eng,
    format_plain,
    nice_ticks,
    log_ticks,
    NumberParseError,
)


@pytest.mark.parametrize("text,expected", [
    # 普通十进制,任意量级
    ("3.3", 3.3),
    ("999.9", 999.9),
    ("1", 1.0),
    ("4700", 4700.0),
    ("1000", 1000.0),
    ("1500000", 1500000.0),
    ("0.5", 0.5),
    ("-1500000", -1500000.0),
    ("0.000001", 0.000001),
    ("-118.7", -118.7),
    ("+3.3", 3.3),
    (" 47 ", 47.0),
    # 科学计数法
    ("1.5e6", 1500000.0),
    ("2.4E-3", 0.0024),
    ("1e-12", 1e-12),
    ("-1.4e2", -140.0),
    # 0 的各种写法都通过
    ("0", 0.0),
    ("0.0", 0.0),
    ("0e0", 0.0),
    ("-0", 0.0),
])
def test_parse_number_valid(text, expected):
    assert parse_number(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", [
    "47k",      # 不再支持 SI 词头输入
    "1.5M",     # 不再支持 SI 词头输入
    "470u",     # 不再支持 SI 词头输入
    "47x",      # 乱字符
    "",         # 空值
    "   ",      # 仅空白
    "1.5 e6",   # 中间空格
    "abc",      # 非数字
    "inf",      # 非有限
    "nan",      # 非有限
])
def test_parse_number_invalid(text):
    with pytest.raises(NumberParseError):
        parse_number(text)


@pytest.mark.parametrize("value,expected", [
    (47000.0, "47k"),
    (0.1, "100m"),
    (3.3, "3.3"),
    (0.0, "0"),
    (1000.0, "1k"),
    (-47000.0, "-47k"),
    (470e-6, "470u"),
    (2.2e6, "2.2M"),
    (999999.9, "1M"),
])
def test_format_eng(value, expected):
    assert format_eng(value) == expected


@pytest.mark.parametrize("value,expected", [
    (47000.0, "47000"),
    (0.1, "0.1"),
    (3.3, "3.3"),
    (0.0, "0"),
    (2.4e6, "2400000"),       # no scientific notation
    (1234567.0, "1234570"),   # ~6 sig figs, plain decimal
    (1e-12, "0.000000000001"),
])
def test_format_plain(value, expected):
    result = format_plain(value)
    assert result == expected
    assert "e" not in result and "E" not in result


def test_nice_ticks_basic():
    ticks = nice_ticks(0.0, 100.0, target=6)
    assert ticks[0] <= 0.0
    assert ticks[-1] >= 100.0
    assert all(ticks[i] < ticks[i + 1] for i in range(len(ticks) - 1))
    assert 5 <= len(ticks) <= 9


def test_nice_ticks_equal_bounds():
    ticks = nice_ticks(5.0, 5.0)
    assert len(ticks) >= 2


def test_log_ticks_decades():
    ticks = log_ticks(1000.0, 2.4e6)
    # 覆盖 [1e3, 1e7] 的十进制刻度
    assert ticks == [1e3, 1e4, 1e5, 1e6, 1e7]


def test_log_ticks_subdecade_range():
    ticks = log_ticks(0.1, 0.3)
    # 即便范围不足一个十进制,也至少给出包住区间的两端幂
    assert ticks[0] <= 0.1
    assert ticks[-1] >= 0.3
    assert all(t > 0 for t in ticks)
