import json
import os
import random
import re
import tempfile
from dataclasses import dataclass, asdict
from core.paths import writable_path
from core.warmups import get_warmup_routine

CONFIG_PATH = writable_path("config.json")

TIER_ORDER = [
    "Iron", "Bronze", "Silver", "Gold", "Platinum",
    "Diamond", "Jade", "Master", "Grandmaster", "Nova", "Astra", "Celestial", "Radiant"
]

TIER_TO_DIFFICULTY = {
    "Iron": ["Novice"],
    "Bronze": ["Novice"],
    "Silver": ["Novice", "Intermediate"],
    "Gold": ["Novice", "Intermediate"],
    "Platinum": ["Intermediate"],
    "Diamond": ["Intermediate", "Advanced"],
    "Jade": ["Intermediate", "Advanced"],
    "Master": ["Advanced"],
    "Grandmaster": ["Advanced"],
    "Nova": ["Advanced"],
    "Astra": ["Advanced"],
    "Celestial": ["Advanced"],
    "Radiant": ["Advanced"],
}

FOCUS_OPTIONS = {
    "weakest": "Weakest Areas (Recommended)",
    "balanced": "Balanced (All Categories)",
    "clicking": "Clicking Only",
    "tracking": "Tracking Only",
    "switching": "Switching Only",
}

SCENARIO_DURATION_MAP = {
    "Static": 3, "Dynamic": 3, "Linear": 3,
    "Precise": 3, "Reactive": 3, "Control": 3, "Mixed": 3,
    "Speed": 2, "Evasive": 2, "Stability": 2,
}

KNOWN_DRIVES = ["C:", "D:", "E:", "F:", "G:", "H:", "I:", "J:"]
KOVAAKS_STEAM_RELATIVE = os.path.join(
    "steamapps", "common", "FPSAimTrainer", "FPSAimTrainer", "Saved", "SaveGames"
)


def _registry_steam_root() -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            return winreg.QueryValueEx(key, "SteamPath")[0]
    except (OSError, ImportError):
        return ""


def _steam_library_roots(steam_root: str = None) -> list[str]:
    roots = []
    primary = steam_root or _registry_steam_root()
    if primary:
        roots.append(os.path.normpath(primary))
        library_file = os.path.join(primary, "steamapps", "libraryfolders.vdf")
        try:
            with open(library_file, encoding="utf-8", errors="ignore") as file:
                contents = file.read()
            for value in re.findall(r'"(?:path|\d+)"\s+"([^"]+)"', contents):
                roots.append(os.path.normpath(value.replace(r"\\", "\\")))
        except OSError:
            pass
    if steam_root is None:
        for drive in KNOWN_DRIVES:
            roots.extend((
                os.path.join(drive + os.sep, "SteamLibrary"),
                os.path.join(drive + os.sep, "Steam"),
            ))
        roots.extend(filter(None, (
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Steam")
            if os.environ.get("PROGRAMFILES(X86)") else "",
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Steam")
            if os.environ.get("PROGRAMFILES") else "",
        )))
    unique = []
    seen = set()
    for root in roots:
        key = os.path.normcase(os.path.abspath(root))
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _detect_kovaaks_install(library_roots: list[str] = None) -> str:
    roots = library_roots if library_roots is not None else _steam_library_roots()
    for root in roots:
        candidate = os.path.join(root, KOVAAKS_STEAM_RELATIVE)
        if os.path.isdir(candidate):
            return candidate
    fallback_root = roots[0] if roots else os.path.join("C:\\", "Program Files (x86)", "Steam")
    return os.path.join(fallback_root, KOVAAKS_STEAM_RELATIVE)


def _detect_kovaaks_playlists() -> str:
    base = _detect_kovaaks_install()
    pl = os.path.join(base, "Playlists")
    return pl


def _detect_kovaaks_stats(savegames_dir: str = None) -> str:
    """Return Kovaak's result folder, which is outside Saved/SaveGames."""
    base = savegames_dir or _detect_kovaaks_install()
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(base)), "stats"),
        os.path.join(base, "stats"),  # Compatibility with older layouts.
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[0]


