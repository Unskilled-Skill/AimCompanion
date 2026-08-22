from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Score:
    benchmark_name: str
    scenario: str
    category: str
    subcategory: str
    difficulty: str
    score: float
    timestamp: datetime
    kills: int = 0
    hits: int = 0
    misses: int = 0
    fight_time: float = 0.0
    avg_ttk: float = 0.0
    accuracy: float = 0.0
    avg_fps: float = 0.0
    resolution: str = ""

    @property
    def energy(self) -> float:
        from models.benchmark import score_to_energy
        return score_to_energy(self.benchmark_name or self.scenario, self.score)


@dataclass
class BenchmarkInfo:
    name: str
    scenario: str
    category: str
    subcategory: str
    difficulty: str
    latest_score: float = 0.0
    best_score: float = 0.0
    attempts: int = 0
    energy: float = 0.0
    tier: str = "Iron"

    def update_from_score(self, score: Score):
        self.attempts += 1
        self.latest_score = score.score
        if score.score > self.best_score:
            self.best_score = score.score
        from models.benchmark import score_to_energy, energy_to_tier
        self.energy = score_to_energy(self.name, self.best_score)
        self.tier = energy_to_tier(self.energy)


@dataclass
class SubcategoryScore:
    name: str
    category: str
    benchmarks: list[BenchmarkInfo] = field(default_factory=list)
    combined_score: float = 0.0
    energy: float = 0.0
    tier: str = "Iron"

    def recalculate(self):
        from models.benchmark import energy_to_tier, score_to_energy
        scored = [b for b in self.benchmarks if b.best_score > 0]
        for b in scored:
            b.energy = score_to_energy(b.name, b.best_score)
            b.tier = energy_to_tier(b.energy)
        self.combined_score = sum(b.best_score for b in self.benchmarks)
        if scored:
            self.energy = sum(b.energy for b in scored) / len(scored)
        else:
            self.energy = 0.0
        self.tier = energy_to_tier(self.energy)


@dataclass
class CategoryScore:
    name: str
    subcategories: list[SubcategoryScore] = field(default_factory=list)
    combined_score: float = 0.0
    energy: float = 0.0
    tier: str = "Iron"

    def recalculate(self):
        for sc in self.subcategories:
            sc.recalculate()
        if self.subcategories:
            self.energy = sum(sc.energy for sc in self.subcategories) / len(self.subcategories)
        else:
            self.energy = 0.0
        self.combined_score = sum(sc.combined_score for sc in self.subcategories)
        from models.benchmark import energy_to_tier
        self.tier = energy_to_tier(self.energy)


@dataclass
class PlayerProfile:
    username: str = ""
    difficulty: str = "Novice"
    categories: list[CategoryScore] = field(default_factory=list)
    overall_score: float = 0.0
    overall_energy: float = 0.0
    overall_tier: str = "Iron"
    last_updated: datetime = None

    def recalculate(self):
        for cat in self.categories:
            cat.recalculate()
        if self.categories:
            self.overall_energy = sum(cat.energy for cat in self.categories) / len(self.categories)
        else:
            self.overall_energy = 0.0
        self.overall_score = sum(c.combined_score for c in self.categories)
        from models.benchmark import energy_to_tier
        self.overall_tier = energy_to_tier(self.overall_energy)

    def get_weakest_subcategories(
        self, n: int = 5, measured_only: bool = True
    ) -> list[SubcategoryScore]:
        all_subs = []
        for cat in self.categories:
            for sub in cat.subcategories:
                if measured_only and not any(b.best_score > 0 for b in sub.benchmarks):
                    continue
                all_subs.append(sub)
        all_subs.sort(key=lambda s: s.energy)
        return all_subs[:n]

    def get_strongest_subcategories(self, n: int = 3) -> list[SubcategoryScore]:
        all_subs = []
        for cat in self.categories:
            for sub in cat.subcategories:
                all_subs.append(sub)
        all_subs.sort(key=lambda s: s.energy, reverse=True)
        return all_subs[:n]
