#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared genre taxonomy resolver.

The taxonomy intentionally separates two namespaces:

- canonical_genre: stable 15-value enum for CSV filtering and Story System.
- template_files: init-only preset templates under templates/genres/.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional


GENRE_CANONICAL: set[str] = {
    "都市", "玄幻", "仙侠", "奇幻", "科幻",
    "历史", "悬疑", "游戏", "古言", "现言",
    "幻言", "年代", "种田", "快穿", "衍生",
}

_INPUT_SPLIT_RE = re.compile(r"[+＋/、,，|]+|与")
_VALUE_SPLIT_RE = re.compile(r"[;；|]+")
_HIGH_PRIORITY_TYPES = {"route", "platform", "canonical", "preset", "legacy"}
_TYPE_PRIORITY = {
    "route": 0,
    "platform": 1,
    "canonical": 2,
    "preset": 3,
    "legacy": 4,
    "format": 5,
    "trope": 6,
}


@dataclass(frozen=True)
class GenreEntry:
    label: str
    canonical_genre: str
    label_type: str
    template_file: str = ""
    route_tags: tuple[str, ...] = ()
    trope_tags: tuple[str, ...] = ()
    format_tags: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    notes: str = ""

    @property
    def lookup_labels(self) -> tuple[str, ...]:
        return (self.label, *self.aliases)


@dataclass
class GenreResolution:
    raw_label: str
    canonical_genre: str = ""
    canonical_genres: list[str] = field(default_factory=list)
    matched_labels: list[str] = field(default_factory=list)
    template_files: list[str] = field(default_factory=list)
    route_tags: list[str] = field(default_factory=list)
    trope_tags: list[str] = field(default_factory=list)
    format_tags: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GenreTaxonomy:
    entries: tuple[GenreEntry, ...]
    lookup: dict[str, GenreEntry]


def default_taxonomy_path() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "taxonomy" / "genre-index.csv"


def _split_list(value: object) -> tuple[str, ...]:
    text = str(value or "").strip()
    if not text:
        return ()
    return tuple(part.strip() for part in _VALUE_SPLIT_RE.split(text) if part.strip())


