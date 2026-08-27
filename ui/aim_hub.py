from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.recommender import DEATHMATCH_GUIDE, TACFPS_GUIDE
from core.training_methods import METHOD_MAP, TRAINING_METHODS


MODE_LABELS = {
    "focused": "Focused block",
    "routine": "Full routine",
    "deathmatch": "Game transfer",
}


class AimHubWidget(QWidget):
    """A searchable method browser with a direct path into training."""

    train_requested = pyqtSignal(str)

    def __init__(self, profile=None, db=None, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.db = db
        self.current_method_id = "adaptive_weakness"
        self._build_ui()
        self._filter_methods()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        nav = QFrame()
        nav.setObjectName("methodNav")
        nav.setFixedWidth(300)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(16, 16, 16, 16)
        nav_layout.setSpacing(10)

        title = QLabel("Choose how to train")
        title.setObjectName("smallTitle")
        nav_layout.addWidget(title)
        intro = QLabel("Pick the outcome and practice philosophy that fit today's session.")
        intro.setObjectName("mutedText")
        intro.setWordWrap(True)
        nav_layout.addWidget(intro)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search methods")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_methods)
        nav_layout.addWidget(self.search_input)

        self.category_combo = QComboBox()
        self.category_combo.addItem("All philosophies", "")
        for category in dict.fromkeys(m["category"] for m in TRAINING_METHODS):
            self.category_combo.addItem(category, category)
        self.category_combo.currentIndexChanged.connect(self._filter_methods)
        nav_layout.addWidget(self.category_combo)

        self.method_list = QListWidget()
        self.method_list.setObjectName("methodList")
        self.method_list.setSpacing(2)
        self.method_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.method_list.currentItemChanged.connect(self._method_selected)
        nav_layout.addWidget(self.method_list, 1)
        root.addWidget(nav)

        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(24, 18, 28, 24)
        detail_layout.setSpacing(12)

        self.method_eyebrow = QLabel()
        self.method_eyebrow.setObjectName("methodEyebrow")
        detail_layout.addWidget(self.method_eyebrow)

        self.method_title = QLabel()
        self.method_title.setObjectName("methodTitle")
        self.method_title.setWordWrap(True)
        detail_layout.addWidget(self.method_title)

        self.method_summary = QLabel()
        self.method_summary.setObjectName("methodSummary")
        self.method_summary.setWordWrap(True)
        detail_layout.addWidget(self.method_summary)

        action_row = QHBoxLayout()
        self.train_button = QPushButton("Use this method")
        self.train_button.setObjectName("primaryButton")
        self.train_button.clicked.connect(self._request_training)
        action_row.addWidget(self.train_button)
        self.source_button = QPushButton("Open original guide")
        self.source_button.setObjectName("secondaryButton")
        self.source_button.clicked.connect(self._open_source)
        action_row.addWidget(self.source_button)
        action_row.addStretch()
        detail_layout.addLayout(action_row)

        detail_layout.addSpacing(8)
        detail_layout.addWidget(self._section_heading("BEST FOR"))
        self.best_for_label = self._body_label()
        detail_layout.addWidget(self.best_for_label)

        detail_layout.addWidget(self._section_heading("WHY THIS WORKS"))
        self.philosophy_label = self._body_label()
        detail_layout.addWidget(self.philosophy_label)

        detail_layout.addWidget(self._section_heading("HOW TO RUN IT"))
        self.execution_label = self._body_label()
        detail_layout.addWidget(self.execution_label)

        self.session_heading = self._section_heading("SESSION CONTENT")
        detail_layout.addWidget(self.session_heading)
        self.session_label = self._body_label()
        detail_layout.addWidget(self.session_label)

        self.avoid_frame = QFrame()
        self.avoid_frame.setObjectName("methodWarning")
        avoid_layout = QVBoxLayout(self.avoid_frame)
        avoid_layout.setContentsMargins(12, 10, 12, 10)
        avoid_layout.setSpacing(4)
        avoid_title = QLabel("WATCH FOR")
        avoid_title.setObjectName("fieldLabel")
        avoid_layout.addWidget(avoid_title)
        self.avoid_label = self._body_label()
        avoid_layout.addWidget(self.avoid_label)
        detail_layout.addWidget(self.avoid_frame)
        detail_layout.addStretch()

        self.detail_scroll.setWidget(detail)
        root.addWidget(self.detail_scroll, 1)

    @staticmethod
    def _section_heading(text):
        label = QLabel(text)
        label.setObjectName("methodSection")
        return label

    @staticmethod
    def _body_label():
        label = QLabel()
        label.setObjectName("methodBody")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _filter_methods(self, *args):
        query = self.search_input.text().strip().lower()
        category = self.category_combo.currentData()
        selected_id = self.current_method_id
        self.method_list.blockSignals(True)
        self.method_list.clear()
        selected_row = -1
        for method in TRAINING_METHODS:
            searchable = " ".join(
                str(method.get(key, ""))
                for key in ("title", "summary", "best_for", "category")
            ).lower()
            if query and query not in searchable:
                continue
            if category and method["category"] != category:
                continue
            item = QListWidgetItem(method["title"])
            item.setData(Qt.ItemDataRole.UserRole, method["id"])
            item.setToolTip(method["summary"])
            self.method_list.addItem(item)
            if method["id"] == selected_id:
                selected_row = self.method_list.count() - 1
        self.method_list.blockSignals(False)
        if self.method_list.count():
            self.method_list.setCurrentRow(selected_row if selected_row >= 0 else 0)
            self._method_selected(self.method_list.currentItem())

    def _method_selected(self, current, previous=None):
        if current is None:
            return
        method_id = current.data(Qt.ItemDataRole.UserRole)
        method = METHOD_MAP[method_id]
        self.current_method_id = method_id
        self.method_eyebrow.setText(
            f"{method['category'].upper()}  /  {MODE_LABELS[method['mode']].upper()}"
        )
        self.method_title.setText(method["title"])
        self.method_summary.setText(method["summary"])
        self.best_for_label.setText(method["best_for"])
        self.philosophy_label.setText(method["philosophy"])
        self.execution_label.setText(
            "\n".join(f"{index}. {step}" for index, step in enumerate(method["execution"], 1))
        )
        self.avoid_label.setText(method["avoid"])

        content = self._session_content(method)
        self.session_heading.setVisible(bool(content))
        self.session_label.setVisible(bool(content))
        self.session_label.setText(content)
        source_url = self._source_url(method)
        self.source_button.setVisible(bool(source_url))
        self.train_button.setText({
            "focused": "Set up focused block",
            "routine": "Build this routine",
            "deathmatch": "Load this checklist",
        }[method["mode"]])
        self.detail_scroll.verticalScrollBar().setValue(0)

    @staticmethod
    def _session_content(method):
        preferred = method.get("preferred_routine")
        if preferred:
            routine = next(
                (r for r in TACFPS_GUIDE["routines"] if r["name"] == preferred),
                None,
            )
            if routine:
                return "\n".join(
                    f"{exercise['duration']}  |  {exercise['scenario']}"
                    for exercise in routine["exercises"]
                )
        block_ids = method.get("deathmatch_blocks")
        if block_ids:
            blocks = {block["id"]: block for block in DEATHMATCH_GUIDE["blocks"]}
            return "\n".join(
                f"{blocks[block_id]['matches']} matches  |  {blocks[block_id]['title']}"
                for block_id in block_ids
                if block_id in blocks
            )
        duration = method.get("duration")
        if duration:
            return f"About {duration} minutes. The app builds the exercises for your current level."
        return "A short 3-5 minute recommendation based on your current level and recent training."

    @staticmethod
    def _source_url(method):
        if method["category"] == "TacFPS":
            return TACFPS_GUIDE["source_url"]
        if method["mode"] == "deathmatch":
            return DEATHMATCH_GUIDE["source_url"]
        return ""

    def _request_training(self):
        self.train_requested.emit(self.current_method_id)

    def _open_source(self):
        method = METHOD_MAP[self.current_method_id]
        source_url = self._source_url(method)
        if source_url:
            QDesktopServices.openUrl(QUrl(source_url))

    def update_profile(self, profile):
        """Keep the shared view contract used after score synchronization."""
        self.profile = profile
