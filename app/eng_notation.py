import math
import re

PREFIXES: dict[str, float] = {
    "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
    "k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12,
}
_EXP_TO_PREFIX = {
    -15: "f", -12: "p", -9: "n", -6: "u", -3: "m", 0: "",
    3: "k", 6: "M", 9: "G", 12: "T",
}
_NUM_RE = re.compile(r"^([+-]?)(\d+(?:\.\d+)?)([fpnumkMGT]?)$")


class EngParseError(ValueError):
    pass


def parse_eng(s: str) -> float:
    if s is None:
        raise EngParseError("空值")
    text = s.strip()
    if text == "":
        raise EngParseError("空值")
    match = _NUM_RE.match(text)
    if not match:
        raise EngParseError(f"`{s}` 无法解析")
    sign, mantissa_str, prefix = match.groups()
    mantissa = float(mantissa_str)
    if mantissa == 0:
        return 0.0
    if not (1.0 <= mantissa < 1000.0):
        raise EngParseError(f"`{s}` 的数值部分必须落在 [1, 1000) 或为 0")
    factor = PREFIXES[prefix] if prefix else 1.0
    value = mantissa * factor
    return -value if sign == "-" else value


def _trim(value: float) -> str:
    text = f"{value:.6g}"
    return text


def format_plain(value: float) -> str:
    if value == 0:
        return "0"
    return _trim(value)


def format_eng(value: float) -> str:
    if value == 0:
        return "0"
    negative = value < 0
    magnitude = abs(value)
    exp3 = int(math.floor(math.log10(magnitude) / 3.0)) * 3
    exp3 = max(-15, min(12, exp3))
    mantissa = magnitude / (10.0 ** exp3)
    prefix = _EXP_TO_PREFIX[exp3]
    text = _trim(mantissa)
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