def _normalize_lookup_key(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return re.sub(r"\s+", "", text)


def _read_taxonomy(path: Path) -> tuple[GenreEntry, ...]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    entries: list[GenreEntry] = []
    for line_no, row in enumerate(rows, start=2):
        label = str(row.get("label") or "").strip()
        canonical = str(row.get("canonical_genre") or "").strip()
        if not label:
            raise ValueError(f"{path}: line {line_no} missing label")
        if canonical not in GENRE_CANONICAL and canonical != "全部":
            raise ValueError(f"{path}: line {line_no} invalid canonical_genre {canonical!r}")
        entries.append(
            GenreEntry(
                label=label,
                canonical_genre=canonical,
                label_type=str(row.get("label_type") or "").strip(),
                template_file=str(row.get("template_file") or "").strip(),
                route_tags=_split_list(row.get("route_tags")),
                trope_tags=_split_list(row.get("trope_tags")),
                format_tags=_split_list(row.get("format_tags")),
                aliases=_split_list(row.get("aliases")),
                notes=str(row.get("notes") or "").strip(),
            )
        )
    return tuple(entries)


def _build_lookup(entries: Iterable[GenreEntry]) -> dict[str, GenreEntry]:
    lookup: dict[str, GenreEntry] = {}
    for entry in entries:
        seen_for_entry: set[str] = set()
        for label in entry.lookup_labels:
            key = _normalize_lookup_key(label)
            if not key or key in seen_for_entry:
                continue
            seen_for_entry.add(key)
            existing = lookup.get(key)
            if existing is not None and existing != entry:
                raise ValueError(
                    f"genre taxonomy duplicate label/alias {label!r}: "
                    f"{existing.label!r} vs {entry.label!r}"
                )
            lookup[key] = entry
    return lookup


@lru_cache(maxsize=8)
def load_genre_taxonomy(index_path: Optional[str] = None) -> GenreTaxonomy:
    path = Path(index_path) if index_path else default_taxonomy_path()
    entries = _read_taxonomy(path)
    return GenreTaxonomy(entries=entries, lookup=_build_lookup(entries))


def split_genre_input(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    tokens = [part.strip() for part in _INPUT_SPLIT_RE.split(text) if part.strip()]
    return tokens or [text]


def _append_unique(values: list[str], additions: Iterable[str]) -> None:
    seen = set(values)
    for value in additions:
        if value and value not in seen:
            seen.add(value)
            values.append(value)


def _choose_canonical(entries: list[GenreEntry], warnings: list[str]) -> str:
    if not entries:
        return ""
    high = [entry for entry in entries if entry.label_type in _HIGH_PRIORITY_TYPES]
    candidates = high or entries
    candidates = sorted(candidates, key=lambda entry: _TYPE_PRIORITY.get(entry.label_type, 99))
    canonical = candidates[0].canonical_genre
    high_canonicals = {entry.canonical_genre for entry in high if entry.canonical_genre != canonical}
    if high_canonicals:
        warnings.append("ambiguous_canonical")
    return canonical


def resolve_genre_input(raw_label: Optional[str], *, index_path: Optional[str] = None) -> GenreResolution:
    raw = str(raw_label or "").strip()
    resolution = GenreResolution(raw_label=raw)
    if not raw:
        return resolution
    if raw == "全部":
        resolution.canonical_genre = "全部"
        resolution.matched_labels.append("全部")
        return resolution

    taxonomy = load_genre_taxonomy(index_path)
    matched: list[GenreEntry] = []
    matched_entry_ids: set[tuple[str, str, str]] = set()

    def add_match(entry: GenreEntry, matched_label: str) -> None:
        identity = (entry.label, entry.canonical_genre, entry.template_file)
        if identity in matched_entry_ids:
            return
        matched_entry_ids.add(identity)
        matched.append(entry)
        resolution.matched_labels.append(matched_label)

    raw_key = _normalize_lookup_key(raw)
    exact = taxonomy.lookup.get(raw_key)
    if exact is not None:
        add_match(exact, raw)
    else:
        unresolved_tokens: list[str] = []
        for token in split_genre_input(raw):
            token_key = _normalize_lookup_key(token)
            entry = taxonomy.lookup.get(token_key)
            if entry is None:
                unresolved_tokens.append(token)
                continue
            add_match(entry, token)

        if not matched:
            lookup_items = sorted(taxonomy.lookup.items(), key=lambda item: len(item[0]), reverse=True)
            consumed: set[str] = set()
            for key, entry in lookup_items:
                if len(key) < 2 or key in consumed:
                    continue
                if key in raw_key:
                    add_match(entry, entry.label)
                    consumed.add(key)
        if not matched:
            resolution.unresolved = unresolved_tokens or [raw]

    resolution.canonical_genre = _choose_canonical(matched, resolution.warnings)
    for entry in matched:
        canon = entry.canonical_genre
        if canon and canon != "全部" and canon not in resolution.canonical_genres:
            resolution.canonical_genres.append(canon)
    for entry in matched:
        _append_unique(resolution.route_tags, entry.route_tags)
        _append_unique(resolution.trope_tags, entry.trope_tags)
        _append_unique(resolution.format_tags, entry.format_tags)
        if entry.template_file:
            _append_unique(resolution.template_files, [entry.template_file])
    return resolution


def seed_genre_label(raw: str) -> str:
    resolved = resolve_genre_input(raw)
    if resolved.canonical_genres:
        return "+".join(resolved.canonical_genres)
    return str(raw or "").strip()


def resolve_canonical_genre(genre: Optional[str], *, index_path: Optional[str] = None) -> Optional[str]:
    if genre is None:
        return None
    raw = str(genre).strip()
    if not raw:
        return raw
    resolved = resolve_genre_input(raw, index_path=index_path)
    return resolved.canonical_genre or raw


def resolve_template_files(genre: Optional[str], *, index_path: Optional[str] = None) -> list[str]:
    return resolve_genre_input(genre, index_path=index_path).template_files


def resolve_template_stems(genre: Optional[str], *, index_path: Optional[str] = None) -> list[str]:
    stems: list[str] = []
    for template_file in resolve_template_files(genre, index_path=index_path):
        stem = Path(template_file).stem
        if stem and stem not in stems:
            stems.append(stem)
    return stems


def normalize_genre_label_for_profile(genre: str, *, index_path: Optional[str] = None) -> str:
    raw = str(genre or "").strip()
    if not raw:
        return ""
    resolved = resolve_genre_input(raw, index_path=index_path)
    if resolved.template_files:
        return Path(resolved.template_files[0]).stem
    if resolved.matched_labels:
        return resolved.matched_labels[0]
    return raw