@dataclass
class TrainingConfig:
    session_minutes: int = 60
    warmup_minutes: int = 14
    cooldown_minutes: int = 5
    focus: str = "weakest"
    prioritize_installed: bool = False
    kovaaks_install_dir: str = ""
    variety_seed: int = 0
    game: str = "General / Fundamentals"
    avoid_continuous_turns: bool = True
    warmup_context: str = "Aim training"
    voltaic_profile_url: str = ""
    challenge_mode_notice_seen: bool = False
    warmup_routine_version: int = 1
    automatic_updates: bool = True
    daily_fps_minutes: int = 120
    training_mode: str = "focused"
    training_method: str = "adaptive_weakness"
    preferred_routine: str = ""

    def save(self):
        directory = os.path.dirname(CONFIG_PATH) or "."
        os.makedirs(directory, exist_ok=True)
        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=directory, delete=False
            ) as file:
                temp_path = file.name
                json.dump(asdict(self), file, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, CONFIG_PATH)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    @classmethod
    def load(cls) -> "TrainingConfig":
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, encoding="utf-8") as file:
                    data = json.load(file)
            except (OSError, json.JSONDecodeError):
                return cls()
            if not isinstance(data, dict):
                return cls()
            if "warmup_routine_version" not in data:
                data["warmup_minutes"] = 14
                data["warmup_routine_version"] = 1
                migrated = cls(**{
                    k: v for k, v in data.items() if k in cls.__dataclass_fields__
                })
                migrated.save()
                return migrated
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        return cls()

    def get_install_dir(self) -> str:
        if self.kovaaks_install_dir and os.path.isdir(self.kovaaks_install_dir):
            return self.kovaaks_install_dir
        return _detect_kovaaks_install()

    def get_playlists_dir(self) -> str:
        return os.path.join(self.get_install_dir(), "Playlists")

    def get_scenarios_dir(self) -> str:
        return os.path.join(self.get_install_dir(), "Scenarios")

    def get_scenario_dirs(self) -> list[str]:
        from core.scenario_files import scenario_search_dirs
        return scenario_search_dirs(self.get_scenarios_dir())

    def get_stats_dir(self) -> str:
        return _detect_kovaaks_stats(self.get_install_dir())


def get_scenario_difficulty_for_tier(tier: str) -> list[str]:
    return TIER_TO_DIFFICULTY.get(tier, ["Novice"])


def _scenario_difficulty(scenario: dict) -> str:
    difficulty = scenario.get("difficulty", "Unknown")
    if difficulty in ("Novice", "Intermediate", "Advanced"):
        return difficulty
    name = scenario.get("name", "").lower()
    for value in ("Novice", "Intermediate", "Advanced"):
        if value.lower() in name:
            return value
    rank_difficulties = (
        (("grandmaster", "celestial", "radiant", "astra", "nova", "master"), "Advanced"),
        (("platinum", "diamond", "jade"), "Intermediate"),
        (("iron", "bronze", "silver", "gold"), "Novice"),
    )
    for rank_names, inferred in rank_difficulties:
        if any(rank in name for rank in rank_names):
            return inferred
    if any(hint in name for hint in ("very hard", "extra small", " hard")):
        return "Advanced"
    if any(hint in name for hint in ("very easy", " easy", "larger")):
        return "Novice"
    return "Unknown"


def _is_measured(subcategory) -> bool:
    return any(benchmark.best_score > 0 for benchmark in subcategory.benchmarks)


def _measured_weaknesses(profile, count=5, include_tracking=True):
    measured = [
        subcategory
        for category in profile.categories
        for subcategory in category.subcategories
        if _is_measured(subcategory)
        and (include_tracking or subcategory.category != "Tracking")
    ]
    return sorted(measured, key=lambda subcategory: subcategory.energy)[:count]


