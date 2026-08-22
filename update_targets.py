import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
BENCHMARKS_PATH = os.path.join(DATA_DIR, "benchmarks.json")

new_targets = {
    "VT Pasu Novice S5": {"Iron": 555, "Bronze": 660, "Silver": 745, "Gold": 800},
    "VT Popcorn Novice S5": {"Iron": 390, "Bronze": 500, "Silver": 600, "Gold": 720},
    "VT 1w4ts Novice S5": {"Iron": 820, "Bronze": 915, "Silver": 1010, "Gold": 1110},
    "VT ww3t Novice S5": {"Iron": 990, "Bronze": 1090, "Silver": 1190, "Gold": 1290},
    "VT Frogtagon Novice S5": {"Iron": 620, "Bronze": 740, "Silver": 850, "Gold": 980},
    "VT Floating Heads Novice S5": {"Iron": 375, "Bronze": 460, "Silver": 540, "Gold": 640},
    "VT PGT Novice S5": {"Iron": 1900, "Bronze": 2325, "Silver": 2775, "Gold": 3050},
    "VT Snake Track Novice S5": {"Iron": 2400, "Bronze": 2750, "Silver": 3125, "Gold": 3425},
    "VT Aether Novice S5": {"Iron": 1525, "Bronze": 1900, "Silver": 2250, "Gold": 2650},
    "VT Ground Novice S5": {"Iron": 2100, "Bronze": 2500, "Silver": 2825, "Gold": 3100},
    "VT Raw Control Novice S5": {"Iron": 2125, "Bronze": 2550, "Silver": 2975, "Gold": 3450},
    "VT Controlsphere Novice S5": {"Iron": 1575, "Bronze": 1950, "Silver": 2400, "Gold": 2900},
    "VT DotTS Novice S5": {"Iron": 845, "Bronze": 940, "Silver": 1030, "Gold": 1090},
    "VT EddieTS Novice S5": {"Iron": 640, "Bronze": 730, "Silver": 810, "Gold": 890},
    "VT DriftTS Novice S5": {"Iron": 315, "Bronze": 355, "Silver": 390, "Gold": 430},
    "VT FlyTS Novice S5": {"Iron": 420, "Bronze": 460, "Silver": 500, "Gold": 535},
    "VT ControlTS Novice S5": {"Iron": 340, "Bronze": 380, "Silver": 420, "Gold": 450},
    "VT Penta Bounce Novice S5": {"Iron": 290, "Bronze": 340, "Silver": 390, "Gold": 445},
}

with open(BENCHMARKS_PATH, 'r') as f:
    data = json.load(f)

for item in data:
    if item['scenario'] in new_targets:
        item['targets'] = new_targets[item['scenario']]

with open(BENCHMARKS_PATH, 'w') as f:
    json.dump(data, f, indent=4)

print("Updated targets successfully!")
