TRAINING_METHODS = [
    {
        "id": "adaptive_weakness",
        "mode": "focused",
        "category": "Adaptive",
        "title": "Adaptive weakness block",
        "summary": "A short recommendation chosen from current benchmark weakness, recent practice, and feedback.",
        "best_for": "Frequent focused practice when you want the app to decide the next useful skill.",
        "philosophy": "Small deliberate blocks preserve attention and let weak skills recur without abandoning maintenance.",
        "execution": ["Use the displayed technical cue.", "Complete only the prescribed runs.", "Record the recurring error before changing drills."],
        "avoid": "Do not restart weak attempts or turn a short block into an unplanned grind.",
        "focus": "weakest"
    },
    {
        "id": "clicking_focus",
        "mode": "focused",
        "category": "Adaptive",
        "title": "Clicking focus",
        "summary": "Short static, dynamic, or linear clicking practice selected at your current level.",
        "best_for": "Flick path, target confirmation, timing, and first-shot precision.",
        "philosophy": "Build a clean initial movement and controlled confirmation before compressing the time between clicks.",
        "execution": ["Keep paths direct.", "Confirm the target before clicking.", "Increase pace only while movement remains repeatable."],
        "avoid": "Do not spam, arc between targets, or trade accuracy for uncontrolled speed.",
        "focus": "clicking"
    },
    {
        "id": "tracking_focus",
        "mode": "focused",
        "category": "Adaptive",
        "title": "Tracking focus",
        "summary": "Short precise, reactive, or control-tracking practice selected from your current needs.",
        "best_for": "Smooth pursuit, reading direction changes, and maintaining contact while moving.",
        "philosophy": "React to visible movement, then settle into smooth contact instead of predicting the target.",
        "execution": ["Watch the target rather than the crosshair.", "React once to each direction change.", "Relax grip pressure between corrections."],
        "avoid": "Do not guess direction changes or stack repeated corrections after one miss.",
        "focus": "tracking"
    },
    {
        "id": "switching_focus",
        "mode": "focused",
        "category": "Adaptive",
        "title": "Target-switching focus",
        "summary": "Short speed, evasive, or stability switching practice selected at your current level.",
        "best_for": "Fast acquisition followed by stable target contact.",
        "philosophy": "Treat the switch and the stabilization as separate skills: move decisively, then match the target.",
        "execution": ["Choose the next target before leaving the current one.", "Move in a direct line.", "Stabilize without overcorrecting."],
        "avoid": "Do not leave targets early or carry excess tension through the stop.",
        "focus": "switching"
    },
    {
        "id": "weakness_routine",
        "mode": "routine",
        "category": "Fundamentals",
        "title": "Weakness-first routine",
        "summary": "A longer session weighted toward measured weakness with balanced support work.",
        "best_for": "Dedicated practice days when benchmark evidence identifies a clear limitation.",
        "philosophy": "Spend most training time on the limiting skill while retaining enough varied work to prevent narrow specialization.",
        "execution": ["Use 65 percent of training time on the primary weakness.", "Keep support categories in the session.", "Review quality before increasing difficulty."],
        "avoid": "Do not infer a weakness from one bad score or remove all maintenance work.",
        "focus": "weakest",
        "duration": 35
    },
    {
        "id": "balanced_fundamentals",
        "mode": "routine",
        "category": "Fundamentals",
        "title": "Balanced fundamentals",
        "summary": "Rank-appropriate clicking, tracking, and switching in one complete routine.",
        "best_for": "General development, incomplete benchmark data, or maintenance weeks.",
        "philosophy": "Broad exposure builds a stable base before specialization and provides evidence about real limitations.",
        "execution": ["Give every category a technical intention.", "Keep difficulty appropriate to rank.", "Finish before technique degrades."],
        "avoid": "Do not treat every exercise as a high-score test.",
        "focus": "balanced",
        "duration": 35
    },
    {
        "id": "speed_stopping",
        "mode": "routine",
        "category": "TacFPS",
        "title": "Speed and stopping",
        "summary": "Aimgud routine for raw acquisition speed and controlled deceleration.",
        "best_for": "TacFPS players whose initial flick is hesitant or who cannot stop cleanly at speed.",
        "philosophy": "Stopping power is a trainable limit. Use aggressive movement, accept some misses, and reacquire immediately.",
        "execution": ["Snap aggressively.", "Hold fire in scenarios that support it.", "Reacquire after a miss instead of polishing the path."],
        "avoid": "Do not slow the whole run merely to protect accuracy.",
        "preferred_routine": "TacFPS - Speed and Stopping",
        "duration": 35
    },
    {
        "id": "speed_precision",
        "mode": "routine",
        "category": "TacFPS",
        "title": "Speed-to-precision bridge",
        "summary": "Aimgud routine that carries raw speed into disciplined static acquisition.",
        "best_for": "Players who can move quickly or accurately, but cannot combine both reliably.",
        "philosophy": "Alternate speed-biased and accuracy-biased runs so the fast initial movement survives a cleaner final correction.",
        "execution": ["Perform speed runs first.", "Retain initial pace during accuracy runs.", "Use the stated accuracy bands rather than score alone."],
        "avoid": "Do not turn accuracy runs into slow target confirmation from the start.",
        "preferred_routine": "TacFPS - Speed-to-Precision",
        "duration": 35
    },
    {
        "id": "smooth_pathing",
        "mode": "routine",
        "category": "TacFPS",
        "title": "Smooth pathing",
        "summary": "Aimgud routine for direct lines, minimal correction, and controlled pursuit.",
        "best_for": "Curved flicks, shaky movement, and repeated correction near the target.",
        "philosophy": "Temporarily reduce pace to make efficient movement explicit, then preserve that path as speed returns.",
        "execution": ["Draw straight target-to-target paths.", "Use the fewest corrections possible.", "Keep pursuit smooth rather than score-driven."],
        "avoid": "Do not chase speed while the path remains uncontrolled.",
        "preferred_routine": "TacFPS - Smooth Pathing",
        "duration": 35
    },
    {
        "id": "deathmatch_complete",
        "mode": "deathmatch",
        "category": "Game transfer",
        "title": "Complete deathmatch cycle",
        "summary": "All eight focused Valorant deathmatches in the supplied order.",
        "best_for": "A full transfer session covering crosshair placement, accuracy, movement, peeking, and role practice.",
        "philosophy": "In-game mechanics improve through deliberate constraints, not by running around and chasing lobby placement.",
        "execution": ["Complete each block with its stated weapon constraint.", "Ignore lobby placement.", "Review one controllable cause after each death."],
        "avoid": "Do not play every match with the same vague goal of getting kills.",
        "deathmatch_blocks": ["crosshair_placement", "sheriff_accuracy_1", "movement_peeking", "sheriff_accuracy_2", "operator_or_weakness"]
    },
    {
        "id": "deathmatch_crosshair",
        "mode": "deathmatch",
        "category": "Game transfer",
        "title": "Crosshair-placement block",
        "summary": "Three rifle deathmatches using short bursts and deliberate crosshair placement.",
        "best_for": "Head-height consistency, corner width, and choosing the next plausible angle.",
        "philosophy": "Restrict shooting so placement errors stay visible instead of being hidden by a spray correction.",
        "execution": ["Use only 2-4 bullet bursts.", "Keep head height at all times.", "Adjust corner width for the expected peek."],
        "avoid": "Do not spray or judge success by kills.",
        "deathmatch_blocks": ["crosshair_placement"]
    },
    {
        "id": "deathmatch_accuracy",
        "mode": "deathmatch",
        "category": "Game transfer",
        "title": "First-bullet accuracy block",
        "summary": "Two Sheriff deathmatches with headshots and a full accuracy reset between attempts.",
        "best_for": "Pistol rounds, eco mechanics, and deliberate head acquisition.",
        "philosophy": "Removing follow-up spam makes the initial acquisition and weapon reset the entire task.",
        "execution": ["Shoot only at the head.", "Wait for the Sheriff to settle after a miss.", "Carry clean movement into each shot."],
        "avoid": "Do not body spam or fire before accuracy has reset.",
        "deathmatch_blocks": ["sheriff_accuracy_1", "sheriff_accuracy_2"]
    },
    {
        "id": "deathmatch_movement",
        "mode": "deathmatch",
        "category": "Game transfer",
        "title": "Movement and peeking block",
        "summary": "Two rifle deathmatches for angle isolation and deliberate peek selection.",
        "best_for": "Overexposure, weak counter-strafing, and using one peek style for every duel.",
        "philosophy": "Clear one threat at a time and select movement based on the information and geometry of the duel.",
        "execution": ["Isolate each angle.", "Practise short, wide, jiggle, and crouch peeks.", "Review whether burst or spray fit each loss."],
        "avoid": "Do not swing through several uncleared angles at once.",
        "deathmatch_blocks": ["movement_peeking"]
    }
]

METHOD_MAP = {method["id"]: method for method in TRAINING_METHODS}


def methods_for_mode(mode: str) -> list[dict]:
    return [method for method in TRAINING_METHODS if method["mode"] == mode]
