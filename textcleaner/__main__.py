from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .changelog import read_changelog_json, utc_now_iso, write_changelog_json, write_changelog_markdown
from .cleaner import CleanerConfig, TextCleaner, apply_edits, md5_text
from .io_ops import load_csv_rows, read_text_file, write_csv_rows, write_text_file


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reproducible text cleaning for CSVs and directory trees.")
    parser.add_argument("--version", action="version", version=f"textcleaner {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    clean = subparsers.add_parser("clean", help="Clean input and emit outputs + changelog.")
    _add_shared_mode_args(clean)
    clean.add_argument("--output-csv")
    clean.add_argument("--output-dir")
    clean.add_argument("--cleaned-column", default="text_cleaned")
    clean.add_argument("--extensions", default=".txt")
    clean.add_argument("--changelog-json", required=True)
    clean.add_argument("--changelog-md", required=True)
    clean.add_argument("--target-charset", choices=("utf-8", "latin-1", "ascii"), default="utf-8")
    clean.add_argument("--input-encoding", default="auto")
    clean.add_argument("--no-spellcheck", action="store_true")
    clean.add_argument("--language", default="en_US")
    clean.add_argument("--max-suggestion-distance", type=int, default=2)

    validate = subparsers.add_parser("validate", help="Validate current inputs against changelog MD5s.")
    _add_shared_mode_args(validate)
    validate.add_argument("--changelog-json", required=True)
    validate.add_argument("--input-encoding", default="auto")
    validate.add_argument("--extensions", default=".txt")

    reproduce = subparsers.add_parser("reproduce", help="Reproduce outputs from input + changelog edits.")
    _add_shared_mode_args(reproduce)
    reproduce.add_argument("--output-csv")
    reproduce.add_argument("--output-dir")
    reproduce.add_argument("--cleaned-column", default="text_cleaned")
    reproduce.add_argument("--changelog-json", required=True)
    reproduce.add_argument("--input-encoding", default="auto")
    reproduce.add_argument("--strict-md5", action="store_true", default=True)
    reproduce.add_argument("--no-strict-md5", action="store_false", dest="strict_md5")

    subparsers.add_parser("gui", help="Launch the PySide6 desktop interface.")

    return parser


def _add_shared_mode_args(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("--mode", choices=("csv", "dir"), required=True)
    subparser.add_argument("--input-csv")
    subparser.add_argument("--text-column", default="text")
    subparser.add_argument("--input-dir")


def _validate_mode_args(args: argparse.Namespace) -> None:
    if args.mode == "csv":
        if not args.input_csv or not args.text_column:
            raise SystemExit("CSV mode requires --input-csv and --text-column.")
    else:
        if not args.input_dir:
            raise SystemExit("Directory mode requires --input-dir.")


def _clean_csv(args: argparse.Namespace, cleaner: TextCleaner) -> dict[str, Any]:
    input_csv = Path(args.input_csv)
    output_csv = Path(args.output_csv)
    rows, fieldnames = load_csv_rows(input_csv)
    if args.text_column not in fieldnames:
        raise SystemExit(f"Column not found: {args.text_column}")
    if args.cleaned_column in fieldnames:
        raise SystemExit(f"Cleaned column overlaps existing CSV column: {args.cleaned_column}")
    output_fieldnames = list(fieldnames)
    output_fieldnames.append(args.cleaned_column)

    items: list[dict[str, Any]] = []
    output_rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows, start=1):
        raw_text = row.get(args.text_column, "") or ""
        result = cleaner.clean(raw_text)
        item_id = f"row:{row_index}"
        items.append(
            {
                "item_id": item_id,
                "row_index": row_index,
                "input_md5": result["input_md5"],
                "output_md5": result["output_md5"],
                "changed": result["changed"],
                "edits": result["edits"],
                "summary": result["summary"],
            }
        )
        out = dict(row)
        out[args.cleaned_column] = result["cleaned_text"]
        output_rows.append(out)

    write_csv_rows(output_csv, output_rows, output_fieldnames)
    return {"items": items, "total": len(items)}


def _resolve_extensions(extensions: str) -> set[str]:
    values = {part.strip().lower() for part in extensions.split(",") if part.strip()}
    return {part if part.startswith(".") else f".{part}" for part in values}


def _iter_text_files(input_dir: Path, extensions: str) -> list[Path]:
    allowed = _resolve_extensions(extensions)
    files = [path for path in input_dir.rglob("*") if path.is_file() and path.suffix.lower() in allowed]
    files.sort()
    return files


def _clean_dir(args: argparse.Namespace, cleaner: TextCleaner) -> dict[str, Any]:
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    items: list[dict[str, Any]] = []
    for source_file in _iter_text_files(input_dir, args.extensions):
        relative = source_file.relative_to(input_dir).as_posix()
        raw_text = read_text_file(source_file, args.input_encoding)
        result = cleaner.clean(raw_text)
        output_file = output_dir / relative
        write_text_file(output_file, result["cleaned_text"], args.target_charset)
        items.append(
            {
                "item_id": relative,
                "source_path": relative,
                "input_md5": result["input_md5"],
                "output_md5": result["output_md5"],
                "changed": result["changed"],
                "edits": result["edits"],
                "summary": result["summary"],
            }
        )
    return {"items": items, "total": len(items)}


def _run_clean(args: argparse.Namespace) -> int:
    _validate_mode_args(args)
    if args.mode == "csv" and not args.output_csv:
        raise SystemExit("CSV mode requires --output-csv in clean.")
    if args.mode == "dir" and not args.output_dir:
        raise SystemExit("Directory mode requires --output-dir in clean.")
    cleaner = TextCleaner(
        CleanerConfig(
            target_charset=args.target_charset,
            spellcheck=not args.no_spellcheck,
            language=args.language,
            max_suggestion_distance=args.max_suggestion_distance,
        )
    )
    result = _clean_csv(args, cleaner) if args.mode == "csv" else _clean_dir(args, cleaner)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "tool_version": __version__,
        "created_at": utc_now_iso(),
        "mode": args.mode,
        "settings": {
            "target_charset": args.target_charset,
            "spellcheck": not args.no_spellcheck,
            "language": args.language,
            "max_suggestion_distance": args.max_suggestion_distance,
            "input_encoding": args.input_encoding,
            "text_column": args.text_column if args.mode == "csv" else None,
        },
        "items": result["items"],
    }
    write_changelog_json(Path(args.changelog_json), payload)
    write_changelog_markdown(Path(args.changelog_md), payload)
    changed_count = sum(1 for item in result["items"] if item.get("changed"))
    print(f"Processed {result['total']} items. Changed {changed_count}.")
    return 0