def score_scenario(
    scenario: dict,
    weaknesses: list,
    tier: str,
    installed: set,
    focus: str,
    prioritize_installed: bool = False,
) -> float:
    score = 0.0
    cat = scenario.get("category", "")
    subcat = scenario.get("subcategory", "")
    name = scenario.get("name", "")
    recommendation_targets = set(
        scenario.get("recommendation_targets", [f"{cat}_{subcat}"])
    )

    if focus == "weakest":
        exact_index = next(
            (index for index, weakness in enumerate(weaknesses)
             if f"{weakness.category}_{weakness.name}" in recommendation_targets),
            None,
        )
        if exact_index is not None:
            score += max(12.0, 30.0 - exact_index * 4.0)
        elif any(
            any(target.startswith(weakness.category + "_") for target in recommendation_targets)
            for weakness in weaknesses
        ):
            score += 5.0
        else:
            score += 0.5
    elif focus == "balanced":
        score += 5.0
    elif focus == cat.lower():
        score += 15.0
        if any(cat == weakness.category and subcat == weakness.name for weakness in weaknesses):
            score += 8.0
    else:
        return -10.0

    if scenario.get("official_recommended"):
        score += 6.0

    # Installation is convenience, not training quality. It may break an
    # otherwise equal tie but must not override skill, rank, or focus fit.
    if prioritize_installed and name.casefold() in installed:
        score += 1.0

    diff = _scenario_difficulty(scenario)
    valid_diffs = get_scenario_difficulty_for_tier(tier)
    if diff in valid_diffs:
        score += 4.0
    elif diff == "Unknown":
        score += 1.0
    else:
        score -= 8.0

    return score


def get_base_name(name):
    suffixes = [
        " Diamond", " Grandmaster", " Jade", " Master", " Nova", " Astra",
        " Celestial", " Gold", " Silver", " Bronze", " Iron", " Platinum",
        " Easy", " Hard", " Intermediate", " Advanced", " Novice",
        " Very Easy", " Very Hard", " Smaller", " Larger", " Thin",
        " Extra Small", " Extra Large", " 30% smaller", " 30% Smaller",
        " Reload", " Fixed", " Varied",
    ]
    result = name
    for suffix in sorted(suffixes, key=len, reverse=True):
        if result.endswith(suffix):
            result = result[:-len(suffix)]
            break
    for suffix in [" v2", " v3", " V2", " V3", " S1", " S2", " S3", " S4", " S5"]:
        if result.endswith(suffix):
            result = result[:-len(suffix)]
            break
    return result


