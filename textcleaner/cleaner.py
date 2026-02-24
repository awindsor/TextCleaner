from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from hashlib import md5
from typing import Any


WORD_RE = re.compile(r"[A-Za-z][A-Za-z']+")


def md5_text(text: str) -> str:
    return md5(text.encode("utf-8")).hexdigest()


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = prev[j] + 1
            subst_cost = prev[j - 1] + (char_a != char_b)
            current.append(min(insert_cost, delete_cost, subst_cost))
        prev = current
    return prev[-1]


def _match_case(source: str, suggestion: str) -> str:
    if source.isupper():
        return suggestion.upper()
    if source.istitle():
        return suggestion.capitalize()
    return suggestion.lower() if source.islower() else suggestion


def normalize_charset(text: str, target_charset: str) -> str:
    normalized = unicodedata.normalize("NFKC", text.replace("\r\n", "\n").replace("\r", "\n"))
    normalized = "".join(ch for ch in normalized if ch == "\n" or ch == "\t" or unicodedata.category(ch)[0] != "C")
    if target_charset == "utf-8":
        return normalized
    if target_charset in {"latin-1", "ascii"}:
        codec = "latin-1" if target_charset == "latin-1" else "ascii"
        return normalized.encode(codec, errors="ignore").decode(codec)
    raise ValueError(f"Unsupported target charset: {target_charset}")


def build_edits(original: str, cleaned: str) -> list[dict[str, Any]]:
    matcher = SequenceMatcher(a=original, b=cleaned, autojunk=False)
    edits: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        edits.append(
            {
                "start": i1,
                "end": i2,
                "replacement": cleaned[j1:j2],
            }
        )
    return edits


def apply_edits(original: str, edits: list[dict[str, Any]]) -> str:
    result: list[str] = []
    cursor = 0
    for edit in edits:
        start = int(edit["start"])
        end = int(edit["end"])
        replacement = str(edit["replacement"])
        if start < cursor:
            raise ValueError("Edits overlap or are out of order.")
        result.append(original[cursor:start])
        result.append(replacement)
        cursor = end
    result.append(original[cursor:])
    return "".join(result)


@dataclass
class CleanerConfig:
    target_charset: str = "utf-8"
    spellcheck: bool = True
    language: str = "en_US"
    max_suggestion_distance: int = 2


class TextCleaner:
    def __init__(self, config: CleanerConfig):
        self.config = config
        self._dictionary = None
        if config.spellcheck:
            try:
                import enchant  # type: ignore
            except Exception as exc:  # pragma: no cover - depends on local env
                raise RuntimeError(
                    "Spellcheck is enabled, but pyenchant is unavailable. "
                    "Install pyenchant (and Enchant system libs), or pass --no-spellcheck."
                ) from exc
            self._dictionary = enchant.Dict(config.language)

    def clean(self, raw_text: str) -> dict[str, Any]:
        normalized = normalize_charset(raw_text, self.config.target_charset)
        cleaned = normalized
        replacement_counter: Counter[tuple[str, str]] = Counter()

        if self.config.spellcheck and self._dictionary is not None:
            pieces: list[str] = []
            cursor = 0
            for match in WORD_RE.finditer(normalized):
                start, end = match.span()
                token = match.group(0)
                replacement = token
                if not self._dictionary.check(token):
                    suggestions = self._dictionary.suggest(token)
                    if suggestions:
                        candidate = suggestions[0]
                        candidate = _match_case(token, candidate)
                        distance = _edit_distance(token.lower(), candidate.lower())
                        if distance <= self.config.max_suggestion_distance:
                            replacement = candidate
                pieces.append(normalized[cursor:start])
                pieces.append(replacement)
                cursor = end
                if replacement != token:
                    replacement_counter[(token, replacement)] += 1
            pieces.append(normalized[cursor:])
            cleaned = "".join(pieces)

        edits = build_edits(raw_text, cleaned)
        top_replacements = [
            {"from": source, "to": target, "count": count}
            for (source, target), count in replacement_counter.most_common(8)
        ]
        return {
            "cleaned_text": cleaned,
            "edits": edits,
            "input_md5": md5_text(raw_text),
            "output_md5": md5_text(cleaned),
            "changed": raw_text != cleaned,
            "summary": {
                "edit_count": len(edits),
                "top_replacements": top_replacements,
            },
        }

