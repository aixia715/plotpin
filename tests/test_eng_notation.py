import pytest
from app.eng_notation import (
    parse_eng,
    format_eng,
    format_plain,
    nice_ticks,
    log_ticks,
    EngParseError,
)


@pytest.mark.parametrize("text,expected", [
    ("47k", 47000.0),
    ("100m", 0.1),
    ("3.3", 3.3),
    ("0", 0.0),
    ("1k", 1000.0),
    ("999.9", 999.9),
    ("1", 1.0),
    ("-47k", -47000.0),
    ("470u", 470e-6),
    ("2.2M", 2.2e6),
    (" 47k ", 47000.0),
])
def test_parse_eng_valid(text, expected):
    assert parse_eng(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", [
    "47x",      # 非法词头
    "4700",     # 无词头但 >=1000
    "1000",     # 边界,>=1000 非法
    "0.5",      # <1 无词头
    "",         # 空值
    "   ",      # 仅空白
    "47 k",     # 中间空格
    "abc",      # 非数字
])
def test_parse_eng_invalid(text):
    with pytest.raises(EngParseError):
        parse_eng(text)


@pytest.mark.parametrize("value,expected", [
    (47000.0, "47k"),
    (0.1, "100m"),
    (3.3, "3.3"),
    (0.0, "0"),
    (1000.0, "1k"),
    (-47000.0, "-47k"),
    (470e-6, "470u"),
    (2.2e6, "2.2M"),
])
def test_format_eng(value, expected):
    assert format_eng(value) == expected


@pytest.mark.parametrize("value,expected", [
    (47000.0, "47000"),
    (0.1, "0.1"),
    (3.3, "3.3"),
    (0.0, "0"),
])
def test_format_plain(value, expected):
    assert format_plain(value) == expected


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
