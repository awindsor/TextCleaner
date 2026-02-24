from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _decode_bytes(data: bytes, input_encoding: str) -> str:
    if input_encoding == "auto":
        for candidate in ("utf-8", "latin-1"):
            try:
                return data.decode(candidate)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")
    return data.decode(input_encoding, errors="replace")


def read_text_file(path: Path, input_encoding: str) -> str:
    return _decode_bytes(path.read_bytes(), input_encoding)


def write_text_file(path: Path, text: str, output_charset: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    codec = "utf-8" if output_charset == "utf-8" else ("latin-1" if output_charset == "latin-1" else "ascii")
    path.write_text(text, encoding=codec, errors="ignore")


def load_csv_rows(input_csv: Path) -> tuple[list[dict[str, str]], list[str]]:
    with input_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def write_csv_rows(output_csv: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

