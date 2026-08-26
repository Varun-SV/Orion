"""Aggregated operation-plan preview for Orion's current execution model."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.config import Config
from core.database import Database


class PlanMetric(QFrame):
    def __init__(self, label: str, tone: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        self._label = QLabel(label.upper())
        self._label.setObjectName("metricLabel")
        layout.addWidget(self._label)
        self._value = QLabel("—")
        self._value.setObjectName("metricValue")
        if tone:
            self._value.setProperty("tone", tone)
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class CheckRow(QFrame):
    def __init__(self, title: str, detail: str, state: str, tone: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("signalRow")
        row = QHBoxLayout(self)
        row.setContentsMargins(11, 9, 11, 9)
        copy = QVBoxLayout()
        copy.setSpacing(1)
        t = QLabel(title)
        t.setObjectName("sectionTitle")
        d = QLabel(detail)
        d.setProperty("role", "muted")
        d.setWordWrap(True)
        copy.addWidget(t)
        copy.addWidget(d)
        row.addLayout(copy, 1)
        chip = QLabel(state)
        chip.setObjectName("chip")
        chip.setProperty("tone", tone)
        row.addWidget(chip)


class OperationPlanPanel(QWidget):
    libraries_requested = pyqtSignal()

    def __init__(self, db: Database, config: Config, parent=None) -> None:
        super().__init__(parent)
        self._db = db
        self._config = config
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 26)
        root.setSpacing(14)

        header = QHBoxLayout()
        copy = QVBoxLayout()
        copy.setSpacing(3)
        eyebrow = QLabel("TRAJECTORY PREVIEW")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Operation Plan")
        title.setObjectName("pageTitle")
        subtitle = QLabel("A single view of the decisions Orion is ready to apply with today's library-specific organisers.")
        subtitle.setProperty("role", "muted")
        copy.addWidget(eyebrow)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        header.addLayout(copy, 1)
        refresh = QPushButton("↻ Refresh")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        open_btn = QPushButton("Open libraries →")
        open_btn.setObjectName("btn_accent")
        open_btn.clicked.connect(self.libraries_requested.emit)
        header.addWidget(open_btn)
        root.addLayout(header)

        note = QFrame()
        note.setObjectName("navigatorBar")
        nv = QHBoxLayout(note)
        nv.setContentsMargins(13, 10, 13, 10)
        mark = QLabel("✦")
        mark.setObjectName("navigatorMark")
        nv.addWidget(mark)
        note_copy = QVBoxLayout()
        note_copy.setSpacing(1)
        note_title = QLabel("Navigator preview — not a fake transaction engine")
        note_title.setObjectName("sectionTitle")
        note_detail = QLabel(
            "Orion currently executes inside each media library. This screen aggregates approved decisions and preflight signals; "
            "atomic commit, verification and rollback belong to the next foundation step."
        )
        note_detail.setProperty("role", "muted")
        note_detail.setWordWrap(True)
        note_copy.addWidget(note_title)
        note_copy.addWidget(note_detail)
        nv.addLayout(note_copy, 1)
        root.addWidget(note)

        grid = QGridLayout()
        grid.setSpacing(10)
        self._approved = PlanMetric("Approved decisions", "accent")
        self._destinations = PlanMetric("Destinations", "success")
        self._errors = PlanMetric("Blocking issues", "danger")
        self._model = PlanMetric("Execution model", "warn")
        for col, metric in enumerate((self._approved, self._destinations, self._errors, self._model)):
            grid.addWidget(metric, 0, col)
        root.addLayout(grid)

        body = QHBoxLayout()
        body.setSpacing(14)

        preflight = QFrame()
        preflight.setObjectName("card")
        pv = QVBoxLayout(preflight)
        pv.setContentsMargins(14, 13, 14, 13)
        pv.setSpacing(8)
        pt = QLabel("Preflight")
        pt.setObjectName("sectionTitle")
        pv.addWidget(pt)
        ph = QLabel("Signals Orion can verify from the current model before you enter a library and execute.")
        ph.setProperty("role", "muted")
        ph.setWordWrap(True)
        pv.addWidget(ph)
        self._checks = QVBoxLayout()
        self._checks.setSpacing(7)
        pv.addLayout(self._checks)
        pv.addStretch()
        body.addWidget(preflight, 2)

        plan = QFrame()
        plan.setObjectName("card")
        pl = QVBoxLayout(plan)
        pl.setContentsMargins(14, 13, 14, 13)
        pl.setSpacing(8)
        plan_title = QLabel("Approved route")
        plan_title.setObjectName("sectionTitle")
        pl.addWidget(plan_title)
        self._tree = QTreeWidget()
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setHeaderLabels(["Library", "Current", "Approved target"])
        self._tree.setColumnWidth(0, 110)
        self._tree.setColumnWidth(1, 280)
        pl.addWidget(self._tree, 1)
        body.addWidget(plan, 3)

        root.addLayout(body, 1)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh(self) -> None:
        scan_by_name = {i["name"]: i for i in self._db.get_scan_items()}
        video = [
            c for c in self._db.get_all_rename_choices()
            if c["original_name"] in scan_by_name
            and scan_by_name[c["original_name"]]["status"] != "moved"
        ]
        music_items = [i for i in self._db.get_music_items() if i["status"] != "moved"]
        books_items = [i for i in self._db.get_book_items() if i["status"] != "moved"]
        music = [(i, self._db.get_music_rename_choice(i["source_path"])) for i in music_items]
        books = [(i, self._db.get_book_rename_choice(i["source_path"])) for i in books_items]
        music = [(i, c) for i, c in music if c]
        books = [(i, c) for i, c in books if c]

        approved_count = len(video) + len(music) + len(books)
        destinations = self._db.get_destinations()
        errors = self._db.get_stats()["errors"]

        self._approved.set_value(str(approved_count))
        self._destinations.set_value(str(len(destinations)))
        self._errors.set_value(str(errors))
        self._model.set_value("Per library")

        self._refresh_checks(approved_count, len(destinations), errors)
        self._tree.clear()

        for choice in video:
            media_type = choice.get("media_type") or "video"
            library = {
                "movie": "Movies", "series": "Series", "anime": "Anime",
                "anime_film": "Anime Films", "web_series": "Web Series",
            }.get(media_type, media_type.replace("_", " ").title())
            self._tree.addTopLevelItem(QTreeWidgetItem([
                library,
                choice["original_name"],
                choice["chosen_name"],
            ]))

        for item, choice in music:
            target = " - ".join(part for part in [choice.get("track_number", ""), choice.get("title", "")] if part)
            album = choice.get("album", "")
            artist = choice.get("artist", "")
            if artist or album:
                target = f"{artist} / {album} / {target}".strip(" /-")
            self._tree.addTopLevelItem(QTreeWidgetItem(["Music", item["filename"], target or item["filename"]]))

        for item, choice in books:
            target = choice.get("title", "")
            author = choice.get("author", "")
            if author:
                target = f"{author} / {target}".strip(" /")
            self._tree.addTopLevelItem(QTreeWidgetItem(["Books", item["filename"], target or item["filename"]]))

        if self._tree.topLevelItemCount() == 0:
            empty = QTreeWidgetItem(["—", "No approved decisions yet", "Review items first"])
            self._tree.addTopLevelItem(empty)

    def _refresh_checks(self, approved: int, destinations: int, errors: int) -> None:
        self._clear_layout(self._checks)
        self._checks.addWidget(CheckRow(
            "Approved decisions",
            f"{approved} rename/metadata decision{'s are' if approved != 1 else ' is'} available to current organisers.",
            "READY" if approved else "EMPTY",
            "good" if approved else "warn",
        ))
        self._checks.addWidget(CheckRow(
            "Destination map",
            f"{destinations} destination root{'s' if destinations != 1 else ''} configured.",
            "READY" if destinations else "MISSING",
            "good" if destinations else "warn",
        ))
        self._checks.addWidget(CheckRow(
            "Known operation issues",
            "No scan items currently report an error." if not errors else f"{errors} item{'s' if errors != 1 else ''} report an error and should be reviewed.",
            "CLEAR" if not errors else "CHECK",
            "good" if not errors else "danger",
        ))
        self._checks.addWidget(CheckRow(
            "Transactional rollback",
            "Not yet implemented in the current mover; this UI does not claim otherwise.",
            "NEXT",
            "violet",
        ))

    def on_shown(self) -> None:
        self.refresh()