def build_routine(
    profile,
    config: TrainingConfig,
    include_tracking: bool = True,
    day: int = 1,
) -> dict:
    from core.recommender import ROUTINES, SCENARIOS
    from core.scenario_files import installed_scenario_names

    session_minutes, warmup_minutes, training_minutes, cooldown_minutes = _allocate_budget(
        config.session_minutes, config.warmup_minutes, config.cooldown_minutes
    )
    weaknesses = _measured_weaknesses(profile, 5, include_tracking=include_tracking)
    effective_focus = config.focus
    if effective_focus == "weakest" and not weaknesses:
        effective_focus = "balanced"
    valid_diffs = set(get_scenario_difficulty_for_tier(profile.overall_tier))

    installed = installed_scenario_names(config.get_scenario_dirs())

    best_routine = None
    if config.preferred_routine:
        best_routine = next(
            (
                routine for routine in ROUTINES
                if routine.get("name") == config.preferred_routine
            ),
            None,
        )
    if best_routine is None and config.game != "General / Fundamentals":
        best_routine = _find_best_game_routine(
            config.game, weaknesses, profile.overall_tier,
            effective_focus, training_minutes,
        )
    elif best_routine is None and effective_focus == "weakest":
        best_routine = _find_best_premade_routine(
            weaknesses, profile.overall_tier, training_minutes
        )
    elif best_routine is None and effective_focus == "balanced" and include_tracking:
        best_routine = _find_fundamental_routine(
            profile.overall_tier, training_minutes
        )

    seed = config.variety_seed + max(0, int(day)) * 1009 if config.variety_seed else None
    rng = random.Random(seed)

    if best_routine:
        focus_allocation = None
        use_balance_guard = (
            effective_focus == "weakest"
            and best_routine.get("kind") == "issue"
            and bool(weaknesses)
            and training_minutes >= 3
        )
        if use_balance_guard:
            primary_minutes = max(1, round(training_minutes * 0.65))
            support_minutes = training_minutes - primary_minutes
            exercises = _adapt_premade_routine(
                best_routine, primary_minutes, installed,
                focus=effective_focus, weaknesses=weaknesses,
            )
            exercises.extend(_build_balanced_support(
                SCENARIOS, support_minutes, installed, profile.overall_tier,
                excluded_category=weaknesses[0].category,
                prioritize_installed=config.prioritize_installed,
            ))
            focus_allocation = {
                "primary_minutes": primary_minutes,
                "support_minutes": support_minutes,
                "primary_skill": f"{weaknesses[0].category} · {weaknesses[0].name}",
                "primary_category": weaknesses[0].category,
            }
        else:
            exercises = _adapt_premade_routine(
                best_routine, training_minutes, installed,
                focus=effective_focus, weaknesses=weaknesses,
            )
        warmup = get_warmup_scenarios(
            SCENARIOS, installed, warmup_minutes, rng=rng,
            prioritize_installed=config.prioritize_installed, context=config.game,
        )
        result = {
            "focus": config.focus,
            "focus_label": (
                "Weakest Areas · 65% focus / 35% balanced support"
                if focus_allocation else
                FOCUS_OPTIONS.get(config.focus, config.focus)
                if effective_focus == config.focus
                else "Balanced starter routine (complete benchmarks for weakness analysis)"
            ),
            "weakness_areas": ["{} {}".format(w.category, w.name) for w in weaknesses[:3]],
            "warmup_minutes": warmup_minutes,
            "warmup_scenarios": warmup,
            "exercises": exercises,
            "training_minutes": sum(e["duration_min"] for e in exercises),
            "cooldown_minutes": cooldown_minutes,
            "total_minutes": session_minutes,
            "source_routine": best_routine.get("name", ""),
            "source_url": best_routine.get("source_url", ""),
            "has_measured_weaknesses": bool(weaknesses),
            "focus_allocation": focus_allocation,
        }
        from core.recommender import enrich_routine_with_guidance
        return enrich_routine_with_guidance(
            result, source_routine=best_routine, game=config.game
        )

    candidates = []
    for s in SCENARIOS:
        if not s.get("official_recommended"):
            continue
        if not include_tracking and s.get("category") == "Tracking":
            continue
        s_score = score_scenario(
            s, weaknesses, profile.overall_tier, installed, effective_focus,
            config.prioritize_installed,
        )
        if s_score < 0:
            continue
        difficulty = _scenario_difficulty(s)
        if difficulty not in valid_diffs and difficulty != "Unknown":
            continue
        candidates.append((s_score, s))

    tier_idx = TIER_ORDER.index(profile.overall_tier) if profile.overall_tier in TIER_ORDER else 0
    noise_scale = max(0.5, 3.0 - tier_idx * 0.2)
    noisy_candidates = []
    for s_score, s in candidates:
        noisy_candidates.append((s_score + rng.gauss(0, noise_scale), s))
    noisy_candidates.sort(key=lambda x: (-x[0], x[1]["name"]))

    exercises = _select_scenarios(
        noisy_candidates, training_minutes, installed,
        focus=effective_focus, weaknesses=weaknesses,
    )
    warmup = get_warmup_scenarios(
        SCENARIOS, installed, warmup_minutes, rng=rng,
        prioritize_installed=config.prioritize_installed, context=config.game,
    )

    result = {
        "focus": config.focus,
        "focus_label": (
            FOCUS_OPTIONS.get(config.focus, config.focus)
            if effective_focus == config.focus
            else "Balanced starter routine (complete benchmarks for weakness analysis)"
        ),
        "weakness_areas": ["{} {}".format(w.category, w.name) for w in weaknesses[:3]],
        "warmup_minutes": warmup_minutes,
        "warmup_scenarios": warmup,
        "exercises": exercises,
        "training_minutes": sum(e["duration_min"] for e in exercises),
        "cooldown_minutes": cooldown_minutes,
        "total_minutes": session_minutes,
        "source_routine": "",
        "source_url": "",
        "has_measured_weaknesses": bool(weaknesses),
        "focus_allocation": None,
    }
    from core.recommender import enrich_routine_with_guidance
    return enrich_routine_with_guidance(result, game=config.game)


