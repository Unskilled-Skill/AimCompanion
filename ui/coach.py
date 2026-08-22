from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from models.database import Database
from models.score import PlayerProfile
from models.benchmark import TIERS, energy_to_tier
from core.recommender import get_scenario_info


class CoachWidget(QWidget):
    def __init__(self, profile: PlayerProfile, db: Database):
        super().__init__()
        self.profile = profile
        self.db = db
        self._build_ui()
        self._generate_advice()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("AI Coach")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(header)

        subtitle = QLabel("Personalized analysis and recommendations")
        subtitle.setStyleSheet("color: #7f849c; font-style: italic;")
        subtitle.setFont(QFont("Segoe UI", 10))
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(12)
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

    def _generate_advice(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sections = [
            self._overall_assessment(),
            self._weakness_analysis(),
            self._stopping_power_analysis(),
            self._stagnation_check(),
            self._consistency_analysis(),
            self._routine_priority(),
            self._game_transfer_advice(),
            self._benchmark_suggestion(),
        ]

        for title, content, color in sections:
            card = self._advice_card(title, content, color)
            self.scroll_layout.addWidget(card)

        self.scroll_layout.addStretch()

    def _advice_card(self, title, content, color):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #1e1e2e;
                border-radius: 10px;
                padding: 16px;
                border: 1px solid #313244;
                border-left: 4px solid {color};
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(8)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {color};")
        layout.addWidget(title_lbl)

        content_lbl = QLabel(content)
        content_lbl.setWordWrap(True)
        content_lbl.setFont(QFont("Segoe UI", 10))
        content_lbl.setStyleSheet("color: #cdd6f4; line-height: 1.5;")
        layout.addWidget(content_lbl)

        return frame

    def _overall_assessment(self):
        tier = self.profile.overall_tier
        energy = self.profile.overall_energy
        sessions = self.db.get_total_sessions()
        attempts = self.db.get_total_attempts()

        lines = [f"Current tier: {tier} ({energy:.1f} energy)"]
        lines.append(f"Total attempts: {attempts}")
        if sessions:
            lines.append(f"Training sessions: {sessions}")

        cats = self.profile.categories
        if cats:
            best = max(cats, key=lambda c: c.energy)
            worst = min(cats, key=lambda c: c.energy)
            lines.append(f"Best category: {best.name} ({best.tier})")
            lines.append(f"Weakest category: {worst.name} ({worst.tier})")

        color = "#44ff88"
        if energy < 30:
            color = "#ff9944"
        if energy < 20:
            color = "#ff4444"

        return "Overall Assessment", "\n".join(lines), color

    def _weakness_analysis(self):
        lines = []
        for cat in self.profile.categories:
            if not cat.subcategories:
                continue
            weakest = min(cat.subcategories, key=lambda s: s.energy)
            energy = weakest.energy
            tier = energy_to_tier(energy)
            lines.append(f"{cat.name}/{weakest.name}: {weakest.combined_score:.0f} ({tier})")

        # Specific advice based on subcategory type (research-backed)
        subcat_advice = {
            "Static": "Static: Focus on precision over speed. Aim for 90%+ accuracy before increasing speed. "
                      "Use undershoot bias — aim slightly short, then micro-adjust. "
                      "For tacFPS: Don't worry about speed, worry about clean flicks and smooth mouse control.",
            "Dynamic": "Dynamic: Practice smooth tracking. Don't predict direction changes, react to them. "
                       "Use the dead stop technique when flicking. Keep crosshair at head level.",
            "Linear": "Linear: Work on straight-line flicks. Use a consistent mouse path. "
                      "Wrist for short flicks, arm for long ones. Practice counter-strafing.",
            "Control": "Control: Prioritize smoothness over speed. Aim for consistent tracking patterns. "
                       "Make heavy use of both smooth wrist and arm movements in a slow and controlled manner.",
            "Precise": "Precise: Small, controlled movements. Focus on micro-adjustments. "
                       "If target too small to stay smooth, use an easier version. Goal: As high accuracy as you can get.",
            "Reactive": "Reactive: React to target direction changes. Stay relaxed, don't tense up. "
                        "Use large arm movements for tracking. Try the 80% version if it's too fast.",
            "Speed": "Speed: Build up gradually. Start slow, maintain accuracy, then increase speed. "
                     "Aim for >90% accuracy. Only increase speed after accuracy is consistent.",
            "Evasive": "Evasive: Practice reading target movement patterns. Stay smooth under pressure. "
                       "Don't spray and don't run and gun. Be honest with yourself about accuracy.",
            "Stability": "Stability: Focus on consistent, controlled movements. Don't over-flick. "
                         "Use rebound flick technique for long-distance targets.",
        }

        for cat in self.profile.categories:
            if not cat.subcategories:
                continue
            weakest = min(cat.subcategories, key=lambda s: s.energy)
            if weakest.name in subcat_advice:
                lines.append("")
                lines.append(subcat_advice[weakest.name])

        return "Weakness Analysis", "\n".join(lines), "#ff9944"

    def _stagnation_check(self):
        lines = []
        has_history = False

        for cat in self.profile.categories:
            if not cat.subcategories:
                continue
            for sub in cat.subcategories:
                for bench in sub.benchmarks:
                    history = self.db.get_score_history(bench.name)
                    if len(history) >= 3:
                        has_history = True
                        recent = [h.score for h in history[-5:]]
                        older = [h.score for h in history[:-5]] if len(history) > 5 else recent[:1]

                        recent_avg = sum(recent) / len(recent)
                        older_avg = sum(older) / len(older) if older else recent_avg
                        change_pct = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0

                        if abs(change_pct) < 3 and len(history) > 5:
                            lines.append(f"STAGNANT: {bench.name} ({change_pct:+.1f}%)")
                            lines.append("  -> Try different scenarios or increase difficulty")

        if not has_history:
            lines.append("Not enough data yet. Keep training to enable stagnation detection.")
        elif not lines:
            lines.append("Good news! No stagnation detected in your recent scores.")
            lines.append("Your training is producing consistent improvement.")

        return "Stagnation Check", "\n".join(lines), "#ffaa00"

    def _consistency_analysis(self):
        lines = []
        sessions = self.db.get_sessions(limit=20)

        if len(sessions) < 3:
            lines.append("Log more sessions to get consistency insights.")
        else:
            from datetime import datetime
            dates = [datetime.fromisoformat(s["timestamp"]).date() for s in sessions]
            unique_dates = len(set(dates))
            total_days = (dates[0] - dates[-1]).days + 1 if len(dates) > 1 else 1
            freq = unique_dates / max(total_days, 1)

            lines.append(f"Trained {unique_dates} days in last {total_days} days")
            lines.append(f"Consistency: {freq:.0%}")

            if freq >= 0.5:
                lines.append("Great consistency! You're training regularly.")
            elif freq >= 0.3:
                lines.append("Decent consistency. Try to train a bit more regularly.")
            else:
                lines.append("Your training is inconsistent. Aim for 3-4 sessions per week.")

            total_min = sum(s["duration_minutes"] for s in sessions)
            avg_min = total_min / max(len(sessions), 1)
            lines.append(f"Average session: {avg_min:.0f} minutes")

        return "Consistency", "\n".join(lines), "#4a9eff"

    def _routine_priority(self):
        lines = []
        priorities = []

        for cat in self.profile.categories:
            if not cat.subcategories:
                continue
            for sub in cat.subcategories:
                energy = sub.energy
                tier = energy_to_tier(energy)
                priorities.append((cat.name, sub.name, energy, tier))

        priorities.sort(key=lambda x: x[2])

        lines.append("Training priority (weakest first):")
        for i, (cat, sub, energy, tier) in enumerate(priorities[:5], 1):
            lines.append(f"{i}. {cat}/{sub} - {tier} ({energy:.1f} energy)")

        return "Training Priority", "\n".join(lines), "#bb88ff"

    def _benchmark_suggestion(self):
        lines = []
        sessions = self.db.get_total_sessions()
        attempts = self.db.get_total_attempts()

        if sessions < 3:
            lines.append("Log at least 3 training sessions before re-benchmarking.")
        elif attempts < 100:
            lines.append("Get more score attempts for accurate re-benchmark timing.")
        else:
            last_bench_attempt = attempts
            if last_bench_attempt > 50:
                lines.append("You've logged many attempts. Consider re-benchmarking soon.")
                lines.append("This will capture your improvement and update your tier.")
            else:
                lines.append("Keep training for another week before re-benchmarking.")

            lines.append("")
            lines.append("When to re-benchmark:")
            lines.append("- After 2-3 weeks of consistent training")
            lines.append("- When you feel noticeably better at your weak areas")
            lines.append("- Before starting a new training cycle")

        return "Re-Benchmark Suggestion", "\n".join(lines), "#44ff88"

    def _stopping_power_analysis(self):
        lines = []
        # Analyze clicking subcategories for stopping power
        for cat in self.profile.categories:
            if cat.name != "Clicking":
                continue
            for sub in cat.subcategories:
                if sub.name == "Static":
                    energy = sub.energy
                    tier = energy_to_tier(energy)
                    if energy < 30:
                        lines.append(f"Static ({tier}): Your stopping power needs work.")
                        lines.append("  -> You're likely overflicking or underflicking consistently.")
                        lines.append("  -> Try: Undershoot bias — aim slightly short, then micro-adjust.")
                        lines.append("  -> Try: Dead stop technique — flick to target and stop dead.")
                        lines.append("  -> Goal: Clean flicks, not fast ones. Speed comes later.")
                    elif energy < 40:
                        lines.append(f"Static ({tier}): Decent stopping power. Push for consistency.")
                        lines.append("  -> Focus on making clean lines target to target.")
                        lines.append("  -> Practice reflex flicks to improve reaction time.")
                    else:
                        lines.append(f"Static ({tier}): Good stopping power! Fine-tune speed.")
                        lines.append("  -> You can now push for faster flicks while maintaining accuracy.")
                elif sub.name == "Linear":
                    energy = sub.energy
                    tier = energy_to_tier(energy)
                    if energy < 30:
                        lines.append(f"Linear ({tier}): Linear aim needs work.")
                        lines.append("  -> Focus on straight-line flicks. Use consistent mouse path.")
                        lines.append("  -> Practice counter-strafing while aiming.")
                        lines.append("  -> Wrist for short flicks, arm for long ones.")
                elif sub.name == "Dynamic":
                    energy = sub.energy
                    tier = energy_to_tier(energy)
                    if energy < 30:
                        lines.append(f"Dynamic ({tier}): Dynamic aim needs work.")
                        lines.append("  -> Practice leading your shots slightly.")
                        lines.append("  -> Focus on smooth tracking, not prediction.")
                        lines.append("  -> React to target movement, don't anticipate.")

        if not lines:
            lines.append("Clicking scores look solid. Focus on other weak areas.")

        lines.append("")
        lines.append("Key principle: Stopping power = precision + speed.")
        lines.append("Don't rush. Build accuracy first, then add speed.")

        return "Stopping Power Analysis", "\n".join(lines), "#bb88ff"

    def _game_transfer_advice(self):
        lines = []
        # Check if user has game-specific scenarios
        game_scenarios = [s for s in self.db.get_score_history("all") if s]
        if len(game_scenarios) < 5:
            lines.append("Log more Kovaak's scores to get game transfer advice.")
        else:
            lines.append("After every Kovaak's session, spend 10-15 min in Deathmatch.")
            lines.append("Focus on applying ONE technique per session.")
            lines.append("")
            lines.append("5-min VOD review > 5 more minutes of Kovaak's.")
            lines.append("Record your games. Watch for:")
            lines.append("- Are you overflicking? Underflicking?")
            lines.append("- Is your tracking smooth or jittery?")
            lines.append("- Are you counter-strafing properly?")
            lines.append("")
            lines.append("Common mistake: Rushing long flicks in-game.")
            lines.append("Take your time. Wrist for short flicks, arm for long ones.")

        return "Game Transfer", "\n".join(lines), "#ff9944"

    def update_profile(self, profile):
        self.profile = profile
        self._generate_advice()
