"""Synchronize factual routine/scenario data from the official Voltaic resources.

This refreshes titles, scenario names, durations, eligibility, and share codes.
The concise, paraphrased offline technique companion in
``data/voltaic_guidance.json`` is intentionally preserved by every sync; the
documents' full instructional prose remains at the linked sources.
"""

from __future__ import annotations

import io
import json
import re
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

SOURCES = {
    "game": {
        "title": "Voltaic Game-specific Kovaak's Aim Routines",
        "short_url": "https://bit.ly/gameroutines",
        "document_id": "1TpFHOg6WbPS2iFie2z53AnyQTXQ_ZBg7lKNqjvWhXIE",
    },
    "issue": {
        "title": "Voltaic Issue-specific Aim Routines",
        "short_url": "https://bit.ly/vtissueroutines",
        "document_id": "1cORiFefxaTxULk1RffPtZht2tUNQkGBv9oiPc_qWlCI",
    },
    "fundamentals": {
        "title": "Voltaic Fundamental Kovaak's Routines 2.5",
        "short_url": "https://bit.ly/VTfundamentals2",
        "document_id": "1iunv6vXKWZpjpFvclGLGBeFg6WudwsavozZ-TlGDq_c",
    },
    "scenarios": {
        "title": "Voltaic Recommended Scenario Sheet",
        "short_url": "https://bit.ly/vtscenariosheet",
        "document_id": "1bLUVZJvaxSTtjIrsjTdXopRsvXnqHVvxOxEAa8yLRTg",
    },
}

TIER_ORDER = [
    "Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Jade",
    "Master", "Grandmaster", "Nova", "Astra", "Celestial", "Radiant",
]

COLUMN_TAXONOMY = {
    "A": ("Clicking_Static", "Static/Pokeball", "Clicking", "Static"),
    "B": ("Clicking_Dynamic", "Dynamic/Linear Dynamic", "Clicking", "Dynamic"),
    "C": ("Tracking_Precise", "Precise/Smooth", "Tracking", "Precise"),
    "D": ("Tracking_Reactive", "Reactive", "Tracking", "Reactive"),
    "E": ("Switching_Speed", "Speed/PreciseTS", "Switching", "Speed"),
    "F": ("Switching_Evasive", "Evasive/SmoothTS", "Switching", "Evasive"),
    "G": ("Movement_Clicking", "Movement Clicking", "Movement", "Clicking"),
    "H": ("Movement_Tracking", "Movement Tracking", "Movement", "Tracking"),
}

# S5 splits three source columns into finer benchmark labels. These mappings are
# explicit because the source sheet itself intentionally groups them together.
S5_EQUIVALENTS = {
    "Clicking_Dynamic": ["Clicking_Dynamic", "Clicking_Linear"],
    "Tracking_Precise": ["Tracking_Precise", "Tracking_Control"],
    "Switching_Evasive": ["Switching_Evasive", "Switching_Stability"],
}

COLORS = {
    "Clicking": "#8b9cfb",
    "Tracking": "#6ee7b7",
    "Switching": "#f0abfc",
    "Movement": "#fbbf24",
}

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
X_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "AimCompanion/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def export_docx(document_id: str) -> bytes:
    return download(f"https://docs.google.com/document/d/{document_id}/export?format=docx")


def export_xlsx(document_id: str) -> bytes:
    return download(f"https://docs.google.com/spreadsheets/d/{document_id}/export?format=xlsx")


def docx_paragraphs(payload: bytes) -> list[dict]:
    namespace = {"w": W_NS}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))

    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(
            node.text or "" for node in paragraph.findall(".//w:t", namespace)
        ).strip()
        if not text:
            continue
        style_node = paragraph.find("./w:pPr/w:pStyle", namespace)
        style = style_node.get(f"{{{W_NS}}}val") if style_node is not None else ""
        number_node = paragraph.find("./w:pPr/w:numPr", namespace)
        level = None
        if number_node is not None:
            level_node = number_node.find("./w:ilvl", namespace)
            if level_node is not None:
                level = int(level_node.get(f"{{{W_NS}}}val"))
        paragraphs.append({"text": text, "style": style, "level": level})
    return paragraphs


