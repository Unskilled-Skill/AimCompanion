import json
from pathlib import Path

import pytest

from core.benchmarks.repository import DefinitionRepository


def write_definition(
    directory,
    *,
    subcategories=None,
    definitions=None,
    sha256=None,
    filename="test.json",
    version="test",
    active=True,
):
    definitions = definitions or [
        {
            "name": "VT Example Novice S5",
            "scenario": "VT Example Novice S5",
            "aliases": ["VT Example Novice S5"],
            "category": "Clicking",
            "subcategory": "Static",
            "difficulty": "Novice",
            "targets": [[100, 100], [200, 200]],
            "energy_cap": 1200,
            "uncap_overall_energy": 1200,
        }
    ]
    payload = {
        "version": version,
        "source_url": "https://app.voltaic.gg/benchmarks",
        "retrieved_at": "2026-08-30T00:00:00+02:00",
        "active": active,
        "required_subcategories": subcategories
        or [
            "Clicking / Static",
            "Clicking / Dynamic",
            "Clicking / Linear",
            "Tracking / Precise",
            "Tracking / Reactive",
            "Tracking / Control",
            "Switching / Speed",
            "Switching / Evasive",
            "Switching / Stability",
        ],
        "ranks": [["Iron", 100], ["Bronze", 200]],
        "definitions": definitions,
    }
    payload["sha256"] = sha256 or DefinitionRepository.canonical_sha256(definitions)
    path = directory / filename
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def complete_definitions(difficulty="Novice"):
    required = [
        "Clicking / Static",
        "Clicking / Dynamic",
        "Clicking / Linear",
        "Tracking / Precise",
        "Tracking / Reactive",
        "Tracking / Control",
        "Switching / Speed",
        "Switching / Evasive",
        "Switching / Stability",
    ]
    return [
        {
            "name": f"{difficulty} {subcategory} Example",
            "scenario": f"{difficulty} {subcategory} Scenario",
            "aliases": [],
            "category": subcategory.split(" / ")[0],
            "subcategory": subcategory.split(" / ")[1],
            "difficulty": difficulty,
            "targets": [[100, 100], [200, 200]],
            "energy_cap": None,
            "uncap_overall_energy": None,
        }
        for subcategory in required
    ]


def test_definition_set_requires_nine_subcategories(tmp_path):
    path = write_definition(tmp_path, subcategories=["Clicking / Static"])

    with pytest.raises(ValueError, match="exactly nine"):
        DefinitionRepository(path.parent).load("test")


def test_active_definition_has_verifiable_provenance():
    definitions = DefinitionRepository.bundled().load_active()

    assert definitions.version == "kovaaks_s5"
    assert definitions.source_url.startswith("https://app.voltaic.gg/")
    assert len(definitions.sha256) == 64
    assert len(definitions.required_subcategories) == 9


def test_bundled_cap_policy_only_conditionally_caps_advanced():
    definitions = DefinitionRepository.bundled().load_active()

    policies = {
        difficulty: {
            (definition.energy_cap, definition.uncap_overall_energy)
            for definition in definitions.benchmarks
            if definition.difficulty == difficulty
        }
        for difficulty in ("Novice", "Intermediate", "Advanced")
    }

    assert policies == {
        "Novice": {(None, None)},
        "Intermediate": {(None, None)},
        "Advanced": {(1200.0, 1200.0)},
    }


def test_definition_rejects_a_tampered_definitions_payload(tmp_path):
    path = write_definition(tmp_path, sha256="0" * 64)

    with pytest.raises(ValueError, match="checksum"):
        DefinitionRepository(path.parent).load("test")


