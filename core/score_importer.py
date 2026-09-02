"""Deterministic, UI-free score import batches."""

from __future__ import annotations

import hashlib
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
    updated: int = 0
    failed_paths: tuple[str, ...] = ()

    def failure_summary(self) -> str:
        if not self.failed:
            return ""
        affected = ", ".join(os.path.basename(path) for path in self.failed_paths[:3])
        if len(self.failed_paths) > 3:
            affected += f", and {len(self.failed_paths) - 3} more"
        noun = "file" if self.failed == 1 else "files"
        detail = f": {affected}" if affected else ""
        return (
            f"{self.failed} {noun} failed{detail}. Fix the file or wait for it to "
            "finish writing; the next scan will retry it, or use Import scores."
        )


class ScoreImporter:
    """Import explicit CSV paths while retaining durable import bookkeeping."""

    def __init__(self, db: Database):
        self.db = db

    def import_paths(
        self, paths: Iterable[str | os.PathLike[str]],
    ) -> ImportBatchResult:
        candidates = self._ordered_paths(paths)
        imported_files = {
            self._path_key(path): content_sha256
            for path, content_sha256 in self.db.get_imported_score_files().items()
        }
        parsed: list[tuple[str, str, Score]] = []
        failed = 0
        failed_paths = []

        for path in candidates:
            path_key = self._path_key(path)
            try:
                content_sha256 = self._content_sha256(path)
                if imported_files.get(path_key) == content_sha256:
                    continue
                score = parse_csv_file(path)
            except Exception as error:
                self.db.record_import_error(path_key, self._format_error(error))
                failed += 1
                failed_paths.append(path)
                continue
            if score is None:
                self.db.record_import_error(
                    path_key, "Malformed or unsupported CSV result",
                )
                failed += 1
                failed_paths.append(path)
                continue
            parsed.append((path_key, content_sha256, score))

        imported = 0
        updated = 0
        duplicates = 0
        if parsed:
            with self.db.conn:
                for path_key, content_sha256, score in parsed:
                    owns_score = self.db.score_exists(path_key)
                    if self.db.score_record_exists(
                        score, exclude_csv_path=path_key,
                    ):
                        if owns_score:
                            self.db.delete_score_for_path(path_key, commit=False)
                        self.db.mark_score_path_imported(
                            path_key, content_sha256, commit=False
                        )
                        duplicates += 1
                    else:
                        self.db.insert_score(
                            score,
                            path_key,
                            content_sha256=content_sha256,
                            commit=False,
                        )
                        if owns_score:
                            updated += 1
                        else:
                            imported += 1
                    self.db.clear_import_error(path_key, commit=False)

        return ImportBatchResult(
            imported=imported,
            duplicates=duplicates,
            failed=failed,
            paths=tuple(candidates),
            updated=updated,
            failed_paths=tuple(failed_paths),
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
    def _content_sha256(path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as score_file:
            for chunk in iter(lambda: score_file.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _format_error(error: Exception) -> str:
        return f"{type(error).__name__}: {error}"