def _allocate_budget(session_minutes, warmup_minutes, cooldown_minutes):
    session = max(0, int(session_minutes))
    warmup = max(0, int(warmup_minutes))
    cooldown = max(0, int(cooldown_minutes))
    if session == 0:
        return 0, 0, 0, 0

    minimum_training = min(3, session)
    accessory_budget = session - minimum_training
    requested_accessory = warmup + cooldown
    if requested_accessory > accessory_budget and requested_accessory > 0:
        warmup = round(accessory_budget * warmup / requested_accessory)
        cooldown = accessory_budget - warmup
    training = session - warmup - cooldown
    return session, warmup, training, cooldown


def _build_balanced_support(
    scenarios, minutes, installed, tier, excluded_category,
    prioritize_installed=False,
):
    """Preserve broad mouse control around an automatically targeted weakness."""
    if minutes <= 0:
        return []
    valid_difficulties = set(get_scenario_difficulty_for_tier(tier))
    candidates = []
    for scenario in scenarios:
        if not scenario.get("official_recommended"):
            continue
        if scenario.get("category") == excluded_category:
            continue
        difficulty = _scenario_difficulty(scenario)
        if difficulty not in valid_difficulties and difficulty != "Unknown":
            continue
        score = score_scenario(
            scenario, [], tier, installed, "balanced", prioritize_installed
        )
        candidates.append((score, scenario))
    candidates.sort(key=lambda item: (-item[0], item[1]["name"]))
    return _select_scenarios(
        candidates, minutes, installed, focus="balanced", weaknesses=[]
    )


def _find_best_premade_routine(weaknesses, tier, training_minutes):
    from core.recommender import get_routines_for_weakness

    candidates = {}
    for w in weaknesses[:3]:
        for routine in get_routines_for_weakness(w.category, w.name, tier):
            if routine.get("kind") != "issue":
                continue
            candidates[routine.get("name", str(id(routine)))] = routine

    if not candidates:
        return None

    scored = []
    current_rank_index = TIER_ORDER.index(tier) if tier in TIER_ORDER else 0
    for routine in candidates.values():
        score = 0.0
        tags = routine.get("targets", [])
        lower_tags = [tag.lower() for tag in tags]
        for index, w in enumerate(weaknesses[:3]):
            tag = "{}_{}".format(w.category, w.name)
            if tag in tags:
                score += max(14.0, 30.0 - index * 6.0)
            elif w.category.lower() in lower_tags:
                score += 4.0
        r_min_rank = routine.get("min_rank", "Iron")
        if r_min_rank in TIER_ORDER:
            rank_distance = abs(current_rank_index - TIER_ORDER.index(r_min_rank))
            score += max(0.0, 8.0 - rank_distance * 2.0)
        if routine.get("share_code"):
            score += 3.0
        duration = routine.get("duration_minutes", 30)
        gap = abs(duration - training_minutes)
        score += max(0.0, 12.0 - gap * 0.6)
        if training_minutes > 0 and duration > training_minutes * 2:
            score -= 20.0
        scored.append((score, routine))

    scored.sort(key=lambda item: (-item[0], item[1].get("name", "")))
    return scored[0][1] if scored else None


def _rank_fit_score(routine, tier):
    recommended = routine.get("recommended_ranks", [])
    if recommended:
        return 12.0 if tier in recommended else -8.0
    current = TIER_ORDER.index(tier) if tier in TIER_ORDER else 0
    minimum = routine.get("min_rank", "Iron")
    required = TIER_ORDER.index(minimum) if minimum in TIER_ORDER else 0
    return max(-8.0, 8.0 - abs(current - required) * 2.0)