def xlsx_columns(payload: bytes) -> dict[str, list[str]]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(f"{{{X_NS}}}si"):
                shared.append("".join(node.text or "" for node in item.iter(f"{{{X_NS}}}t")))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            item.get("Id"): item.get("Target")
            for item in relationships.findall(f"{{{P_NS}}}Relationship")
        }
        sheet = workbook.find(f"{{{X_NS}}}sheets")[0]
        target = targets[sheet.get(f"{{{R_NS}}}id")].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ET.fromstring(archive.read(target))

    values = defaultdict(list)
    for cell in root.findall(f".//{{{X_NS}}}c"):
        reference = cell.get("r", "")
        column = re.match(r"[A-Z]+", reference).group(0)
        if column not in COLUMN_TAXONOMY:
            continue
        cell_type = cell.get("t")
        value_node = cell.find(f"{{{X_NS}}}v")
        inline_node = cell.find(f"{{{X_NS}}}is")
        value = ""
        if cell_type == "s" and value_node is not None:
            value = shared[int(value_node.text)]
        elif cell_type == "inlineStr" and inline_node is not None:
            value = "".join(node.text or "" for node in inline_node.iter(f"{{{X_NS}}}t"))
        elif value_node is not None:
            value = value_node.text or ""
        value = re.sub(r"\s*\*+\s*$", "", value).strip()
        row_number = int(re.search(r"\d+", reference).group(0))
        if value and row_number > 2:
            values[column].append(value)
    return dict(values)


def build_scenario_data(columns: dict[str, list[str]]) -> tuple[dict, dict]:
    categories = {}
    scenario_index = defaultdict(set)
    for column, (key, label, category, subcategory) in COLUMN_TAXONOMY.items():
        scenarios = list(dict.fromkeys(columns.get(column, [])))
        categories[key] = {
            "name": label,
            "category": category,
            "subcategory": subcategory,
            "source_column": column,
            "color": COLORS[category],
            "scenarios": scenarios,
        }
        target_keys = S5_EQUIVALENTS.get(key, [key])
        for scenario in scenarios:
            scenario_index[normalize_name(scenario)].update(target_keys)

    data = {
        "description": "Scenario recommendations synchronized from the Voltaic scenario sheet.",
        "source": SOURCES["scenarios"]["short_url"],
        "taxonomy_note": (
            "The source combines Dynamic/Linear, Precise/Control, and "
            "Evasive/Stability; s5_equivalents records that mapping explicitly."
        ),
        "s5_equivalents": S5_EQUIVALENTS,
        "categories": categories,
    }
    return data, scenario_index


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.casefold())


def duration_range(text: str) -> tuple[int | None, int | None]:
    match = re.search(r"Duration:\s*(\d+)\s*[-–]?\s*(\d+)?\s*(?:~\s*)?minutes", text, re.I)
    if not match:
        return None, None
    low = int(match.group(1))
    high = int(match.group(2) or low)
    return low, high


def parse_prescription(text: str) -> tuple[int, int, list[str], bool]:
    optional = "optional" in text.casefold()
    cleaned = re.sub(r"\s+optional\s*\*?", "", text, flags=re.I).strip()
    parts = [part.strip(" -") for part in re.split(r"\s+or\s+", cleaned) if part.strip(" -")]
    names = []
    minute_values = []
    run_values = []
    for part in parts:
        minute_match = re.search(r"\s+-\s+(\d+)(?:\s*[-–]\s*(\d+))?\s*m(?:in(?:ute)?s?)?\b", part, re.I)
        run_match = re.search(r"\s+-\s+(\d+)(?:\s*[-–]\s*(\d+))?\s*runs?\b", part, re.I)
        cutoff = len(part)
        if minute_match:
            minute_values.extend([int(minute_match.group(1)), int(minute_match.group(2) or minute_match.group(1))])
            cutoff = min(cutoff, minute_match.start())
        if run_match:
            run_values.extend([int(run_match.group(1)), int(run_match.group(2) or run_match.group(1))])
            cutoff = min(cutoff, run_match.start())
        name = re.sub(r"\s+-\s*$", "", part[:cutoff]).strip()
        if name and not re.fullmatch(r"\d+\s*(?:m|minutes?|runs?)", name, re.I):
            names.append(name)

    if not names:
        names = [re.split(r"\s+-\s+\d", cleaned, maxsplit=1)[0].strip()]
    minimum = min(minute_values) if minute_values else (min(run_values) if run_values else 3)
    maximum = max(minute_values) if minute_values else (max(run_values) if run_values else minimum)
    return minimum, maximum, list(dict.fromkeys(names)), optional


