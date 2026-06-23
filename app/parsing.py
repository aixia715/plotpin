import io
from dataclasses import dataclass

import pandas as pd

from app.eng_notation import NumberParseError, parse_number


class CSVParseError(Exception):
    pass


@dataclass
class ParsedCSV:
    x_label: str
    x: list[float]
    y_labels: list[str]
    ys: list[list[float]]


def decode_bytes(raw: bytes) -> str:
    for encoding in ("utf-8", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CSVParseError("无法识别文件编码(已尝试 UTF-8、GBK)")


def read_csv_bytes(raw: bytes) -> ParsedCSV:
    text = decode_bytes(raw)
    try:
        frame = pd.read_csv(io.StringIO(text), dtype=str)
    except Exception:
        raise CSVParseError("文件无法识别为 CSV")
    if frame.shape[1] < 2:
        raise CSVParseError("至少需要 X 列和 1 个 Y 列")
    if frame.shape[0] < 1:
        raise CSVParseError("CSV 没有数据行")
    columns = [str(c) for c in frame.columns]
    if len(set(columns)) != len(columns):
        raise CSVParseError("表头存在重复列名")

    def parse_cell(value, row_idx: int, col_idx: int) -> float:
        cell = str(value)
        try:
            return parse_number(cell)
        except NumberParseError as err:
            raise CSVParseError(
                f"第 {row_idx + 2} 行 第 {col_idx + 1} 列 `{cell}` 无法解析:{err}"
            )

    x_values: list[float] = []
    for r, raw_cell in enumerate(frame.iloc[:, 0].tolist()):
        x_values.append(parse_cell(raw_cell, r, 0))

    y_labels = columns[1:]
    y_series: list[list[float]] = []
    for c in range(1, frame.shape[1]):
        col_values: list[float] = []
        for r, raw_cell in enumerate(frame.iloc[:, c].tolist()):
            col_values.append(parse_cell(raw_cell, r, c))
        y_series.append(col_values)

    return ParsedCSV(
        x_label=columns[0],
        x=x_values,
        y_labels=y_labels,
        ys=y_series,
    )