def test_definition_rejects_duplicate_normalized_aliases(tmp_path):
    definitions = [
        {
            "name": "First",
            "scenario": "First Scenario",
            "aliases": ["Shared Alias"],
            "category": "Clicking",
            "subcategory": "Static",
            "difficulty": "Novice",
            "targets": [[100, 100], [200, 200]],
            "energy_cap": 1200,
            "uncap_overall_energy": 1200,
        },
        {
            "name": "Second",
            "scenario": "Second Scenario",
            "aliases": [" shared-alias "],
            "category": "Clicking",
            "subcategory": "Dynamic",
            "difficulty": "Novice",
            "targets": [[100, 100], [200, 200]],
            "energy_cap": 1200,
            "uncap_overall_energy": 1200,
        },
    ]
    path = write_definition(tmp_path, definitions=definitions)

    with pytest.raises(ValueError, match="duplicate normalized alias"):
        DefinitionRepository(path.parent).load("test")


def test_definition_rejects_duplicate_normalized_aliases_within_one_definition(tmp_path):
    definitions = [
        {
            "name": "First",
            "scenario": "First Scenario",
            "aliases": ["Shared Alias", " shared-alias "],
            "category": "Clicking",
            "subcategory": "Static",
            "difficulty": "Novice",
            "targets": [[100, 100], [200, 200]],
            "energy_cap": 1200,
            "uncap_overall_energy": 1200,
        }
    ]
    path = write_definition(tmp_path, definitions=definitions)

    with pytest.raises(ValueError, match="duplicate normalized alias"):
        DefinitionRepository(path.parent).load("test")


def test_definition_rejects_duplicate_canonical_names(tmp_path):
    definitions = [
        {
            "name": "Same Name",
            "scenario": "First Scenario",
            "aliases": [],
            "category": "Clicking",
            "subcategory": "Static",
            "difficulty": "Novice",
            "targets": [[100, 100], [200, 200]],
            "energy_cap": 1200,
            "uncap_overall_energy": 1200,
        },
        {
            "name": "Same Name",
            "scenario": "Second Scenario",
            "aliases": [],
            "category": "Clicking",
            "subcategory": "Dynamic",
            "difficulty": "Novice",
            "targets": [[100, 100], [200, 200]],
            "energy_cap": 1200,
            "uncap_overall_energy": 1200,
        },
    ]
    path = write_definition(tmp_path, definitions=definitions)

    with pytest.raises(ValueError, match="duplicate normalized alias"):
        DefinitionRepository(path.parent).load("test")


def test_definition_rejects_missing_required_subcategory_coverage(tmp_path):
    path = write_definition(tmp_path)

    with pytest.raises(ValueError, match="required subcategor"):
        DefinitionRepository(path.parent).load("test")


def test_definition_rejects_benchmark_outside_required_subcategories(tmp_path):
    required = [
        "Clicking / Static",
        "Clicking / Dynamic",
        "Clicking / Linear",
        "Tracking / Precise",
        "Tracking / Reactive",
        "Tracking / Control",
        "Switching / Speed",
        "Switching / Evasive",
        "Switching / Stability",
    ]
    definitions = [
        {
            "name": f"{subcategory} Example",
            "scenario": f"{subcategory} Example Scenario",
            "aliases": [],
            "category": subcategory.split(" / ")[0],
            "subcategory": subcategory.split(" / ")[1],
            "difficulty": "Novice",
            "targets": [[100, 100], [200, 200]],
            "energy_cap": 1200,
            "uncap_overall_energy": 1200,
        }
        for subcategory in required
    ]
    definitions.append(
        {
            "name": "Unlisted Example",
            "scenario": "Unlisted Example Scenario",
            "aliases": [],
            "category": "Clicking",
            "subcategory": "Unlisted",
            "difficulty": "Novice",
            "targets": [[100, 100], [200, 200]],
            "energy_cap": 1200,
            "uncap_overall_energy": 1200,
        }
    )
    path = write_definition(tmp_path, definitions=definitions)

    with pytest.raises(ValueError, match="not in required subcategor"):
        DefinitionRepository(path.parent).load("test")


def test_definition_requires_subcategory_coverage_for_each_declared_difficulty(tmp_path):
    definitions = complete_definitions("Novice")
    definitions.append(
        {
            **definitions[0],
            "name": "Intermediate Clicking Static Example",
            "scenario": "Intermediate Clicking Static Scenario",
            "difficulty": "Intermediate",
        }
    )
    path = write_definition(tmp_path, definitions=definitions)

    with pytest.raises(ValueError, match="Intermediate.*required subcategor"):
        DefinitionRepository(path.parent).load("test")


