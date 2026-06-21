import math
from decimal import Decimal

# 仅用于坐标轴标签的工程计数法显示(format_eng),不参与输入解析。
_EXP_TO_PREFIX = {
    -15: "f", -12: "p", -9: "n", -6: "u", -3: "m", 0: "",
    3: "k", 6: "M", 9: "G", 12: "T",
}


class NumberParseError(ValueError):
    pass


def parse_number(s: str) -> float:
    """解析单元格数值。仅支持普通十进制与科学计数法(如 1.5e6),
    不支持 SI 词头(工程计数法只用于显示)。"""
    if s is None:
        raise NumberParseError("空值")
    text = s.strip()
    if text == "":
        raise NumberParseError("空值")
    try:
        value = float(text)
    except (ValueError, OverflowError):
        raise NumberParseError(f"`{s}` 无法解析为数值(仅支持十进制与科学计数法)")
    if not math.isfinite(value):
        raise NumberParseError(f"`{s}` 不是有限数值")
    return value


def _trim(value: float) -> str:
    text = f"{value:.6g}"
    return text


def format_plain(value: float) -> str:
    if value == 0:
        return "0"
    text = _trim(value)
    # Never emit scientific notation in axis labels: expand any exponent
    # (e.g. "2.4e+06") into plain decimal form while keeping ~6 sig figs.
    if "e" in text or "E" in text:
        text = format(Decimal(text), "f")
    return text


def format_eng(value: float) -> str:
    if value == 0:
        return "0"
    negative = value < 0
    magnitude = abs(value)
    exp3 = int(math.floor(math.log10(magnitude) / 3.0)) * 3
    exp3 = max(-15, min(12, exp3))
    mantissa = magnitude / (10.0 ** exp3)
    text = _trim(mantissa)

    # If mantissa rounds to >= 1000, carry into next SI prefix
    mantissa_val = float(text)
    if mantissa_val >= 1000.0 and exp3 < 12:
        exp3 += 3
        mantissa = magnitude / (10.0 ** exp3)
        text = _trim(mantissa)

    prefix = _EXP_TO_PREFIX[exp3]
    return ("-" if negative else "") + text + prefix


def nice_ticks(lo: float, hi: float, target: int = 6) -> list[float]:
    if lo == hi:
        lo, hi = lo - 1.0, hi + 1.0
    if lo > hi:
        lo, hi = hi, lo
    span = hi - lo
    raw_step = span / max(1, target)
    mag = 10.0 ** math.floor(math.log10(raw_step))
    norm = raw_step / mag
    if norm < 1.5:
        step = 1.0
    elif norm < 3.0:
        step = 2.0
    elif norm < 7.0:
        step = 5.0
    else:
        step = 10.0
    step *= mag
    start = math.ceil(lo / step) * step
    ticks: list[float] = []
    value = start
    while value <= hi + step * 1e-9:
        ticks.append(round(value, 12))
        value += step
    return ticks


def log_ticks(lo: float, hi: float) -> list[float]:
    if lo <= 0 or hi <= 0:
        raise ValueError("log_ticks 需要正数边界")
    if lo > hi:
        lo, hi = hi, lo
    start = int(math.floor(math.log10(lo)))
    end = int(math.ceil(math.log10(hi)))
    if end == start:
        end += 1
    return [10.0 ** k for k in range(start, end + 1)]
