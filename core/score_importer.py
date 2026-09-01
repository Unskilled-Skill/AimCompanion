"""Deterministic, UI-free score import batches."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass

from core.parser import parse_csv_file
from models.database import Database
from models.score import Score


@dataclass(frozen=True)
class ImportBatchResult:
    imported: int
    duplicates: int
    failed: int
    paths: tuple[str, ...]


class ScoreImporter:
    """Import explicit CSV paths while retaining durable import bookkeeping."""

    def __init__(self, db: Database):
        self.db = db

    def import_paths(
        self, paths: Iterable[str | os.PathLike[str]],
    ) -> ImportBatchResult:
        candidates = self._ordered_paths(paths)
        imported_paths = {
            self._path_key(path)
            for path in self.db.get_imported_score_paths()
        }
        parsed: list[tuple[str, str, Score]] = []
        failed = 0

        for path in candidates:
            path_key = self._path_key(path)
            if path_key in imported_paths:
                continue
            try:
                score = parse_csv_file(path)
            except Exception as error:
                self.db.record_import_error(path_key, self._format_error(error))
                failed += 1
                continue
            if score is None:
                self.db.record_import_error(
                    path_key, "Malformed or unsupported CSV result",
                )
                failed += 1
                continue
            parsed.append((path, path_key, score))

        imported = 0
        duplicates = 0
        if parsed:
            with self.db.conn:
                for path, path_key, score in parsed:
                    if self.db.score_record_exists(score):
                        self.db.mark_score_path_imported(path_key, commit=False)
                        duplicates += 1
                    else:
                        self.db.insert_score(score, path_key, commit=False)
                        imported += 1
                    self.db.clear_import_error(path_key, commit=False)

        return ImportBatchResult(
            imported=imported,
            duplicates=duplicates,
            failed=failed,
            paths=tuple(candidates),
        )

    @classmethod
    def _ordered_paths(
        cls, paths: Iterable[str | os.PathLike[str]],
    ) -> list[str]:
        by_key: dict[str, str] = {}
        for supplied_path in paths:
            path = os.path.normpath(os.path.abspath(os.fspath(supplied_path)))
            key = cls._path_key(path)
            previous = by_key.get(key)
            if previous is None or path < previous:
                by_key[key] = path
        return [by_key[key] for key in sorted(by_key)]

    @staticmethod
    def _path_key(path: str) -> str:
        return os.path.normcase(os.path.normpath(os.path.abspath(path)))

    @staticmethod
    def _format_error(error: Exception) -> str:
        return f"{type(error).__name__}: {error}"
