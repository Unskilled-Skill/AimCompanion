from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QFileDialog, QPushButton, QTextEdit, QProgressBar
)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent

from models.database import Database
from core.parser import parse_csv_file, import_all_scores


class DragDropImport(QWidget):
    def __init__(self, db: Database, on_import_complete=None):
        super().__init__()
        self.db = db
        self.on_import_complete = on_import_complete
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.drop_frame = QFrame()
        self.drop_frame.setObjectName("dropZone")
        self.drop_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.drop_frame.setStyleSheet("""
            QFrame#dropZone {
                background-color: #1a1a2a;
                border: 2px dashed #444;
                border-radius: 12px;
                padding: 40px;
            }
        """)
        drop_layout = QVBoxLayout(self.drop_frame)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        drop_icon = QLabel("+")
        drop_icon.setFont(QFont("Segoe UI", 36))
        drop_icon.setStyleSheet("color: #4a9eff;")
        drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(drop_icon)

        drop_text = QLabel("Drag & drop Kovaak's CSV score files here")
        drop_text.setStyleSheet("color: #888; font-size: 12px;")
        drop_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(drop_text)

        drop_sub = QLabel("Or click the button below to browse")
        drop_sub.setStyleSheet("color: #555; font-size: 10px;")
        drop_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(drop_sub)

        layout.addWidget(self.drop_frame)

        btn_row = QHBoxLayout()
        browse_btn = QPushButton("Choose CSV files")
        browse_btn.setObjectName("quietButton")
        browse_btn.clicked.connect(self._browse_files)
        btn_row.addWidget(browse_btn)

        auto_btn = QPushButton("Import from Kovaak's")
        auto_btn.setObjectName("primaryButton")
        auto_btn.clicked.connect(self._auto_import)
        btn_row.addWidget(auto_btn)

        layout.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setStyleSheet(
            "QProgressBar { background-color: #1a1a2a; border-radius: 4px; text-align: center; color: white; }"
            "QProgressBar::chunk { background-color: #4a9eff; border-radius: 4px; }"
        )
        self.progress.hide()
        layout.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        self.log.setStyleSheet(
            "QTextEdit { background-color: #0d0d1a; color: #aaa; border-radius: 4px; padding: 5px; font-family: Consolas; font-size: 10px; }"
        )
        layout.addWidget(self.log)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_frame.setStyleSheet("""
                QFrame#dropZone {
                    background-color: #1a2a3a;
                    border: 2px dashed #4a9eff;
                    border-radius: 12px;
                    padding: 40px;
                }
            """)

    def dragLeaveEvent(self, event):
        self.drop_frame.setStyleSheet("""
            QFrame#dropZone {
                background-color: #1a1a2a;
                border: 2px dashed #444;
                border-radius: 12px;
                padding: 40px;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        self.drop_frame.setStyleSheet("""
            QFrame#dropZone {
                background-color: #1a1a2a;
                border: 2px dashed #444;
                border-radius: 12px;
                padding: 40px;
            }
        """)

        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith('.csv'):
                files.append(path)

        if files:
            self._import_files(files)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select CSV Files", "",
            "CSV Files (*.csv);;All Files (*)"
        )
        if files:
            self._import_files(files)

    def _auto_import(self):
        imported = import_all_scores(self.db)
        self.log.append(f"Auto-imported {imported} new scores from Kovaak's folder")
        if self.on_import_complete:
            self.on_import_complete()

    def _import_files(self, files):
        self.progress.show()
        self.progress.setMaximum(len(files))
        self.progress.setValue(0)
        self.log.clear()

        imported = 0
        for i, path in enumerate(files):
            self.log.append(f"Importing: {path.split('/')[-1].split(chr(92))[-1]}")
            try:
                score = parse_csv_file(path)
                if score:
                    if not self.db.score_exists(path) and not self.db.score_record_exists(score):
                        self.db.insert_score(score, path)
                        imported += 1
                        self.log.append(f"  -> {score.scenario}: {score.score:.0f}")
                    else:
                        self.log.append(f"  -> Already imported")
                else:
                    self.log.append(f"  -> Failed to parse")
            except Exception as e:
                self.log.append(f"  -> Error: {str(e)}")

            self.progress.setValue(i + 1)

        self.log.append(f"\nDone! Imported {imported}/{len(files)} new scores")
        if self.on_import_complete:
            self.on_import_complete()