def _duration_fit_score(routine, training_minutes):
    duration = routine.get("duration_minutes", training_minutes) or training_minutes
    gap = abs(duration - training_minutes)
    score = max(0.0, 12.0 - gap * 0.4)
    if training_minutes and duration > training_minutes * 2:
        score -= 10.0
    return score


def _find_fundamental_routine(tier, training_minutes):
    from core.recommender import ROUTINES

    available_tiers = [
        value for value in TIER_ORDER
        if any(
            routine.get("kind") == "fundamentals"
            and value in routine.get("recommended_ranks", [])
            for routine in ROUTINES
        )
    ]
    if not available_tiers:
        return None
    target_tier = tier if tier in available_tiers else available_tiers[-1]
    candidates = [
        routine for routine in ROUTINES
        if routine.get("kind") == "fundamentals"
        and target_tier in routine.get("recommended_ranks", [])
        and "complete" in routine.get("variant", "").lower()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda routine: _duration_fit_score(routine, training_minutes))


def _find_best_game_routine(game, weaknesses, tier, focus, training_minutes):
    from core.recommender import ROUTINES

    candidates = [
        routine for routine in ROUTINES
        if routine.get("kind") == "game"
        and routine.get("group", "").casefold() == game.casefold()
    ]
    if focus in ("clicking", "tracking", "switching"):
        prefix = focus.capitalize() + "_"
        candidates = [
            routine for routine in candidates
            if any(target.startswith(prefix) for target in routine.get("targets", []))
        ]
    elif focus == "weakest" and weaknesses:
        weakness_targets = {
            f"{weakness.category}_{weakness.name}" for weakness in weaknesses[:3]
        }
        candidates = [
            routine for routine in candidates
            if weakness_targets.intersection(routine.get("targets", []))
        ]
    if not candidates:
        return None

    def routine_score(routine):
        targets = set(routine.get("targets", []))
        score = _rank_fit_score(routine, tier) + _duration_fit_score(routine, training_minutes)
        if focus == "weakest":
            for index, weakness in enumerate(weaknesses[:3]):
                if f"{weakness.category}_{weakness.name}" in targets:
                    score += max(10.0, 24.0 - index * 5.0)
        elif focus in ("clicking", "tracking", "switching"):
            category = focus.capitalize() + "_"
            score += sum(8.0 for target in targets if target.startswith(category))
        else:
            score += len({target.split("_", 1)[0] for target in targets}) * 5.0
        return score

    return max(candidates, key=lambda routine: (routine_score(routine), routine.get("name", "")))


def _adapt_premade_routine(
    routine, max_time, installed, focus="weakest", weaknesses=None
):
    from core.recommender import get_scenario_info, infer_routine_target

    exercises = []
    total = 0
    required = [exercise for exercise in routine.get("exercises", []) if not exercise.get("optional")]
    optional = [exercise for exercise in routine.get("exercises", []) if exercise.get("optional")]
    raw_exercises = required or optional
    if routine.get("kind") == "game" and focus != "balanced":
        raw_exercises = [*required, *optional]
    if max_time > (routine.get("duration_minutes") or max_time):
        raw_exercises = [*raw_exercises, *optional]
    if not raw_exercises or max_time <= 0:
        return exercises

    prepared = []
    for ex in raw_exercises:
        names = [ex["scenario"], *ex.get("alternatives", [])]
        # Preserve the routine author's primary recommendation. Alternatives
        # are metadata, not a reason to replace quality with local availability.
        scenario_name = names[0]
        scenario_info = get_scenario_info(scenario_name) or {}
        category, subcategory = infer_routine_target(
            scenario_name, routine.get("targets", []), scenario_info
        )
        prepared.append((ex, scenario_name, scenario_info, category, subcategory))

    declared_duration = routine.get("duration_minutes") or sum(
        _parse_duration(ex.get("duration", "3m")) for ex in raw_exercises
    )
    use_selector = (
        routine.get("kind") in ("fundamentals", "game")
        and max_time < declared_duration
    ) or (
        routine.get("kind") == "game" and focus != "balanced"
    )
    if use_selector:
        candidates = []
        for index, (ex, name, info, category, subcategory) in enumerate(prepared):
            scenario = dict(info)
            scenario.update({
                "name": name,
                "category": category,
                "subcategory": subcategory,
                "tags": info.get("tags", []),
                "recommendation_targets": info.get(
                    "recommendation_targets", [f"{category}_{subcategory}"]
                ),
            })
            candidates.append((100.0 - index * 0.01, scenario))
        return _select_scenarios(
            candidates, max_time, installed,
            focus=("balanced" if routine.get("kind") == "fundamentals" else focus),
            weaknesses=weaknesses or [],
        )

    while total < max_time:
        before_pass = total
        for ex, scenario_name, scenario_info, category, subcategory in prepared:
            if total >= max_time:
                break
            duration = _parse_duration(ex.get("duration", "3m"))
            if total + duration > max_time:
                duration = max_time - total
            if duration <= 0:
                continue

            exercises.append({
                "scenario": scenario_name,
                "category": category,
                "subcategory": subcategory,
                "duration_min": duration,
                "installed": scenario_name.casefold() in installed,
                "tags": scenario_info.get("tags", []),
                "focus": ex.get("focus", ""),
            })
            total += duration
        if total == before_pass:
            break

    return exercises


