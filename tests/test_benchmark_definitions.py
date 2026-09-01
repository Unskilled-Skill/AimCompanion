import json

import pytest

from core.benchmarks.repository import DefinitionRepository


def write_definition(
    directory,
    *,
    subcategories=None,
    definitions=None,
    sha256=None,
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
        "version": "test",
        "source_url": "https://app.voltaic.gg/benchmarks",
        "retrieved_at": "2026-08-30T00:00:00+02:00",
        "active": True,
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
    path = directory / "test.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


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
