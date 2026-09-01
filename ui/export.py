import csv
import os
import shutil
import tempfile
import zipfile
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QFrame
)
from PyQt6.QtGui import QFont

from models.database import Database
from models.score import PlayerProfile
from models.benchmark import score_to_energy, energy_to_tier
from models.config import CONFIG_PATH


class ExportWidget(QWidget):
    def __init__(self, profile: PlayerProfile, db: Database, on_restore=None):
        super().__init__()
        self.profile = profile
        self.db = db
        self.on_restore = on_restore
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        cards_layout = QHBoxLayout()

        csv_card = self._export_card(
            "Export Scores (CSV)",
            "Export all your benchmark scores to a CSV file.\nCan be opened in Excel or Google Sheets.",
            "#4a9eff",
            self._export_scores_csv
        )
        cards_layout.addWidget(csv_card)

        progress_card = self._export_card(
            "Export Progress Report",
            "Generate a text report of your current tier,\nweaknesses, and recommendations.",
            "#44ff88",
            self._export_progress_report
        )
        cards_layout.addWidget(progress_card)

        history_card = self._export_card(
            "Export Session History",
            "Export your training session log\nto a CSV file.",
            "#ff9944",
            self._export_sessions_csv
        )
        cards_layout.addWidget(history_card)

        backup_card = QFrame()
        backup_card.setObjectName("exportCard")
        backup_layout = QVBoxLayout(backup_card)
        backup_title = QLabel("Full Backup")
        backup_title.setStyleSheet("color: #cba6f7; font-weight: bold;")
        backup_layout.addWidget(backup_title)
        backup_layout.addWidget(QLabel("Save or restore scores, sessions, routines, and settings."))
        backup_btn = QPushButton("Create backup")
        backup_btn.setObjectName("quietButton")
        backup_btn.clicked.connect(self._backup_all)
        restore_btn = QPushButton("Restore backup")
        restore_btn.setObjectName("quietButton")
        restore_btn.clicked.connect(self._restore_all)
        backup_layout.addWidget(backup_btn)
        backup_layout.addWidget(restore_btn)
        cards_layout.addWidget(backup_card)

        layout.addLayout(cards_layout)

        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("exportPreview")
        self.preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_frame.setStyleSheet("QFrame#exportPreview { background-color: #11192b; border: 1px solid #263149; border-radius: 10px; }")
        self.preview_layout = QVBoxLayout(self.preview_frame)
        layout.addWidget(self.preview_frame, stretch=1)

    def _export_card(self, title, desc, color, callback):
        frame = QFrame()
        frame.setObjectName("exportCard")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame#exportCard { background-color: #11192b; border-radius: 10px; border: 1px solid #263149; }
        """)
        layout = QVBoxLayout(frame)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {color};")
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("color: #aaa;")
        layout.addWidget(desc_lbl)

        btn = QPushButton("Export")
        btn.setObjectName("quietButton")
        btn.clicked.connect(callback)
        layout.addWidget(btn)

        return frame

    def _export_scores_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Scores", "kovaaks_scores.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        scores = self.db.get_all_scores()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Benchmark", "Scenario", "Category", "Subcategory",
                           "Difficulty", "Score", "Energy", "Tier", "Timestamp"])
            for s in scores:
                e = score_to_energy(s.benchmark_name, s.score)
                tier = energy_to_tier(e)
                writer.writerow([
                    s.benchmark_name, s.scenario, s.category, s.subcategory,
                    s.difficulty, f"{s.score:.1f}", f"{e:.1f}", tier,
                    s.timestamp.isoformat()
                ])

        self._show_preview(f"Exported {len(scores)} scores to:\n{path}")

    def _export_progress_report(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Report", "aim_progress_report.txt", "Text Files (*.txt)"
        )
        if not path:
            return

        lines = []
        lines.append("=" * 50)
        lines.append("  VOLTAIC S5 BENCHMARK PROGRESS REPORT")
        lines.append(f"  Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("=" * 50)
        lines.append("")

        lines.append(f"OVERALL TIER: {self.profile.overall_tier}")
        if self.profile.overall_energy is None:
            lines.append("OVERALL ENERGY: UNAVAILABLE (complete all nine subcategories)")
        else:
            lines.append(f"OVERALL ENERGY: {self.profile.overall_energy:.1f}")
        lines.append("")

        lines.append("CATEGORY BREAKDOWN:")
        lines.append("-" * 40)
        for cat in self.profile.categories:
            lines.append(
                f"  {cat.name}: {cat.combined_score:.0f} combined score "
                "(local compatibility view)"
            )
            if hasattr(cat, 'subcategories') and cat.subcategories:
                for sub in cat.subcategories:
                    if sub.energy > 0:
                        lines.append(
                            f"    {sub.name}: {sub.energy:.1f} official energy "
                            f"({sub.tier}); {sub.combined_score:.0f} combined score"
                        )
                    else:
                        lines.append(
                            f"    {sub.name}: Unmeasured; "
                            f"{sub.combined_score:.0f} combined score"
                        )
        lines.append("")

        lines.append("WEAKNESSES (sorted by priority):")
        lines.append("-" * 40)
        all_subs = []
        for cat in self.profile.categories:
            if hasattr(cat, 'subcategories') and cat.subcategories:
                for sub in cat.subcategories:
                    all_subs.append((cat.name, sub))

        all_subs.sort(key=lambda x: x[1].energy)
        for i, (cat, sub) in enumerate(all_subs, 1):
            lines.append(f"  {i}. {cat}/{sub.name}: {sub.combined_score:.0f} ({sub.tier})")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        self._show_preview(f"Report exported to:\n{path}")

    def _export_sessions_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Sessions", "training_sessions.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        sessions = self.db.get_sessions(limit=None)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Duration (min)", "Focus", "Notes"])
            for s in sessions:
                writer.writerow([
                    s["timestamp"][:16],
                    s["duration_minutes"],
                    s["focus"],
                    s.get("notes", "")
                ])

        self._show_preview(f"Exported {len(sessions)} sessions to:\n{path}")

    def _show_preview(self, message):
        while self.preview_layout.count():
            item = self.preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl = QLabel(message)
        lbl.setStyleSheet("color: #44ff88; font-size: 12px;")
        self.preview_layout.addWidget(lbl)

    def _backup_all(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Create Full Backup", "aim_companion_backup.zip", "ZIP Files (*.zip)"
        )
        if not path:
            return
        with tempfile.TemporaryDirectory() as directory:
            db_snapshot = os.path.join(directory, "kovaaks.db")
            self.db.backup_to(db_snapshot)
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(db_snapshot, "kovaaks.db")
                if os.path.exists(CONFIG_PATH):
                    archive.write(CONFIG_PATH, "config.json")
        self._show_preview(f"Full backup created:\n{path}")

    def _restore_all(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Restore Full Backup", "", "ZIP Files (*.zip)"
        )
        if not path:
            return
        answer = QMessageBox.question(
            self, "Restore backup?",
            "This replaces the current scores, sessions, routines, and settings. "
            "Create a backup first if you may need them.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            with tempfile.TemporaryDirectory() as directory:
                with zipfile.ZipFile(path, "r") as archive:
                    names = set(archive.namelist())
                    if "kovaaks.db" not in names:
                        raise ValueError("Backup does not contain kovaaks.db")
                    archive.extract("kovaaks.db", directory)
                    self.db.restore_from(os.path.join(directory, "kovaaks.db"))
                    if "config.json" in names:
                        archive.extract("config.json", directory)
                        shutil.copy2(os.path.join(directory, "config.json"), CONFIG_PATH)
            if self.on_restore:
                self.on_restore()
            self._show_preview(f"Backup restored:\n{path}")
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            QMessageBox.critical(self, "Restore failed", str(error))

    def update_profile(self, profile):
        self.profile = profile