def eligible_ranks(text: str, exact_rank: str | None = None) -> list[str]:
    if exact_rank:
        return [exact_rank.title()]
    lowered = text.casefold()
    mentioned = [tier for tier in TIER_ORDER if tier.casefold() in lowered]
    if not mentioned:
        return []
    if "and below" in lowered or "up to" in lowered:
        return TIER_ORDER[: TIER_ORDER.index(mentioned[-1]) + 1]
    if "and above" in lowered or "+" in text:
        return TIER_ORDER[TIER_ORDER.index(mentioned[0]) :]
    return mentioned


def heuristic_targets(name: str) -> set[str]:
    lowered = name.casefold()
    rules = (
        ("Clicking_Static", ("1w", "ww", "static", "sphere hipfire", "pokeball")),
        ("Clicking_Dynamic", ("pasu", "popcorn", "b180", "bounce click", "floating heads")),
        ("Tracking_Precise", ("smooth", "centering", "thin", "pgt", "glider", "control")),
        ("Tracking_Reactive", ("react", "strafe", "ground plaza", "air ", "kindaclose")),
        ("Switching_Speed", ("voxt", "patts", "dotts", "targetswitch", "pokeball auto")),
        ("Switching_Evasive", ("kints", "b180t", "switch", "ts ")),
    )
    for key, hints in rules:
        if any(hint in lowered for hint in hints):
            return set(S5_EQUIVALENTS.get(key, [key]))
    return set()


def exercise_targets(names: list[str], scenario_index: dict) -> set[str]:
    targets = set()
    for name in names:
        targets.update(scenario_index.get(normalize_name(name), set()))
        if not scenario_index.get(normalize_name(name)):
            targets.update(heuristic_targets(name))
    return targets


def new_routine(name: str, kind: str, group: str, variant: str = "") -> dict:
    return {
        "name": name,
        "kind": kind,
        "group": group,
        "variant": variant,
        "description": "",
        "duration_minutes": None,
        "duration_max_minutes": None,
        "share_code": "",
        "recommended_ranks": [],
        "min_rank": "Iron",
        "targets": [],
        "source": SOURCES[kind]["title"],
        "source_url": SOURCES[kind]["short_url"],
        "exercises": [],
    }


def finalize_routine(routine: dict, scenario_index: dict) -> dict | None:
    if not routine or not routine["exercises"]:
        return None
    targets = set()
    required_total = 0
    for exercise in routine["exercises"]:
        targets.update(exercise_targets([exercise["scenario"], *exercise["alternatives"]], scenario_index))
        if not exercise["optional"]:
            required_total += exercise["duration_min"]
    routine["targets"] = sorted(targets)
    if routine["kind"] == "issue":
        issue_targets = {
            "Smoothness & Precision": ["Tracking_Precise", "Tracking_Control"],
            "Static": ["Clicking_Static"],
            "Speed": ["Switching_Speed"],
            "Reactivity": ["Tracking_Reactive"],
            "Strafe Tracking": ["Tracking_Reactive", "Tracking_Control", "Movement_Tracking"],
        }
        routine["targets"] = issue_targets.get(routine["group"], routine["targets"])
    if routine["duration_minutes"] is None:
        routine["duration_minutes"] = required_total
        routine["duration_max_minutes"] = required_total
    if routine["recommended_ranks"]:
        routine["min_rank"] = routine["recommended_ranks"][0]
    return routine


def add_exercise(routine: dict, text: str):
    minimum, maximum, names, optional = parse_prescription(text)
    if not names or not names[0]:
        return
    routine["exercises"].append({
        "scenario": names[0],
        "alternatives": names[1:],
        "duration": f"{minimum}m",
        "duration_min": minimum,
        "duration_max": maximum,
        "optional": optional,
        "focus": "",
    })