def _validate_csv(args: argparse.Namespace, payload: dict[str, Any]) -> int:
    rows, fieldnames = load_csv_rows(Path(args.input_csv))
    if args.text_column not in fieldnames:
        raise SystemExit(f"Column not found: {args.text_column}")
    expected = {item["row_index"]: item["input_md5"] for item in payload.get("items", [])}
    mismatches = 0
    for row_index, row in enumerate(rows, start=1):
        if row_index not in expected:
            continue
        digest = md5_text(row.get(args.text_column, "") or "")
        if digest != expected[row_index]:
            mismatches += 1
            print(f"MD5 mismatch: row:{row_index}")
    if mismatches:
        print(f"Validation failed. Mismatches: {mismatches}")
        return 1
    print("Validation passed.")
    return 0


def _validate_dir(args: argparse.Namespace, payload: dict[str, Any]) -> int:
    input_dir = Path(args.input_dir)
    expected = {item["source_path"]: item["input_md5"] for item in payload.get("items", [])}
    mismatches = 0
    for relative, expected_md5 in expected.items():
        source_file = input_dir / relative
        if not source_file.exists():
            mismatches += 1
            print(f"Missing file: {relative}")
            continue
        digest = md5_text(read_text_file(source_file, args.input_encoding))
        if digest != expected_md5:
            mismatches += 1
            print(f"MD5 mismatch: {relative}")
    if mismatches:
        print(f"Validation failed. Mismatches: {mismatches}")
        return 1
    print("Validation passed.")
    return 0


