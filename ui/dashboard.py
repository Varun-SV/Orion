"""Orion Navigator overview.

The dashboard is intentionally workflow-first: it tells the user what Orion
knows, what needs attention, and where the next safe action lives.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.config import Config
from core.database import Database
from core.utils import format_bytes


class MetricCard(QFrame):
    def __init__(self, label: str, tone: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 13, 15, 13)
        layout.setSpacing(5)

        label_widget = QLabel(label.upper())
        label_widget.setObjectName("metricLabel")
        layout.addWidget(label_widget)

        self._value = QLabel("—")
        self._value.setObjectName("metricValue")
        if tone:
            self._value.setProperty("tone", tone)
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class SignalRow(QFrame):
    def __init__(self, title: str, detail: str, chip: str, tone: str = "warn", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("signalRow")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(10)

        mark = QLabel("⌖")
        mark.setObjectName("navigatorMark")
        mark.setFixedWidth(24)
        row.addWidget(mark)

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

        badge = QLabel(chip)
        badge.setObjectName("chip")
        badge.setProperty("tone", tone)
        row.addWidget(badge)


class DashboardPanel(QWidget):
    review_requested = pyqtSignal()
    plan_requested = pyqtSignal()
    libraries_requested = pyqtSignal()

    def __init__(self, db: Database, config: Config, parent=None) -> None:
        super().__init__(parent)
        self._db = db
        self._config = config
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(26, 24, 26, 26)
        root.setSpacing(16)

        header = QHBoxLayout()
        header_copy = QVBoxLayout()
        header_copy.setSpacing(3)
        eyebrow = QLabel("ORION NAVIGATOR")
        eyebrow.setObjectName("eyebrow")
        self._hero = QLabel("Your library is on course.")
        self._hero.setObjectName("pageTitle")
        self._subtitle = QLabel("Orion is mapping your collection and surfacing the decisions that deserve your attention.")
        self._subtitle.setProperty("role", "muted")
        self._subtitle.setWordWrap(True)
        header_copy.addWidget(eyebrow)
        header_copy.addWidget(self._hero)
        header_copy.addWidget(self._subtitle)
        header.addLayout(header_copy, 1)

        review_btn = QPushButton("Review queue")
        review_btn.clicked.connect(self.review_requested.emit)
        header.addWidget(review_btn)
        plan_btn = QPushButton("Open operation plan")
        plan_btn.setObjectName("btn_accent")
        plan_btn.clicked.connect(self.plan_requested.emit)
        header.addWidget(plan_btn)
        root.addLayout(header)

        navigator = QFrame()
        navigator.setObjectName("navigatorBar")
        nav = QHBoxLayout(navigator)
        nav.setContentsMargins(14, 11, 14, 11)
        nav.setSpacing(10)
        star = QLabel("✦")
        star.setObjectName("navigatorMark")
        nav.addWidget(star)
        nav_copy = QVBoxLayout()
        nav_copy.setSpacing(1)
        nav_title = QLabel("Orion has plotted the next course.")
        nav_title.setObjectName("sectionTitle")
        self._navigator_detail = QLabel("Reading library state…")
        self._navigator_detail.setProperty("role", "muted")
        nav_copy.addWidget(nav_title)
        nav_copy.addWidget(self._navigator_detail)
        nav.addLayout(nav_copy, 1)
        self._navigator_chip = QLabel("NAVIGATOR ONLINE")
        self._navigator_chip.setObjectName("chip")
        self._navigator_chip.setProperty("tone", "good")
        nav.addWidget(self._navigator_chip)
        root.addWidget(navigator)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        self._total = MetricCard("Tracked media", "accent")
        self._pending = MetricCard("Awaiting review", "warn")
        self._moved = MetricCard("Organised", "success")
        self._issues = MetricCard("Issues", "danger")
        for col, card in enumerate((self._total, self._pending, self._moved, self._issues)):
            metrics.addWidget(card, 0, col)
        root.addLayout(metrics)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        columns.addWidget(self._build_attention_card(), 3)
        columns.addWidget(self._build_route_card(), 2)
        root.addLayout(columns)

        activity = QFrame()
        activity.setObjectName("card")
        av = QVBoxLayout(activity)
        av.setContentsMargins(15, 14, 15, 14)
        title_row = QHBoxLayout()
        title = QLabel("Recent navigation")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        refresh = QPushButton("↻ Refresh")
        refresh.clicked.connect(self.refresh)
        title_row.addWidget(refresh)
        av.addLayout(title_row)
        self._activity_layout = QVBoxLayout()
        self._activity_layout.setSpacing(7)
        av.addLayout(self._activity_layout)
        root.addWidget(activity)
        root.addStretch()

    def _build_attention_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 14, 15, 14)
        layout.setSpacing(9)

        row = QHBoxLayout()
        title = QLabel("Signals requiring attention")
        title.setObjectName("sectionTitle")
        row.addWidget(title)
        row.addStretch()
        btn = QPushButton("Open queue")
        btn.clicked.connect(self.review_requested.emit)
        row.addWidget(btn)
        layout.addLayout(row)

        hint = QLabel("Orion keeps ambiguous or failed items out of the execution path until you decide what they are.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._attention_layout = QVBoxLayout()
        self._attention_layout.setSpacing(7)
        layout.addLayout(self._attention_layout)
        return card

    def _build_route_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 14, 15, 14)
        layout.setSpacing(9)

        title = QLabel("Library route")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        hint = QLabel("Sources in Orion's field of view and the destinations it can currently navigate to.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        src_label = QLabel("SOURCES")
        src_label.setObjectName("eyebrow")
        layout.addWidget(src_label)
        self._sources_layout = QVBoxLayout()
        self._sources_layout.setSpacing(5)
        layout.addLayout(self._sources_layout)

        dst_label = QLabel("DESTINATIONS")
        dst_label.setObjectName("eyebrow")
        layout.addWidget(dst_label)
        self._destinations_layout = QVBoxLayout()
        self._destinations_layout.setSpacing(5)
        layout.addLayout(self._destinations_layout)

        open_btn = QPushButton("Open libraries")
        open_btn.clicked.connect(self.libraries_requested.emit)
        layout.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        return card

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            child = item.layout()
            if child is not None:
                DashboardPanel._clear_layout(child)

    def refresh(self) -> None:
        stats = self._db.get_stats()
        total = stats["total"]
        pending = stats["pending"]
        moved = stats["moved"]
        errors = stats["errors"]

        self._total.set_value(str(total))
        self._pending.set_value(str(pending))
        self._moved.set_value(str(moved))
        self._issues.set_value(str(errors))

        if errors:
            self._hero.setText("A few signals need a safer course.")
            self._subtitle.setText("Orion found items that should be resolved before you organise the next batch.")
        elif pending:
            self._hero.setText("Your library is on course.")
            self._subtitle.setText("The route is clear; the remaining decisions are waiting in Review Queue.")
        elif total:
            self._hero.setText("The constellation is clear.")
            self._subtitle.setText("Everything Orion currently tracks is organised and no issues are blocking the route.")
        else:
            self._hero.setText("Give Orion a library to navigate.")
            self._subtitle.setText("Add a source folder, scan it, and Orion will turn the collection into a reviewable route.")

        destinations = self._db.get_destinations()
        sources = self._db.get_source_folders()
        self._navigator_detail.setText(
            f"{total} tracked items · {pending} awaiting review · {errors} issues · "
            f"{len(destinations)} destination{'s' if len(destinations) != 1 else ''} mapped"
        )
        self._navigator_chip.setText("CHECK SIGNALS" if errors else "NAVIGATOR ONLINE")
        self._navigator_chip.setProperty("tone", "warn" if errors else "good")
        self._navigator_chip.style().unpolish(self._navigator_chip)
        self._navigator_chip.style().polish(self._navigator_chip)

        self._refresh_attention()
        self._refresh_routes(sources, destinations)
        self._refresh_activity()

    def _refresh_attention(self) -> None:
        self._clear_layout(self._attention_layout)
        rows = []
        for item in self._db.get_scan_items():
            if item["status"] == "error":
                rows.append((item["name"], "The last operation reported an error for this item.", "ISSUE", "danger"))
        if len(rows) < 4:
            resolved = {r["original_name"] for r in self._db.get_all_rename_choices()}
            for item in self._db.get_scan_items():
                if item["status"] == "moved" or item["name"] in resolved:
                    continue
                rows.append((item["name"], f"{item['detected_category'] or 'Media'} still needs a match decision.", "REVIEW", "warn"))
                if len(rows) >= 4:
                    break

        if not rows:
            clear = SignalRow("No blocking signals", "Orion has no unresolved video-library decisions in the current scan.", "CLEAR", "good")
            self._attention_layout.addWidget(clear)
            return

        for title, detail, chip, tone in rows[:4]:
            self._attention_layout.addWidget(SignalRow(title, detail, chip, tone))

    def _refresh_routes(self, sources: list[dict], destinations: list[dict]) -> None:
        self._clear_layout(self._sources_layout)
        self._clear_layout(self._destinations_layout)

        if sources:
            for src in sources[:4]:
                label = QLabel(f"⌁  {src['path']}")
                label.setProperty("role", "muted")
                label.setToolTip(src["path"])
                self._sources_layout.addWidget(label)
        else:
            label = QLabel("No source folders configured")
            label.setProperty("role", "subtle")
            self._sources_layout.addWidget(label)

        if destinations:
            for dst in destinations[:4]:
                free_text = "capacity unavailable"
                try:
                    usage = shutil.disk_usage(Path(dst["path"]))
                    free_text = f"{format_bytes(usage.free)} free"
                except Exception:
                    pass
                label = QLabel(f"↗  {dst['path']}  ·  {free_text}")
                label.setProperty("role", "muted")
                label.setToolTip(dst["path"])
                self._destinations_layout.addWidget(label)
        else:
            label = QLabel("No destinations configured")
            label.setProperty("role", "subtle")
            self._destinations_layout.addWidget(label)

    def _refresh_activity(self) -> None:
        self._clear_layout(self._activity_layout)
        logs = self._db.get_logs(6)
        if not logs:
            empty = QLabel("No navigation history yet. Orion will record scans and organisation work here.")
            empty.setProperty("role", "subtle")
            self._activity_layout.addWidget(empty)
            return

        for entry in logs:
            row = QHBoxLayout()
            status = entry.get("status", "ok")
            icon = "✓" if status == "ok" else "⚠" if status == "warning" else "✕"
            chip = QLabel(icon)
            chip.setObjectName("chip")
            chip.setProperty("tone", "good" if status == "ok" else "warn" if status == "warning" else "danger")
            row.addWidget(chip)
            title = QLabel(entry.get("action", "Activity"))
            row.addWidget(title)
            detail = QLabel(entry.get("item_path", ""))
            detail.setProperty("role", "muted")
            detail.setToolTip(entry.get("item_path", ""))
            row.addWidget(detail, 1)
            stamp = QLabel(entry.get("created_at", ""))
            stamp.setProperty("role", "subtle")
            row.addWidget(stamp)
            self._activity_layout.addLayout(row)

    def on_shown(self) -> None:
        self.refresh()