def parse_game_routines(paragraphs: list[dict], scenario_index: dict) -> list[dict]:
    routines = []
    game = ""
    current = None
    ignored_h1 = {"Introduction", "Why should you follow these routines?", "Credits"}

    def finish():
        nonlocal current
        result = finalize_routine(current, scenario_index)
        if result:
            routines.append(result)
        current = None

    for paragraph in paragraphs:
        text, style, level = paragraph["text"], paragraph["style"], paragraph["level"]
        if style == "Heading1":
            finish()
            game = "" if text in ignored_h1 else text.title()
        elif style == "Heading2" and game:
            finish()
            if text.casefold() not in {"in-game", "about this routine"}:
                current = new_routine(f"{game} — {text}", "game", game, text)
        elif current:
            low, high = duration_range(text)
            if low is not None:
                current["duration_minutes"], current["duration_max_minutes"] = low, high
            elif re.fullmatch(r"KOVAAKS[A-Z0-9]+", text):
                current["share_code"] = text
            elif text.casefold().startswith("recommended"):
                current["recommended_ranks"] = eligible_ranks(text)
            elif level == 0:
                add_exercise(current, text)
    finish()
    return routines


def parse_issue_routines(paragraphs: list[dict], scenario_index: dict) -> list[dict]:
    routines = []
    issue = ""
    base_name = ""
    current = None
    ignored = {"Introduction", "Credits"}

    def finish():
        nonlocal current
        result = finalize_routine(current, scenario_index)
        if result:
            routines.append(result)
        current = None

    for paragraph in paragraphs:
        text, style, level = paragraph["text"], paragraph["style"], paragraph["level"]
        if style == "Heading1":
            finish()
            issue = "" if text in ignored else text
            base_name = issue
        elif style == "Heading2" and issue and text.casefold().endswith("routine"):
            finish()
            base_name = re.sub(r"\s+Routine$", "", text, flags=re.I) or issue
            current = new_routine(base_name, "issue", issue)
        elif style == "Heading3" and issue:
            finish()
            current = new_routine(f"{base_name} — {text}", "issue", issue, text)
        elif current:
            low, high = duration_range(text)
            if low is not None:
                current["duration_minutes"], current["duration_max_minutes"] = low, high
            elif re.fullmatch(r"KOVAAKS[A-Z0-9]+", text):
                current["share_code"] = text
            elif text.casefold().startswith("recommended"):
                current["recommended_ranks"] = eligible_ranks(text)
            elif level == 0:
                add_exercise(current, text)
    finish()
    return routines


def parse_fundamental_routines(paragraphs: list[dict], scenario_index: dict) -> list[dict]:
    routines = []
    rank = ""
    current = None

    def finish():
        nonlocal current
        result = finalize_routine(current, scenario_index)
        if result:
            routines.append(result)
        current = None

    for paragraph in paragraphs:
        text, style, level = paragraph["text"], paragraph["style"], paragraph["level"]
        if style == "Heading1" and text.title() in TIER_ORDER:
            finish()
            rank = text.title()
        elif style == "Heading2" and rank and (
            "ROUTINE" in text.upper() or "STRAFE" in text.upper()
        ):
            finish()
            current = new_routine(
                f"{rank} — {text.title()}", "fundamentals", "Fundamentals", text.title()
            )
            current["recommended_ranks"] = [rank]
        elif current:
            low, high = duration_range(text)
            if low is not None:
                current["duration_minutes"], current["duration_max_minutes"] = low, high
            elif re.fullmatch(r"KOVAAKS[A-Z0-9]+", text):
                current["share_code"] = text
            elif level == 0:
                add_exercise(current, text)
    finish()
    return routines


def main():
    scenario_payload = export_xlsx(SOURCES["scenarios"]["document_id"])
    scenario_data, scenario_index = build_scenario_data(xlsx_columns(scenario_payload))

    routines = []
    routines.extend(parse_game_routines(
        docx_paragraphs(export_docx(SOURCES["game"]["document_id"])), scenario_index
    ))
    routines.extend(parse_issue_routines(
        docx_paragraphs(export_docx(SOURCES["issue"]["document_id"])), scenario_index
    ))
    routines.extend(parse_fundamental_routines(
        docx_paragraphs(export_docx(SOURCES["fundamentals"]["document_id"])), scenario_index
    ))

    routine_data = {
        "description": "Structured factual index of the supplied Voltaic routine documents.",
        "sources": [
            {"title": value["title"], "url": value["short_url"]}
            for key, value in SOURCES.items() if key != "scenarios"
        ],
        "routines": routines,
    }

    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "recommended_scenarios.json").write_text(
        json.dumps(scenario_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (DATA_DIR / "voltaic_routines.json").write_text(
        json.dumps(routine_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Synchronized {sum(len(v['scenarios']) for v in scenario_data['categories'].values())} "
        f"scenario recommendations and {len(routines)} routines."
    )


if __name__ == "__main__":
    main()
