"""Unified Review Queue for Orion's existing media resolvers."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.config import Config
from core.database import Database


_VIDEO_LIBRARY = {
    "movie": ("Movies", "movies"),
    "series": ("Series", "series"),
    "anime": ("Anime", "anime"),
    "anime_film": ("Anime Films", "anime_films"),
    "web_series": ("Web Series", "web_series"),
}


class ReviewQueuePanel(QWidget):
    """One queue across video, music, and books without faking a new resolver.

    Orion's current approval editors remain inside each media panel. This view
    provides the workflow-first inbox and routes the selected item to the
    correct existing editor.
    """

    open_library = pyqtSignal(str)

    def __init__(self, db: Database, config: Config, parent=None) -> None:
        super().__init__(parent)
        self._db = db
        self._config = config
        self._rows: list[dict] = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 26)
        root.setSpacing(14)

        header = QHBoxLayout()
        copy = QVBoxLayout()
        copy.setSpacing(3)
        eyebrow = QLabel("DECISION INBOX")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Review Queue")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Anything Orion cannot resolve safely lands here before it can move through the library.")
        subtitle.setProperty("role", "muted")
        copy.addWidget(eyebrow)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        header.addLayout(copy, 1)
        self._count_chip = QLabel("0 SIGNALS")
        self._count_chip.setObjectName("chip")
        self._count_chip.setProperty("tone", "warn")
        header.addWidget(self._count_chip)
        root.addLayout(header)

        controls = QFrame()
        controls.setObjectName("softCard")
        ctl = QHBoxLayout(controls)
        ctl.setContentsMargins(12, 10, 12, 10)
        ctl.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search unresolved media…")
        self._search.textChanged.connect(self._apply_filters)
        ctl.addWidget(self._search, 1)
        self._filter = QComboBox()
        self._filter.addItems([
            "All media", "Movies", "Series", "Anime", "Anime Films",
            "Web Series", "Music", "Books",
        ])
        self._filter.currentTextChanged.connect(self._apply_filters)
        ctl.addWidget(self._filter)
        refresh = QPushButton("↻ Refresh")
        refresh.clicked.connect(self.refresh)
        ctl.addWidget(refresh)
        root.addWidget(controls)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        self._tree = QTreeWidget()
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setHeaderLabels(["Item", "Library", "Signal", "Source"])
        self._tree.setColumnWidth(0, 280)
        self._tree.setColumnWidth(1, 120)
        self._tree.setColumnWidth(2, 150)
        self._tree.itemDoubleClicked.connect(lambda *_: self._open_selected())
        self._tree.itemSelectionChanged.connect(self._selection_changed)
        card_layout.addWidget(self._tree)

        footer = QHBoxLayout()
        footer.setContentsMargins(12, 10, 12, 10)
        note = QLabel("Orion routes the item to its existing resolver; no decision is auto-invented here.")
        note.setProperty("role", "muted")
        footer.addWidget(note, 1)
        self._open_btn = QPushButton("Open in library →")
        self._open_btn.setObjectName("btn_accent")
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._open_selected)
        footer.addWidget(self._open_btn)
        card_layout.addLayout(footer)
        root.addWidget(card, 1)

    @property
    def pending_count(self) -> int:
        return len(self._rows)

    def set_search(self, text: str) -> None:
        self._search.setText(text)
        self._search.setFocus()

    def refresh(self) -> None:
        self._rows = self._collect_rows()
        count = len(self._rows)
        self._count_chip.setText(f"{count} SIGNAL{'S' if count != 1 else ''}")
        self._count_chip.setProperty("tone", "warn" if count else "good")
        self._count_chip.style().unpolish(self._count_chip)
        self._count_chip.style().polish(self._count_chip)
        self._apply_filters()

    def _collect_rows(self) -> list[dict]:
        rows: list[dict] = []
        categories = {c["name"]: c for c in self._db.get_categories()}
        resolved = {r["original_name"] for r in self._db.get_all_rename_choices()}

        for item in self._db.get_scan_items():
            if item["status"] == "moved" or item["name"] in resolved:
                continue
            category_name = item.get("detected_category", "")
            category = categories.get(category_name)
            media_type = (category or {}).get("media_type", category_name)
            display, key = _VIDEO_LIBRARY.get(media_type, (category_name or "Video", "movies"))
            rows.append({
                "item": item["name"],
                "library": display,
                "key": key,
                "signal": "Operation issue" if item["status"] == "error" else "Match required",
                "source": item["path"],
            })

        for item in self._db.get_music_items():
            if item["status"] == "moved" or self._db.get_music_rename_choice(item["source_path"]):
                continue
            rows.append({
                "item": item.get("filename") or item["source_path"],
                "library": "Music",
                "key": "music",
                "signal": "Metadata review" if item["status"] in {"identified", "pending"} else item["status"].replace("_", " ").title(),
                "source": item["source_path"],
            })

        for item in self._db.get_book_items():
            if item["status"] == "moved" or self._db.get_book_rename_choice(item["source_path"]):
                continue
            rows.append({
                "item": item.get("filename") or item["source_path"],
                "library": "Books",
                "key": "books",
                "signal": "Metadata review",
                "source": item["source_path"],
            })

        rows.sort(key=lambda r: (r["library"], r["item"].lower()))
        return rows

    def _apply_filters(self) -> None:
        text = self._search.text().strip().lower()
        selected_library = self._filter.currentText()
        self._tree.clear()

        for row in self._rows:
            if selected_library != "All media" and row["library"] != selected_library:
                continue
            haystack = f"{row['item']} {row['library']} {row['signal']} {row['source']}".lower()
            if text and text not in haystack:
                continue
            item = QTreeWidgetItem([row["item"], row["library"], row["signal"], row["source"]])
            item.setData(0, Qt.ItemDataRole.UserRole, row["key"])
            item.setToolTip(3, row["source"])
            self._tree.addTopLevelItem(item)

        self._selection_changed()

    def _selection_changed(self) -> None:
        self._open_btn.setEnabled(bool(self._tree.selectedItems()))

    def _open_selected(self) -> None:
        selected = self._tree.selectedItems()
        if not selected:
            return
        key = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if key:
            self.open_library.emit(str(key))

    def on_shown(self) -> None:
        self.refresh()