def test_repository_rejects_duplicate_versions_across_custom_files(tmp_path):
    definitions = complete_definitions()
    write_definition(
        tmp_path,
        definitions=definitions,
        filename="first.json",
        version="duplicate",
        active=False,
    )
    write_definition(
        tmp_path,
        definitions=definitions,
        filename="second.json",
        version="duplicate",
        active=True,
    )

    with pytest.raises(ValueError, match="duplicate definition version"):
        DefinitionRepository(tmp_path).load("duplicate")


def test_custom_repository_loads_a_complete_definition_set(tmp_path):
    path = write_definition(tmp_path, definitions=complete_definitions())

    loaded = DefinitionRepository(path.parent).load("test")

    assert loaded.version == "test"
    assert len(loaded.benchmarks) == 9
    assert loaded.benchmarks[0].energy_cap is None


def test_definition_rejects_uncap_threshold_without_an_energy_cap(tmp_path):
    definitions = complete_definitions()
    definitions[0]["uncap_overall_energy"] = 1200
    path = write_definition(tmp_path, definitions=definitions)

    with pytest.raises(ValueError, match="uncap_overall_energy requires energy_cap"):
        DefinitionRepository(path.parent).load("test")


def test_redundant_explicit_alias_is_harmless_for_its_own_definition(tmp_path):
    definitions = complete_definitions()
    definitions[0]["aliases"] = [definitions[0]["name"]]
    path = write_definition(tmp_path, definitions=definitions)

    loaded = DefinitionRepository(path.parent).load("test")

    assert loaded.benchmarks[0].aliases == (definitions[0]["name"],)


def test_bundled_snapshot_preserves_the_complete_legacy_target_conversion():
    root = Path(__file__).parents[1]
    legacy_benchmarks = json.loads((root / "data" / "benchmarks.json").read_text())
    legacy_tiers = json.loads((root / "data" / "tiers.json").read_text())
    rank_energy = {item["name"]: float(item["min_energy"]) for item in legacy_tiers}
    loaded = DefinitionRepository.bundled().load_active()

    expected = {
        item["name"]: (
            item["scenario"],
            item["category"],
            item["subcategory"],
            item["difficulty"],
            tuple(
                (float(score), rank_energy[tier])
                for tier, score in item["targets"].items()
            ),
        )
        for item in legacy_benchmarks
    }
    actual = {
        item.name: (
            item.scenario,
            item.category,
            item.subcategory,
            item.difficulty,
            item.targets,
        )
        for item in loaded.benchmarks
    }

    assert loaded.ranks == tuple(
        (item["name"], float(item["min_energy"])) for item in legacy_tiers
    )
    assert actual == expected


def test_definition_rejects_non_increasing_target_points(tmp_path):
    definitions = [
        {
            "name": "VT Example Novice S5",
            "scenario": "VT Example Novice S5",
            "aliases": ["VT Example Novice S5"],
            "category": "Clicking",
            "subcategory": "Static",
            "difficulty": "Novice",
            "targets": [[100, 100], [200, 100]],
            "energy_cap": 1200,
            "uncap_overall_energy": 1200,
        }
    ]
    path = write_definition(tmp_path, definitions=definitions)

    with pytest.raises(ValueError, match="strictly increasing"):
        DefinitionRepository(path.parent).load("test")


def test_definition_rejects_non_finite_target_points(tmp_path):
    definitions = [
        {
            "name": "VT Example Novice S5",
            "scenario": "VT Example Novice S5",
            "aliases": [],
            "category": "Clicking",
            "subcategory": "Static",
            "difficulty": "Novice",
            "targets": [[100, float("nan")], [200, 200]],
            "energy_cap": 1200,
            "uncap_overall_energy": 1200,
        }
    ]
    path = write_definition(tmp_path, definitions=definitions)

    with pytest.raises(ValueError, match="finite"):
        DefinitionRepository(path.parent).load("test")
