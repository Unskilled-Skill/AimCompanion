"""Load and strictly validate bundled benchmark definition snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import hashlib
import hmac
import json
import math
from pathlib import Path
import re

from core.paths import bundled_path

from .definitions import BenchmarkDefinition, DefinitionSet, normalize_alias


class DefinitionRepository:
    """Repository for versioned JSON definitions.

    The repository currently reads only the bundled directory.  A cache can be
    added behind this boundary later without changing callers.
    """

    _TOP_LEVEL_FIELDS = frozenset(
        {
            "version",
            "source_url",
            "retrieved_at",
            "sha256",
            "active",
            "required_subcategories",
            "ranks",
            "definitions",
        }
    )
    _DEFINITION_FIELDS = frozenset(
        {
            "name",
            "scenario",
            "aliases",
            "category",
            "subcategory",
            "difficulty",
            "targets",
            "energy_cap",
            "uncap_overall_energy",
        }
    )

    def __init__(self, directory: str | Path):
        self._directory = Path(directory)

    @classmethod
    def bundled(cls) -> "DefinitionRepository":
        return cls(bundled_path("data", "benchmark_definitions"))

    @staticmethod
    def canonical_sha256(definitions: object) -> str:
        """Return the checksum of a canonical JSON definitions payload."""

        canonical = json.dumps(
            definitions,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def load_active(self) -> DefinitionSet:
        active = [definition for definition in self._load_all() if definition.active]
        if len(active) != 1:
            raise ValueError("exactly one active definition set is required")
        return active[0]

    def load(self, version: str) -> DefinitionSet:
        if not isinstance(version, str) or not version.strip():
            raise ValueError("definition version must be a non-empty string")
        for definition in self._load_all():
            if definition.version == version:
                return definition
        raise KeyError(f"unknown benchmark definition version: {version}")

    def _load_all(self) -> tuple[DefinitionSet, ...]:
        definitions = tuple(self._load_path(path) for path in self._definition_paths())
        versions: set[str] = set()
        for definition in definitions:
            if definition.version in versions:
                raise ValueError(f"duplicate definition version: {definition.version}")
            versions.add(definition.version)
        return definitions

    def _definition_paths(self) -> tuple[Path, ...]:
        if not self._directory.is_dir():
            raise FileNotFoundError(f"definition directory does not exist: {self._directory}")
        paths = tuple(sorted(self._directory.glob("*.json")))
        if not paths:
            raise FileNotFoundError(f"no benchmark definition JSON files in: {self._directory}")
        return paths

    def _load_path(self, path: Path) -> DefinitionSet:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid definition JSON in {path.name}") from error
        return self._parse(raw, path.name)

    @classmethod
    def _parse(cls, raw: object, filename: str) -> DefinitionSet:
        payload = cls._mapping(raw, f"{filename} payload")
        cls._require_exact_fields(payload, cls._TOP_LEVEL_FIELDS, "definition payload")

        definitions = cls._sequence(payload["definitions"], "definitions")
        checksum = cls._string(payload["sha256"], "sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise ValueError("sha256 must be a 64-character lowercase hexadecimal checksum")
        calculated = cls.canonical_sha256(payload["definitions"])
        if not hmac.compare_digest(checksum, calculated):
            raise ValueError("definition checksum does not match definitions payload")

        required = tuple(
            cls._string(item, "required_subcategories item")
            for item in cls._sequence(payload["required_subcategories"], "required_subcategories")
        )
        if len(required) != 9:
            raise ValueError("definition set must require exactly nine subcategories")
        if len(set(required)) != len(required):
            raise ValueError("required_subcategories must not contain duplicates")

        benchmarks = tuple(cls._parse_definition(item) for item in definitions)
        cls._validate_aliases(benchmarks)
        cls._validate_subcategory_coverage(benchmarks, required)

        return DefinitionSet(
            version=cls._string(payload["version"], "version"),
            source_url=cls._https_url(payload["source_url"]),
            retrieved_at=cls._datetime(payload["retrieved_at"]),
            sha256=checksum,
            active=cls._bool(payload["active"], "active"),
            required_subcategories=required,
            ranks=cls._parse_ranks(payload["ranks"]),
            benchmarks=benchmarks,
        )

    @classmethod
    def _parse_definition(cls, raw: object) -> BenchmarkDefinition:
        definition = cls._mapping(raw, "definition")
        cls._require_exact_fields(definition, cls._DEFINITION_FIELDS, "definition")
        aliases = tuple(
            cls._string(alias, "definition alias")
            for alias in cls._sequence(definition["aliases"], "definition aliases")
        )
        energy_cap = cls._optional_positive_number(
            definition["energy_cap"], "energy_cap"
        )
        uncap_overall_energy = cls._optional_positive_number(
            definition["uncap_overall_energy"], "uncap_overall_energy"
        )
        if energy_cap is None and uncap_overall_energy is not None:
            raise ValueError("uncap_overall_energy requires energy_cap")
        return BenchmarkDefinition(
            name=cls._string(definition["name"], "definition name"),
            scenario=cls._string(definition["scenario"], "definition scenario"),
            aliases=aliases,
            category=cls._string(definition["category"], "definition category"),
            subcategory=cls._string(definition["subcategory"], "definition subcategory"),
            difficulty=cls._string(definition["difficulty"], "definition difficulty"),
            targets=cls._parse_targets(definition["targets"]),
            energy_cap=energy_cap,
            uncap_overall_energy=uncap_overall_energy,
        )

    @classmethod
    def _parse_targets(cls, raw: object) -> tuple[tuple[float, float], ...]:
        points = tuple(cls._number_pair(item, "target") for item in cls._sequence(raw, "targets"))
        if not points:
            raise ValueError("targets must not be empty")
        for previous, current in zip(points, points[1:]):
            if current[0] <= previous[0] or current[1] <= previous[1]:
                raise ValueError("target points must be strictly increasing")
        return points

    @classmethod
    def _parse_ranks(cls, raw: object) -> tuple[tuple[str, float], ...]:
        ranks = tuple(cls._rank_pair(item) for item in cls._sequence(raw, "ranks"))
        if not ranks:
            raise ValueError("ranks must not be empty")
        names = [name for name, _ in ranks]
        if len(set(names)) != len(names):
            raise ValueError("rank names must be unique")
        for previous, current in zip(ranks, ranks[1:]):
            if current[1] <= previous[1]:
                raise ValueError("rank thresholds must be strictly increasing")
        return ranks

    @classmethod
    def _validate_aliases(cls, benchmarks: Sequence[BenchmarkDefinition]) -> None:
        owners: dict[str, str] = {}
        for benchmark in benchmarks:
            # Name and scenario are implicit aliases. They may be identical,
            # as they are in the bundled S5 source data.
            cls._claim_alias(owners, benchmark.name, benchmark.name, allow_same_owner=False)
            cls._claim_alias(owners, benchmark.scenario, benchmark.name, allow_same_owner=True)
            seen_explicit: set[str] = set()
            for alias in benchmark.aliases:
                normalized = normalize_alias(alias)
                if normalized in seen_explicit:
                    raise ValueError(f"duplicate normalized alias: {alias}")
                seen_explicit.add(normalized)
                cls._claim_alias(owners, alias, benchmark.name, allow_same_owner=True)

    @staticmethod
    def _validate_subcategory_coverage(
        benchmarks: Sequence[BenchmarkDefinition], required: Sequence[str]
    ) -> None:
        required_set = set(required)
        covered = {f"{item.category} / {item.subcategory}" for item in benchmarks}
        missing = sorted(required_set - covered)
        if missing:
            raise ValueError(f"required subcategories lack benchmark coverage: {missing}")
        unexpected = sorted(covered - required_set)
        if unexpected:
            raise ValueError(f"benchmark subcategory not in required subcategories: {unexpected}")
        for difficulty in sorted({item.difficulty for item in benchmarks}):
            difficulty_coverage = {
                f"{item.category} / {item.subcategory}"
                for item in benchmarks
                if item.difficulty == difficulty
            }
            missing = sorted(required_set - difficulty_coverage)
            if missing:
                raise ValueError(
                    f"{difficulty} definitions lack required subcategory coverage: {missing}"
                )

    @staticmethod
    def _claim_alias(
        owners: dict[str, str], alias: str, benchmark_name: str, *, allow_same_owner: bool
    ) -> None:
        normalized = normalize_alias(alias)
        if not normalized:
            raise ValueError("definition aliases must not normalize to an empty value")
        owner = owners.get(normalized)
        if owner is not None and (not allow_same_owner or owner != benchmark_name):
            raise ValueError(f"duplicate normalized alias: {alias}")
        owners[normalized] = benchmark_name

    @staticmethod
    def _mapping(raw: object, description: str) -> Mapping[str, object]:
        if not isinstance(raw, Mapping):
            raise ValueError(f"{description} must be an object")
        return raw

    @staticmethod
    def _require_exact_fields(
        payload: Mapping[str, object], expected: frozenset[str], description: str
    ) -> None:
        actual = set(payload)
        if actual != expected:
            missing = sorted(expected - actual)
            unknown = sorted(actual - expected)
            raise ValueError(f"{description} fields are invalid (missing={missing}, unknown={unknown})")

    @staticmethod
    def _sequence(raw: object, description: str) -> Sequence[object]:
        if not isinstance(raw, list):
            raise ValueError(f"{description} must be an array")
        return raw

    @staticmethod
    def _string(raw: object, description: str) -> str:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"{description} must be a non-empty string")
        return raw

    @staticmethod
    def _bool(raw: object, description: str) -> bool:
        if not isinstance(raw, bool):
            raise ValueError(f"{description} must be a boolean")
        return raw

    @classmethod
    def _number_pair(cls, raw: object, description: str) -> tuple[float, float]:
        if not isinstance(raw, list) or len(raw) != 2:
            raise ValueError(f"{description} must contain exactly two numbers")
        return (
            cls._positive_number(raw[0], f"{description} score"),
            cls._positive_number(raw[1], f"{description} energy"),
        )

    @classmethod
    def _rank_pair(cls, raw: object) -> tuple[str, float]:
        if not isinstance(raw, list) or len(raw) != 2:
            raise ValueError("rank must contain a name and threshold")
        return cls._string(raw[0], "rank name"), cls._positive_number(raw[1], "rank threshold")

    @staticmethod
    def _positive_number(raw: object, description: str) -> float:
        if (
            isinstance(raw, bool)
            or not isinstance(raw, int | float)
            or not math.isfinite(raw)
            or raw <= 0
        ):
            raise ValueError(f"{description} must be a positive finite number")
        return float(raw)

    @classmethod
    def _optional_positive_number(cls, raw: object, description: str) -> float | None:
        return None if raw is None else cls._positive_number(raw, description)

    @classmethod
    def _datetime(cls, raw: object) -> datetime:
        value = cls._string(raw, "retrieved_at")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("retrieved_at must be an ISO-8601 timestamp") from error
        if parsed.tzinfo is None:
            raise ValueError("retrieved_at must include a timezone")
        return parsed

    @classmethod
    def _https_url(cls, raw: object) -> str:
        value = cls._string(raw, "source_url")
        if not value.startswith("https://"):
            raise ValueError("source_url must use https")
        return value