def _parse_duration(dur_str):
    dur_str = str(dur_str).strip().lower()
    if "m" in dur_str:
        try:
            return int(dur_str.replace("m", "").strip())
        except ValueError:
            pass
    if "-" in dur_str:
        parts = dur_str.replace("m", "").strip().split("-")
        try:
            return int(parts[-1].strip())
        except ValueError:
            pass
    try:
        return int(dur_str.replace("m", "").strip())
    except ValueError:
        return 3


def _select_scenarios(candidates, max_time, installed, focus="balanced", weaknesses=None):
    if max_time <= 0 or not candidates:
        return []

    weaknesses = weaknesses or []
    if focus in ("clicking", "tracking", "switching"):
        prefix = focus.capitalize() + "_"
        focused_candidates = []
        for score, scenario in candidates:
            targets = scenario.get(
                "recommendation_targets",
                [f"{scenario.get('category')}_{scenario.get('subcategory')}"]
            )
            matching = [target for target in targets if target.startswith(prefix)]
            if not matching:
                continue
            focused = dict(scenario)
            focused["category"], focused["subcategory"] = matching[0].split("_", 1)
            focused_candidates.append((score, focused))
        candidates = focused_candidates
        if not candidates:
            return []
    selected = []
    used_names = set()
    used_bases = set()
    remaining = max_time

    def take_from(pool, budget):
        nonlocal remaining
        spent = 0
        for _, scenario in pool:
            if spent >= budget or remaining <= 0:
                break
            name = scenario["name"]
            base = get_base_name(name)
            if name in used_names or (base != name and base in used_bases):
                continue
            duration = min(
                SCENARIO_DURATION_MAP.get(scenario.get("subcategory"), 3),
                budget - spent,
                remaining,
            )
            if duration <= 0:
                continue
            selected.append({
                "scenario": name,
                "category": scenario.get("category", "General"),
                "subcategory": scenario.get("subcategory", "Mixed"),
                "duration_min": duration,
                "installed": name.casefold() in installed,
                "tags": scenario.get("tags", []),
            })
            used_names.add(name)
            used_bases.add(base)
            spent += duration
            remaining -= duration
        return spent

    def extend_from(pool, amount):
        nonlocal remaining
        pool_names = {scenario["name"] for _, scenario in pool}
        eligible = [
            exercise for exercise in selected
            if exercise["scenario"] in pool_names
        ]
        index = 0
        while amount > 0 and remaining > 0 and eligible:
            eligible[index % len(eligible)]["duration_min"] += 1
            amount -= 1
            remaining -= 1
            index += 1

    allocation_groups = []
    if focus == "balanced":
        categories = [
            category for category in ("Clicking", "Tracking", "Switching")
            if any(s.get("category") == category for _, s in candidates)
        ]
        for category in categories:
            allocation_groups.append([
                item for item in candidates if item[1].get("category") == category
            ])
    elif focus in ("clicking", "tracking", "switching"):
        category = focus.capitalize()
        subcategories = []
        for _, scenario in candidates:
            if scenario.get("category") == category:
                subcategory = scenario.get("subcategory", "Mixed")
                if subcategory not in subcategories:
                    subcategories.append(subcategory)
        allocation_groups = [
            [item for item in candidates if item[1].get("category") == category
             and item[1].get("subcategory", "Mixed") == subcategory]
            for subcategory in subcategories
        ]
    else:
        seen = set()
        for weakness in weaknesses:
            key = (weakness.category, weakness.name)
            if key in seen:
                continue
            seen.add(key)
            pool = []
            target_key = f"{key[0]}_{key[1]}"
            for score, scenario in candidates:
                if target_key not in scenario.get(
                    "recommendation_targets",
                    [f"{scenario.get('category')}_{scenario.get('subcategory')}"]
                ):
                    continue
                targeted = dict(scenario)
                targeted["category"], targeted["subcategory"] = key
                pool.append((score, targeted))
            if pool:
                allocation_groups.append(pool)

    allocation_groups = [group for group in allocation_groups if group]
    if allocation_groups:
        base_budget, extra = divmod(max_time, len(allocation_groups))
        for index, group in enumerate(allocation_groups):
            budget = base_budget + (1 if index < extra else 0)
            spent = take_from(group, budget)
            if spent < budget:
                extend_from(group, budget - spent)

    if remaining > 0:
        fallback_candidates = candidates
        if focus in ("clicking", "tracking", "switching"):
            prefix = focus.capitalize() + "_"
            fallback_candidates = [
                item for item in candidates
                if any(
                    target.startswith(prefix)
                    for target in item[1].get(
                        "recommendation_targets",
                        [f"{item[1].get('category')}_{item[1].get('subcategory')}"]
                    )
                )
            ]
        take_from(fallback_candidates, remaining)

    # A recommendation should honor the requested training block even when a
    # narrowly focused catalog runs out of unique variants.
    index = 0
    while remaining > 0 and selected:
        selected[index % len(selected)]["duration_min"] += 1
        remaining -= 1
        index += 1

    return selected


