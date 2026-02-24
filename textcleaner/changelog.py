from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_changelog_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_changelog_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_changelog_markdown(path: Path, payload: dict[str, Any]) -> None:
    items = payload.get("items", [])
    changed = [item for item in items if item.get("changed")]
    unchanged = len(items) - len(changed)
    lines: list[str] = []
    lines.append("# TextCleaner Run Summary")
    lines.append("")
    lines.append(f"- Created at: `{payload.get('created_at')}`")
    lines.append(f"- Mode: `{payload.get('mode')}`")
    lines.append(f"- Total items: `{len(items)}`")
    lines.append(f"- Changed items: `{len(changed)}`")
    lines.append(f"- Unchanged items: `{unchanged}`")
    lines.append("")
    lines.append("## Changed Items")
    lines.append("")
    if not changed:
        lines.append("_No textual changes were made._")
    else:
        lines.append("| Item | Edit Count | Top Replacements |")
        lines.append("|---|---:|---|")
        for item in changed:
            summary = item.get("summary", {})
            replacements = summary.get("top_replacements", [])
            rep_text = ", ".join(f"{r['from']} -> {r['to']} (x{r['count']})" for r in replacements) or "-"
            lines.append(f"| `{item.get('item_id')}` | {summary.get('edit_count', 0)} | {rep_text} |")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