def _run_validate(args: argparse.Namespace) -> int:
    _validate_mode_args(args)
    payload = read_changelog_json(Path(args.changelog_json))
    if payload.get("mode") != args.mode:
        raise SystemExit(f"Mode mismatch. Changelog mode is {payload.get('mode')}.")
    if args.mode == "csv":
        return _validate_csv(args, payload)
    return _validate_dir(args, payload)


def _reproduce_csv(args: argparse.Namespace, payload: dict[str, Any]) -> int:
    rows, fieldnames = load_csv_rows(Path(args.input_csv))
    if args.text_column not in fieldnames:
        raise SystemExit(f"Column not found: {args.text_column}")
    if args.cleaned_column in fieldnames:
        raise SystemExit(f"Cleaned column overlaps existing CSV column: {args.cleaned_column}")
    output_fieldnames = list(fieldnames)
    output_fieldnames.append(args.cleaned_column)
    by_row = {item["row_index"]: item for item in payload.get("items", [])}
    output_rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows, start=1):
        item = by_row.get(row_index)
        raw_text = row.get(args.text_column, "") or ""
        if item is None:
            cleaned = raw_text
        else:
            digest = md5_text(raw_text)
            if args.strict_md5 and digest != item["input_md5"]:
                raise SystemExit(f"MD5 mismatch for row:{row_index}. Use --no-strict-md5 to override.")
            cleaned = apply_edits(raw_text, item.get("edits", []))
        out = dict(row)
        out[args.cleaned_column] = cleaned
        output_rows.append(out)
    write_csv_rows(Path(args.output_csv), output_rows, output_fieldnames)
    print(f"Reproduced CSV rows: {len(output_rows)}")
    return 0


def _reproduce_dir(args: argparse.Namespace, payload: dict[str, Any]) -> int:
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    processed = 0
    output_charset = payload.get("settings", {}).get("target_charset", "utf-8")
    for item in payload.get("items", []):
        relative = item["source_path"]
        source_file = input_dir / relative
        if not source_file.exists():
            raise SystemExit(f"Missing file: {relative}")
        raw_text = read_text_file(source_file, args.input_encoding)
        digest = md5_text(raw_text)
        if args.strict_md5 and digest != item["input_md5"]:
            raise SystemExit(f"MD5 mismatch for {relative}. Use --no-strict-md5 to override.")
        cleaned = apply_edits(raw_text, item.get("edits", []))
        write_text_file(output_dir / relative, cleaned, output_charset)
        processed += 1
    print(f"Reproduced files: {processed}")
    return 0


def _run_reproduce(args: argparse.Namespace) -> int:
    _validate_mode_args(args)
    payload = read_changelog_json(Path(args.changelog_json))
    if payload.get("mode") != args.mode:
        raise SystemExit(f"Mode mismatch. Changelog mode is {payload.get('mode')}.")
    if args.mode == "csv":
        if not args.output_csv:
            raise SystemExit("CSV mode requires --output-csv in reproduce.")
        return _reproduce_csv(args, payload)
    if not args.output_dir:
        raise SystemExit("Directory mode requires --output-dir in reproduce.")
    return _reproduce_dir(args, payload)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "clean":
        return _run_clean(args)
    if args.command == "validate":
        return _run_validate(args)
    if args.command == "reproduce":
        return _run_reproduce(args)
    if args.command == "gui":
        try:
            from .gui import run_gui
        except ImportError as exc:
            raise SystemExit("PySide6 is required for the GUI. Install it with: pip install PySide6") from exc
        return run_gui()
    raise SystemExit("Unknown command.")


if __name__ == "__main__":
    sys.exit(main())
