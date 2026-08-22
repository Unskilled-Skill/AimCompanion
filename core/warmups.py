RECOMMENDED_WARMUP_ROUTINE = [
    {"scenario": "Close Long Strafes Invincible", "duration_min": 5,
     "category": "Tracking", "subcategory": "Reactive",
     "cue": "Stay relaxed and match direction changes smoothly; do not chase score yet."},
    {"scenario": "1Wall9000Targets", "duration_min": 3,
     "category": "Clicking", "subcategory": "Static",
     "cue": "Use clean straight paths and confirm each target before clicking."},
    {"scenario": "Bounce 180", "duration_min": 3,
     "category": "Clicking", "subcategory": "Dynamic",
     "cue": "Read the target arc first, then click with controlled timing."},
    {"scenario": "Close FS Dodge", "duration_min": 3,
     "category": "Tracking", "subcategory": "Reactive",
     "cue": "Keep the hand loose and react without predicting rapid strafes."},
]

RECOMMENDED_WARMUP_MINUTES = sum(
    step["duration_min"] for step in RECOMMENDED_WARMUP_ROUTINE
)

GAME_WARMUP_ROUTINES = {
    "Apex Legends": [
        {"scenario": "fuglaaXYLongstrafes", "duration_min": 5,
         "category": "Tracking", "subcategory": "Reactive",
         "cue": "Match long strafes fairly and smoothly; correct only after reading the turn."},
        {"scenario": "CloseLongStrafes", "duration_min": 5,
         "category": "Tracking", "subcategory": "Reactive",
         "cue": "Stay relaxed during close direction changes and keep continuous contact."},
    ],
    "Valorant & Counterstrike": [
        {"scenario": "Microshot Speed", "duration_min": 3,
         "category": "Clicking", "subcategory": "Static",
         "cue": "Acquire quickly, stop cleanly, and avoid dragging the crosshair through targets."},
        {"scenario": "1wall5targets_pasu", "duration_min": 4,
         "category": "Clicking", "subcategory": "Dynamic",
         "cue": "Track each moving target briefly, then commit to a clean timed flick."},
        {"scenario": "TileFrenzyMini", "duration_min": 3,
         "category": "Clicking", "subcategory": "Static",
         "cue": "Build speed with compact motions while keeping the hand and shoulder loose."},
    ],
}


def get_warmup_routine(context: str = "Aim training"):
    if context in ("Aim training", "General / Fundamentals", ""):
        return RECOMMENDED_WARMUP_ROUTINE
    return GAME_WARMUP_ROUTINES.get(context)


def warmup_minutes(context: str = "Aim training") -> int:
    routine = get_warmup_routine(context)
    return sum(step["duration_min"] for step in routine) if routine else 0