def get_warmup_scenarios(
    scenarios, installed, total_minutes=4, rng=None, prioritize_installed=False,
    context="General / Fundamentals",
):
    if total_minutes <= 0:
        return []
    remaining = total_minutes
    prescribed = []
    installed_names = {name.casefold() for name in installed}
    preset = get_warmup_routine(context)
    for step in preset or []:
        if remaining <= 0:
            break
        duration = min(step["duration_min"], remaining)
        prescribed.append({
            "scenario": step["scenario"],
            "duration_min": duration,
            "installed": step["scenario"].casefold() in installed_names,
        })
        remaining -= duration
    if prescribed:
        if remaining > 0:
            prescribed[-1]["duration_min"] += remaining
        return prescribed
    rng = rng or random.Random()
    warmup_candidates = []
    for s in scenarios:
        if not s.get("official_recommended"):
            continue
        tags = s.get("tags", [])
        name_lower = s.get("name", "").lower()
        if any(t in tags for t in ["smooth", "tracking", "control"]) or "smooth" in name_lower:
            warmup_candidates.append(s)
        elif s.get("subcategory") in ("Precise", "Control") and s.get("category") == "Tracking":
            warmup_candidates.append(s)
    if not warmup_candidates:
        warmup_candidates = [s for s in scenarios if s.get("category") == "Tracking"]
    warmup_candidates = list(warmup_candidates)
    rng.shuffle(warmup_candidates)
    count = min(len(warmup_candidates), max(1, min(3, total_minutes)))
    base_duration, extra = divmod(total_minutes, count)
    return [
        {
            "scenario": scenario["name"],
            "duration_min": base_duration + (1 if index < extra else 0),
            "installed": scenario["name"].casefold() in installed,
        }
        for index, scenario in enumerate(warmup_candidates[:count])
    ]
