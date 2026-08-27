import json
import os
from models.score import PlayerProfile
from core.scenario_duration import quick_block_plan
from core.scenario_files import installed_scenario_names, iter_scenario_files
from models.config import (
    TrainingConfig, _scenario_difficulty, build_routine,
    get_scenario_difficulty_for_tier,
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

with open(os.path.join(DATA_DIR, "scenarios.json"), "r") as f:
    _RAW_SCENARIOS = json.load(f)

with open(os.path.join(DATA_DIR, "voltaic_routines.json"), "r", encoding="utf-8") as f:
    _ROUTINE_DATA = json.load(f)

with open(os.path.join(DATA_DIR, "recommended_scenarios.json"), "r", encoding="utf-8") as f:
    _RECOMMENDATION_DATA = json.load(f)

with open(os.path.join(DATA_DIR, "voltaic_guidance.json"), "r", encoding="utf-8") as f:
    GUIDANCE = json.load(f)

with open(os.path.join(DATA_DIR, "aim_glossary.json"), "r", encoding="utf-8") as f:
    AIM_GLOSSARY = json.load(f)

ROUTINES = _ROUTINE_DATA["routines"]


def _normalize_name(name: str) -> str:
    return "".join(character for character in name.casefold() if character.isalnum())


def _official_scenario_index() -> dict[str, dict]:
    equivalents = _RECOMMENDATION_DATA.get("s5_equivalents", {})
    index = {}
    for key, category_data in _RECOMMENDATION_DATA.get("categories", {}).items():
        targets = equivalents.get(key, [key])
        for name in category_data.get("scenarios", []):
            normalized = _normalize_name(name)
            item = index.setdefault(normalized, {"name": name, "targets": set()})
            item["targets"].update(targets)
    return index


OFFICIAL_SCENARIOS = _official_scenario_index()

_SUBCATEGORY_HINTS = {
    "Dynamic": ("pasu", "popcorn", "bounce click", "moving click"),
    "Static": ("static", "1wall", "1w4t", "sphere hipfire", "pokeball", "pressure"),
    "Linear": ("frogtagon", "floating heads", "linear"),
    "Precise": ("smooth", "centering", "thin", "pgt", "glider", "precise"),
    "Reactive": ("react", "fast strafe", "air ufo", "ground", "aether", "narrow strafe"),
    "Control": ("control track", "controlsphere", "long strafe", "revolving", "dodge"),
    "Speed": ("dotts", "eddiets", "targetswitch", "patcircle", "speed switch"),
    "Evasive": ("driftts", "flyts", "viscose", "evasive"),
    "Stability": ("controlts", "penta bounce", "stability"),
}


def infer_routine_target(name: str, targets: list[str], fallback: dict = None) -> tuple[str, str]:
    """Infer category metadata for routine-only scenarios without silently returning blanks."""
    exact_targets = []
    for target in targets:
        if "_" in target:
            category, subcategory = target.split("_", 1)
            exact_targets.append((category, subcategory))

    fallback_pair = None
    if fallback:
        fallback_pair = (fallback.get("category", ""), fallback.get("subcategory", ""))
        if fallback_pair in exact_targets:
            return fallback_pair

    lowered = name.lower()
    for subcategory, hints in _SUBCATEGORY_HINTS.items():
        if any(hint in lowered for hint in hints):
            for category, allowed_subcategory in exact_targets:
                if allowed_subcategory == subcategory:
                    return category, subcategory

    if len(exact_targets) == 1:
        return exact_targets[0]
    if exact_targets:
        return exact_targets[0]
    if fallback_pair and all(fallback_pair):
        return fallback_pair
    return "General", "Mixed"


def _build_scenario_catalog() -> list[dict]:
    catalog = []
    known_normalized = set()
    for raw_scenario in _RAW_SCENARIOS:
        scenario = dict(raw_scenario)
        normalized = _normalize_name(scenario["name"])
        official = OFFICIAL_SCENARIOS.get(normalized)
        if official:
            scenario["official_recommended"] = True
            scenario["recommendation_targets"] = sorted(official["targets"])
        catalog.append(scenario)
        known_normalized.add(normalized)

    for normalized, official in OFFICIAL_SCENARIOS.items():
        if normalized in known_normalized:
            continue
        primary_target = sorted(official["targets"])[0]
        category, subcategory = primary_target.split("_", 1)
        catalog.append({
            "name": official["name"],
            "category": category,
            "subcategory": subcategory,
            "difficulty": "Unknown",
            "tags": [category.lower(), subcategory.lower(), "voltaic-recommended"],
            "description": "Recommended in the Voltaic scenario sheet.",
            "installed": False,
            "instructions": "",
            "official_recommended": True,
            "recommendation_targets": sorted(official["targets"]),
        })
        known_normalized.add(normalized)

    pending = {}

    for routine in ROUTINES:
        targets = routine.get("targets", [])
        for exercise in routine.get("exercises", []):
            name = exercise.get("scenario", "").strip()
            normalized = _normalize_name(name)
            if not name or normalized in known_normalized or normalized in pending:
                continue
            category, subcategory = infer_routine_target(name, targets)
            pending[normalized] = {
                "name": name,
                "category": category,
                "subcategory": subcategory,
                "difficulty": "Unknown",
                "tags": [category.lower(), subcategory.lower(), "routine"],
                "description": routine.get("description", ""),
                "installed": False,
                "instructions": exercise.get("focus", ""),
                "official_recommended": True,
                # A routine's target list describes the whole playlist, not
                # every individual exercise. Use the exercise's inferred skill
                # so a clicking drill cannot leak into tracking recommendations.
                "recommendation_targets": [f"{category}_{subcategory}"],
            }

    catalog.extend(pending.values())
    return catalog


SCENARIOS = _build_scenario_catalog()
SCENARIO_MAP = {s["name"]: s for s in SCENARIOS}
SCENARIO_NORMALIZED_MAP = {_normalize_name(s["name"]): s for s in SCENARIOS}


def load_scenario_db() -> list[dict]:
    return SCENARIOS


def get_scenario_info(scenario_name: str) -> dict | None:
    return SCENARIO_MAP.get(scenario_name) or SCENARIO_NORMALIZED_MAP.get(
        _normalize_name(scenario_name)
    )


def get_game_options() -> list[str]:
    games = sorted({
        routine.get("group", "")
        for routine in ROUTINES
        if routine.get("kind") == "game" and routine.get("group")
    })
    return ["General / Fundamentals", *games]


def get_training_guidance(category: str = None, subcategory: str = None) -> dict:
    """Return the locally preserved technique guidance for an S5 skill."""
    if category and subcategory:
        key = f"{category}_{subcategory}"
        if key in GUIDANCE.get("categories", {}):
            return GUIDANCE["categories"][key]
    return {
        "title": "General mouse control",
        "goal": GUIDANCE["session_method"]["summary"],
        "cue": GUIDANCE["principles"][0],
        "avoid": "Do not sacrifice repeatable technique for a single high-score attempt.",
        "progress": GUIDANCE["difficulty_and_progression"]["summary"],
    }


def get_exercise_cue(category: str, subcategory: str) -> str:
    return get_training_guidance(category, subcategory)["cue"]


def enrich_routine_with_guidance(
    routine: dict, source_routine: dict | None = None,
    game: str = "General / Fundamentals",
) -> dict:
    """Attach concise, actionable theory to a generated routine and its exercises."""
    represented = []
    for exercise in routine.get("exercises", []):
        category = exercise.get("category", "General")
        subcategory = exercise.get("subcategory", "Mixed")
        exercise["coaching_cue"] = get_exercise_cue(category, subcategory)
        key = f"{category}_{subcategory}"
        if key not in represented:
            represented.append(key)

    warmup_cue = (
        "Start below maximum speed. Stay relaxed and use this block to prepare "
        "clean movement, not to chase a score."
    )
    for exercise in routine.get("warmup_scenarios", []):
        exercise["coaching_cue"] = warmup_cue

    principles = GUIDANCE.get("principles", [])
    cues = [
        GUIDANCE["session_method"]["steps"][2],
        principles[1],
    ]
    for key in represented[:2]:
        guidance = GUIDANCE.get("categories", {}).get(key)
        if guidance:
            cues.append(guidance["cue"])

    theory_summary = GUIDANCE["session_method"]["summary"]
    if source_routine:
        kind = source_routine.get("kind")
        group = source_routine.get("group", "")
        if kind == "issue":
            theory_summary = GUIDANCE.get("issues", {}).get(group, theory_summary)
        elif kind == "game":
            theory_summary = GUIDANCE.get("game_transfer", {}).get(group, theory_summary)
        elif kind == "fundamentals":
            theory_summary = (
                "This is skill-building practice rather than a benchmark. Use the "
                "routine matching your achieved rank and preserve the intended technique."
            )
    elif game:
        theory_summary = GUIDANCE.get("game_transfer", {}).get(game, theory_summary)

    routine["theory_summary"] = theory_summary
    routine["session_cues"] = list(dict.fromkeys(cues))[:5]
    routine["progression_guidance"] = GUIDANCE["difficulty_and_progression"]["summary"]
    routine["practice_mode"] = "Learning Zone"
    routine["mindset_cue"] = GUIDANCE["mindset"]["learning_zone"]
    routine["reflection_prompt"] = GUIDANCE["mindset"]["reflection_prompt"]
    routine["reset_cue"] = GUIDANCE["mindset"]["reset_action"]
    routine["scope_guidance"] = GUIDANCE["practice_scope"]["transfer_rule"]
    if routine.get("total_minutes", 0) >= 60:
        routine["break_guidance"] = GUIDANCE["training_environment"]["session_quality"]
    else:
        routine["break_guidance"] = ""
    routine["guidance_sources"] = GUIDANCE.get("sources", [])
    return routine


def generate_routine(
    profile: PlayerProfile,
    available_minutes: int = 60,
    focus_weakest: bool = True,
    include_tracking: bool = True,
    day: int = 1,
    config: TrainingConfig = None,
) -> dict:
    loaded_defaults = config is None
    if config is None:
        config = TrainingConfig.load()
    if loaded_defaults:
        config.focus = "weakest" if focus_weakest else "balanced"
    config.session_minutes = available_minutes
    return build_routine(profile, config, include_tracking=include_tracking, day=day)


GAME_WARMUP_TARGETS = {
    "Valorant & Counterstrike": ("Clicking_Static", "Clicking_Dynamic", "Switching_Speed"),
    "Rainbow 6 Siege": ("Clicking_Static", "Switching_Speed", "Tracking_Precise"),
    "Apex Legends": ("Tracking_Reactive", "Tracking_Control", "Tracking_Precise"),
    "Overwatch": ("Tracking_Reactive", "Tracking_Precise", "Clicking_Dynamic"),
    "Arena Fps: Quake & Diabotical": ("Tracking_Reactive", "Tracking_Control", "Clicking_Dynamic"),
    "Call Of Duty & Battlefield": ("Switching_Speed", "Tracking_Reactive", "Tracking_Control"),
    "Warzone - Call Of Duty": ("Switching_Evasive", "Tracking_Control", "Tracking_Reactive"),
    "Fortnite": ("Clicking_Dynamic", "Clicking_Linear", "Tracking_Reactive"),
    "Destiny 2": ("Tracking_Control", "Switching_Evasive", "Clicking_Dynamic"),
    "Hyper Scape": ("Tracking_Reactive", "Tracking_Control", "Clicking_Dynamic"),
    "Splitgate": ("Switching_Speed", "Tracking_Reactive", "Clicking_Dynamic"),
}

_STARTER_TARGET_ORDER = [
    "Clicking_Static", "Tracking_Precise", "Switching_Speed",
    "Clicking_Dynamic", "Tracking_Reactive", "Switching_Evasive",
    "Clicking_Linear", "Tracking_Control", "Switching_Stability",
]


def _weighted_maintenance_cycle(items):
    """Repeat the weakest item while guaranteeing scheduled maintenance."""
    if len(items) <= 1:
        return list(items)
    if len(items) == 2:
        return [items[0], items[1], items[0]]
    return [items[0], items[1], items[0], items[2], *items[3:]]


def _micro_session_target(profile, rotation_index: int):
    measured = sorted(
        [
            subcategory
            for category in profile.categories
            for subcategory in category.subcategories
            if any(benchmark.best_score > 0 for benchmark in subcategory.benchmarks)
        ],
        key=lambda subcategory: subcategory.energy,
    )
    if measured:
        category_groups = []
        for category_name in ("Clicking", "Tracking", "Switching"):
            subcategories = sorted([
                subcategory for subcategory in measured
                if subcategory.category == category_name
            ], key=lambda subcategory: subcategory.energy)
            if subcategories:
                category_groups.append((category_name, subcategories))
        category_groups.sort(key=lambda item: item[1][0].energy)
        category_cycle = _weighted_maintenance_cycle(category_groups)
        selected_group = category_cycle[rotation_index % len(category_cycle)]
        prior_occurrences = sum(
            1 for index in range(rotation_index)
            if category_cycle[index % len(category_cycle)] is selected_group
        )
        subcategory_cycle = _weighted_maintenance_cycle(selected_group[1])
        target = subcategory_cycle[prior_occurrences % len(subcategory_cycle)]
        basis = (
            "benchmark weakness"
            if selected_group is category_groups[0] and target is selected_group[1][0]
            else "skill maintenance"
        )
        return target.category, target.name, basis, target.tier

    category, subcategory = _STARTER_TARGET_ORDER[
        rotation_index % len(_STARTER_TARGET_ORDER)
    ].split("_", 1)
    return category, subcategory, "balanced starter", profile.overall_tier


def _preferred_quick_difficulty(tier: str) -> str:
    if tier in ("Iron", "Bronze", "Silver"):
        return "Novice"
    if tier in ("Gold", "Platinum", "Diamond", "Jade"):
        return "Intermediate"
    return "Advanced"


def _scenario_training_targets(scenario: dict) -> set[str]:
    targets = scenario.get("recommendation_targets")
    if targets:
        return set(targets)
    return {f"{scenario.get('category')}_{scenario.get('subcategory')}"}


ISSUE_FOCUS_CUES = {
    "overflicking": "Bias the initial movement to stop just short, then correct forward without reversing direction.",
    "curved_path": "Prioritize a straight target-to-target path, even if the first movement needs to be slower.",
    "shaky_tense": "Relax your grip and shoulder; reduce pace until the movement stays smooth.",
    "overcorrecting": "After a direction change, make one small correction toward the target's inner edge and settle.",
    "predicting": "React only to movement you can see; do not guess the next direction change.",
    "target_selection": "Choose the next efficient target before finishing the current one.",
}


def generate_quick_scenario(
    profile: PlayerProfile,
    warmup: bool = False,
    recent_names: list[str] | None = None,
    rotation_index: int = 0,
    config: TrainingConfig | None = None,
    warmup_context: str = "Aim training",
    training_schedule: list[dict] | None = None,
    scenario_signals: dict[str, dict] | None = None,
) -> dict:
    """Choose one official, rank-suitable scenario for a short duration-aware block."""
    config = config or TrainingConfig.load()
    recent = {_normalize_name(name) for name in (recent_names or [])}
    selection_basis = "warm-up"
    selection_tier = profile.overall_tier
    progression = "hold"
    focus_issue = ""
    observation_id = None
    observed_game = ""
    observation_note = ""
    if not warmup:
        if training_schedule:
            target = training_schedule[rotation_index % len(training_schedule)]
            target_category = target["category"]
            target_subcategory = target["subcategory"]
            selection_tier = target["tier"]
            progression = target.get("progression", "hold")
            focus_issue = target.get("latest_issue", "")
            observation_id = target.get("observation_id")
            observed_game = target.get("observed_game", "")
            observation_note = target.get("observation_note", "")
            selection_basis = (
                "evidence-building" if target.get("benchmark_due") else
                "adaptive weakness" if target.get("weakness_severity", 0) >= 0.12 else
                "maintenance recency"
            )
        else:
            (
                target_category, target_subcategory, selection_basis, selection_tier,
            ) = _micro_session_target(profile, rotation_index)
    valid_difficulties = set(get_scenario_difficulty_for_tier(selection_tier))
    difficulty_order = ["Novice", "Intermediate", "Advanced"]
    preferred = _preferred_quick_difficulty(selection_tier)
    preferred_index = difficulty_order.index(preferred)
    if progression == "advance" and preferred_index < len(difficulty_order) - 1:
        preferred = difficulty_order[preferred_index + 1]
        valid_difficulties.add(preferred)
    elif progression == "regress" and preferred_index > 0:
        preferred = difficulty_order[preferred_index - 1]
        valid_difficulties.add(preferred)
    install_dirs = config.get_scenario_dirs()
    installed = installed_scenario_names(install_dirs)

    candidates = []
    continuous_turn_hints = ("revolving", "360", "centering i 180")
    for scenario in SCENARIOS:
        if not scenario.get("official_recommended"):
            continue
        if config.avoid_continuous_turns and any(
            hint in scenario.get("name", "").casefold()
            for hint in continuous_turn_hints
        ):
            continue
        difficulty = _scenario_difficulty(scenario)
        if difficulty not in valid_difficulties and difficulty != "Unknown":
            continue
        candidates.append(scenario)

    target_label = "Smooth control"
    warmup_target_priority = {}
    if warmup:
        context_targets = GAME_WARMUP_TARGETS.get(warmup_context, ())
        if context_targets:
            warmup_target_priority = {
                target: index for index, target in enumerate(context_targets)
            }
            warmup_candidates = [
                scenario for scenario in candidates
                if _scenario_training_targets(scenario) & set(warmup_target_priority)
            ]
            target_label = warmup_context
        else:
            warmup_candidates = [
                scenario for scenario in candidates
                if scenario.get("category") == "Tracking"
                and scenario.get("subcategory") in ("Precise", "Control")
            ]
        if warmup_candidates:
            candidates = warmup_candidates
    else:
        target_key = f"{target_category}_{target_subcategory}"
        targeted = [
            scenario for scenario in candidates
            if target_key in _scenario_training_targets(scenario)
        ]
        if targeted:
            candidates = targeted
        target_label = f"{target_category} · {target_subcategory}"

    fresh = [scenario for scenario in candidates if _normalize_name(scenario["name"]) not in recent]
    if fresh:
        candidates = fresh
    if not candidates:
        raise LookupError("No suitable official scenarios are available.")

    def candidate_score(scenario):
        score = 0
        if config.prioritize_installed and scenario["name"].casefold() in installed:
            score += 1
        difficulty = _scenario_difficulty(scenario)
        if difficulty == preferred:
            score += 10
        elif difficulty in valid_difficulties:
            score += 6
        elif difficulty == "Unknown":
            score += 3
        if warmup and "smooth" in scenario["name"].casefold():
            score += 5
        if (
            warmup_target_priority
            and difficulty == get_scenario_difficulty_for_tier(profile.overall_tier)[0]
        ):
            score += 4
        matching_priorities = [
            warmup_target_priority[target]
            for target in _scenario_training_targets(scenario)
            if target in warmup_target_priority
        ]
        if matching_priorities:
            score += max(4, 12 - min(matching_priorities) * 3)
        if scenario_signals:
            score += scenario_signals.get(
                scenario["name"].casefold(), {}
            ).get("adjustment", 0.0)
        return score

    candidates.sort(key=lambda scenario: (-candidate_score(scenario), scenario["name"]))
    scenario = candidates[0]
    category = (
        scenario.get("category", "General") if warmup else target_category
    )
    subcategory = (
        scenario.get("subcategory", "Mixed") if warmup else target_subcategory
    )
    if warmup and warmup_target_priority:
        matched_targets = [
            target for target in _scenario_training_targets(scenario)
            if target in warmup_target_priority
        ]
        if matched_targets:
            selected_target = min(
                matched_targets, key=lambda target: warmup_target_priority[target]
            )
            category, subcategory = selected_target.split("_", 1)
    block_plan = quick_block_plan(
        scenario["name"], install_dirs, config.get_stats_dir()
    )
    issue_cue = ISSUE_FOCUS_CUES.get(focus_issue, "")
    reason = (
        (
            "Selected for smooth, controlled preparation without tiring you. "
            "It does not require continuous turning."
            if config.avoid_continuous_turns else
            "Selected for smooth, controlled preparation without tiring you."
        )
        if warmup and warmup_context == "Aim training" else
        f"Selected to prepare you for the main aiming demands of {target_label} without creating fatigue."
        if warmup else
        f"Selected from your adaptive Voltaic priority: {target_label}. "
        "Weak areas recur more often while every category stays in rotation."
        if selection_basis in ("benchmark weakness", "adaptive weakness", "evidence-building") else
        f"Scheduled maintenance for {target_label} so stronger skills do not fall off."
    )
    if issue_cue:
        reason += (
            f" Your {observed_game} review identified this correction."
            if observed_game else
            " Your last review identified a specific correction for this skill."
        )

    return {
        "scenario": scenario["name"],
        "category": category,
        "subcategory": subcategory,
        "runs": block_plan["runs"],
        "estimated_minutes": block_plan["estimated_minutes"],
        "scenario_seconds": block_plan["scenario_seconds"],
        "duration_source": block_plan["duration_source"],
        "installed": scenario["name"].casefold() in installed,
        "warmup": warmup,
        "warmup_context": warmup_context if warmup else None,
        "target_label": target_label,
        "selection_basis": "warm-up" if warmup else selection_basis,
        "target_tier": selection_tier,
        "progression": progression,
        "game_context": config.game,
        "reason": reason,
        "focus_issue": focus_issue if issue_cue else "",
        "observation_id": observation_id,
        "observation_note": observation_note,
        "coaching_cue": issue_cue or get_exercise_cue(category, subcategory),
    }


def get_routines_for_weakness(category: str, subcategory: str, tier: str) -> list[dict]:
    matching = []
    compound = f"{category}_{subcategory}"
    for routine in ROUTINES:
        tags = routine.get("targets", [])
        if compound in tags:
            recommended_ranks = routine.get("recommended_ranks", [])
            rank_req = routine.get("min_rank", "Iron")
            if (recommended_ranks and tier in recommended_ranks) or (
                not recommended_ranks and _tier_above_or_equal(tier, rank_req)
            ):
                matching.append(routine)
    return matching


def _tier_above_or_equal(current: str, required: str) -> bool:
    from models.config import TIER_ORDER
    try:
        return TIER_ORDER.index(current) >= TIER_ORDER.index(required)
    except ValueError:
        return False


def get_vdim_schedule(profile: PlayerProfile) -> dict:
    from models.config import TIER_ORDER

    vdim_routines = [r for r in ROUTINES if r.get("source", "").startswith("Voltaic VDIM")]
    if not vdim_routines:
        return {}

    tier = profile.overall_tier
    tier_idx = TIER_ORDER.index(tier) if tier in TIER_ORDER else 0

    day_map = {
        0: ["Clicking I", "Clicking II"],
        1: ["Clicking II"],
        2: ["Tracking I", "Tracking II"],
        3: ["Tracking II"],
        4: ["Switching I", "Switching II"],
        5: ["Switching II"],
        6: [],
    }

    schedule = {}
    for day_idx, day_name in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]):
        keywords = day_map.get(day_idx, [])
        day_routines = []
        for r in vdim_routines:
            for kw in keywords:
                if kw.lower() in r.get("name", "").lower():
                    r_min_rank = r.get("min_rank", "Iron")
                    if r_min_rank in TIER_ORDER and tier_idx >= TIER_ORDER.index(r_min_rank):
                        day_routines.append(r)
                    break
        schedule[day_name] = day_routines

    return schedule


def get_installed_scenarios() -> list[dict]:
    names = get_installed_scenario_names()
    if names:
        normalized = {name.casefold() for name in names}
        return [s for s in SCENARIOS if s["name"].casefold() in normalized]
    return [s for s in SCENARIOS if s.get("installed", False)]


def get_installed_scenario_names() -> set:
    from models.config import TrainingConfig
    config = TrainingConfig.load()
    return {
        os.path.splitext(os.path.basename(path))[0]
        for path in iter_scenario_files(config.get_scenario_dirs())
    }


def get_scenarios_by_tag(tag: str) -> list[dict]:
    return [s for s in SCENARIOS if tag in s.get("tags", [])]


def get_scenarios_by_category(category: str, subcategory: str = None) -> list[dict]:
    if subcategory:
        return [s for s in SCENARIOS if s["category"] == category and s["subcategory"] == subcategory]
    return [s for s in SCENARIOS if s["category"] == category]
