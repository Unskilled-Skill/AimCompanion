"""One conclusion-first home for rank, skill, benchmark, and history views."""

from PyQt6.QtWidgets import QFrame, QLabel, QTabWidget, QVBoxLayout, QWidget


class ProgressHub(QTabWidget):
    TAB_NAMES = ("Summary", "Skills", "Benchmarks", "History")

    def __init__(self, summary_widget, skills_widget, benchmarks_widget, history_widget, parent=None):
        super().__init__(parent)
        summary = QWidget()
        self.summary_layout = QVBoxLayout(summary)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        conclusion_panel = QFrame()
        conclusion_panel.setObjectName("panel")
        conclusion_layout = QVBoxLayout(conclusion_panel)
        conclusion_layout.addWidget(QLabel("What your progress means"))
        self.conclusion = QLabel("Complete benchmarks to establish your rank.")
        self.conclusion.setWordWrap(True)
        self.conclusion.setAccessibleName("Progress conclusion")
        conclusion_layout.addWidget(self.conclusion)
        self.summary_layout.addWidget(conclusion_panel)
        self.chart_container = summary_widget
        self.summary_layout.addWidget(self.chart_container, 1)
        for name, widget in zip(
            self.TAB_NAMES,
            (summary, skills_widget, benchmarks_widget, history_widget),
        ):
            self.addTab(widget, name)

    def tab_names(self):
        return tuple(self.tabText(index) for index in range(self.count()))

    def set_view_model(self, view_model):
        missing = len(view_model.missing_subcategories)
        completeness = (
            f"Benchmark incomplete · {missing} missing subcategories. "
            if missing else "All required subcategories measured. "
        )
        self.conclusion.setText(
            f"{view_model.conclusion}\n{completeness}"
            f"Definition: {view_model.definition_version}"
        )
