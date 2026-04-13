from pathlib import Path
import json
import shutil
import re
from typing import Optional, List

from PySide6.QtWidgets import (
    QFrame, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QSizePolicy,
    QMenu, QMessageBox, QWidget, QGraphicsOpacityEffect
)
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtCore import Qt, QRectF
from pathlib import Path
import json

from .icons import icon
from .ui_add_quote import QuoteDialog

# avatar cache
_AVATAR_CACHE: dict[str, QPixmap] = {}


def _rounded_pixmap(src: QPixmap, radius: float) -> QPixmap:
    # return pixmap with rounded corners
    if src.isNull():
        return src

    w = src.width()
    h = src.height()
    result = QPixmap(w, h)
    result.fill(Qt.transparent)

    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, src)
    painter.end()

    return result


def get_avatar_pixmap(path: Path) -> QPixmap:
    # load, scale, round, cache
    key = str(path)
    pix = _AVATAR_CACHE.get(key)
    if pix is None:
        raw = QPixmap(key)
        if raw.isNull():
            scaled = QPixmap()
        else:
            scaled = raw.scaled(24, 24, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            corner_radius = 6
            scaled = _rounded_pixmap(scaled, corner_radius)

        _AVATAR_CACHE[key] = scaled
        pix = scaled
    return pix


# formatting helpers
def format_date(iso_date: str) -> str:
    y, m, d = iso_date.split("-")
    return f"{d}.{m}.{y}"


def format_time(ts: str) -> str:
    if not ts:
        return ""
    try:
        hour, rest = ts.split(":", 1)
        return f"{int(hour)}:{rest}"
    except ValueError:
        return ts


# icon button helper
def make_icon_button(key: str, tooltip: str, outer_size: int, icon_size: int) -> QPushButton:
    btn = QPushButton()
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFlat(True)
    icon(btn, key, icon_size)
    btn.setFixedSize(outer_size, outer_size)
    return btn


# quote bubble widget
class QuoteItem(QFrame):
    def __init__(self, quote, avatar_map, default_avatar, storage):
        super().__init__()

        self.quote = quote
        self.storage = storage

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.setObjectName("QuoteBubble")
        self.setStyleSheet("""
        QFrame#QuoteBubble {
            background-color: palette(base);
            border-radius: 14px;
            border: 1px solid palette(mid);
        }
        QFrame#QuoteBubble:hover {
            background-color: palette(alternate-base);
        }
        """)

        root = QHBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(12, 10, 12, 10)
        root.setAlignment(Qt.AlignVCenter)

        # left column
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)

        people_container = QWidget()
        people_layout = QVBoxLayout(people_container)
        people_layout.setSpacing(6)
        people_layout.setContentsMargins(0, 0, 0, 0)
        people_layout.setAlignment(Qt.AlignVCenter)

        for seg in quote.segments:
            segment = QFrame()
            segment.setObjectName("SegmentGroup")
            segment.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            segment.setStyleSheet("""
                QFrame#SegmentGroup {
                    border-radius: 8px;
                }
                QFrame#SegmentGroup:hover {
                    background-color: palette(window);
                }
            """)

            seg_layout = QHBoxLayout(segment)
            seg_layout.setSpacing(8)
            seg_layout.setContentsMargins(8, 6, 8, 6)
            seg_layout.setAlignment(Qt.AlignVCenter)

            if seg.speaker:
                avatar = avatar_map.get(seg.speaker, default_avatar)
                img = QLabel()
                img.setPixmap(get_avatar_pixmap(avatar))
                img.setFixedSize(24, 24)
                img.setAlignment(Qt.AlignCenter)
                img.setToolTip(seg.speaker)
                seg_layout.addWidget(img, 0, Qt.AlignTop)

            text = QLabel(seg.text)
            text.setWordWrap(True)
            text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            text.setTextInteractionFlags(Qt.TextSelectableByMouse)
            seg_layout.addWidget(text, 1)

            copy_btn = make_icon_button("copy", "Copy segment", outer_size=24, icon_size=14)
            copy_btn.setStyleSheet("""
                QPushButton { border-radius: 12px; }
                QPushButton:hover { background-color: palette(highlight); }
            """)
            copy_btn.clicked.connect(
                lambda _, s=seg.speaker, t=seg.text, b=copy_btn:
                self._copy_segment(s, t, b)
            )

            seg_layout.addWidget(copy_btn, 0, Qt.AlignTop)
            people_layout.addWidget(segment)

        # Format the details line
        details_parts = [
            f"Date: {format_date(quote.date)} at {format_time(quote.time)}",
        ]
        
        if quote.url:
            details_parts.append(f"Link: {quote.url}")
            
        if quote.timestamp:
            details_parts.append(f"Timestamp: {format_time(quote.timestamp)}")
            
        if quote.tags:
            details_parts.append(f"Tags: {', '.join(quote.tags)}")

        details = " | ".join(details_parts)
        
        # Add note field between quote and metadata if note exists
        if quote.note:
            # Create note container with icon
            note_container = QWidget()
            note_layout = QHBoxLayout(note_container)
            note_layout.setContentsMargins(0, 4, 0, 0)
            note_layout.setSpacing(4)
            
            # Note icon
            note_icon = QLabel()
            note_icon.setFixedSize(14, 14)
            icon(note_icon, "note", 14)
            note_icon.setStyleSheet("margin: 0px; padding: 0px;")
            
            # Note text
            note_label = QLabel(quote.note)
            note_label.setAlignment(Qt.AlignLeft)
            note_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            note_label.setStyleSheet("""
                QLabel {
                    color: palette(text);
                    font-size: 10px;
                    margin: 0px;
                    padding: 0px;
                }
            """)
            # Set opacity to 70%
            note_effect = QGraphicsOpacityEffect(note_label)
            note_effect.setOpacity(0.7)
            note_label.setGraphicsEffect(note_effect)
            
            note_layout.addWidget(note_icon)
            note_layout.addWidget(note_label)
            note_layout.addStretch(1)
            
            # Add note to the layout - between segments and metadata
            people_layout.addWidget(note_container)
            people_layout.addSpacing(4)
        
        footer = QLabel(details)
        footer.setAlignment(Qt.AlignLeft)
        footer.setTextInteractionFlags(Qt.TextSelectableByMouse)
        footer.setStyleSheet("""
            QLabel {
                color: palette(text);
                font-size: 10px;
                margin-top: 6px;
            }
        """)
        # footer opacity
        effect = QGraphicsOpacityEffect(footer)
        effect.setOpacity(0.4)
        footer.setGraphicsEffect(effect)

        left.addStretch(1)
        left.addWidget(people_container, 0, Qt.AlignVCenter)
        left.addStretch(1)
        left.addWidget(footer)

        root.addLayout(left, 1)

        # action pill
        pill = QFrame()
        pill.setObjectName("ActionPill")
        pill.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)
        pill.setStyleSheet("""
            QFrame#ActionPill {
                background-color: palette(window);
                border-radius: 18px;
                padding: 2px;
                border: 1px solid palette(mid);
            }
        """)

        pill_layout = QVBoxLayout(pill)
        pill_layout.setSpacing(2)
        pill_layout.setContentsMargins(2, 2, 2, 2)
        pill_layout.setAlignment(Qt.AlignVCenter)

        def pill_button(key, tooltip):
            # icon button
            btn = make_icon_button(key, tooltip, outer_size=26, icon_size=14)
            btn.setStyleSheet("""
                QPushButton { border-radius: 13px; }
                QPushButton:hover { background-color: palette(highlight); }
            """)
            return btn

        copy_all = pill_button("copy_all", "Copy entire quote")
        open_url = pill_button("link", "Open source link")
        more_btn = pill_button("more", "More actions")

        def _copy_all_clicked():
            speaker_choice: dict[str, str | None] = {}
            parts = []
            for seg in self.quote.segments:
                s = seg.speaker
                t = seg.text
                if s:
                    if s not in speaker_choice:
                        nickname = self._choose_nickname(s, copy_all)
                        speaker_choice[s] = nickname
                    display = speaker_choice[s] if speaker_choice[s] else s
                    parts.append(f"{display} {t}")
                else:
                    parts.append(t)
            self.copy_text(" ".join(parts))

        copy_all.clicked.connect(_copy_all_clicked)
        open_url.clicked.connect(lambda: self.open_url(quote.url))

        menu = QMenu(self)
        menu.addAction("Edit quote", self._on_edit)
        menu.addAction("Delete quote", self._on_delete)
        more_btn.clicked.connect(
            lambda: menu.exec(more_btn.mapToGlobal(more_btn.rect().bottomLeft()))
        )

        pill_layout.addWidget(copy_all)
        pill_layout.addWidget(open_url)
        pill_layout.addWidget(more_btn)

        root.addWidget(pill)

    # actions
    def _on_delete(self):
        from .write_manager import QuoteModifier

        confirm = QMessageBox.question(
            self,
            "Delete Quote",
            "Are you sure you want to delete this quote?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        modifier = QuoteModifier(self.storage.root)
        modifier.remove_quote(self.quote.date, self.quote.time, self.quote.url, self.quote.timestamp, self.quote.tags, self.quote.note)
        self.window().refresh_storage()

    def _on_edit(self):
        dlg = QuoteDialog(self.storage, self, quote=self.quote)
        if dlg.exec():
            self.window().refresh_storage()

    # nickname helpers
    def _load_nicknames(self, person: str) -> list[str]:
        try:
            attr_file = (self.storage.root / person / "attributes.json")
            if not attr_file.exists():
                return []
            data = json.loads(attr_file.read_text(encoding="utf-8"))
            n = data.get("nicknames", []) or []
            return [str(x) for x in n if x is not None and str(x).strip() != ""]
        except Exception:
            return []

    def _choose_nickname(self, person: str, anchor_widget: QWidget | None = None) -> str | None:
        nicks = self._load_nicknames(person)
        if not nicks:
            return None
        if len(nicks) == 1:
            return nicks[0]

        menu = QMenu(self)
        actions = []
        for nick in nicks:
            actions.append(menu.addAction(nick))
        try:
            if anchor_widget is not None:
                pos = anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft())
            else:
                pos = self.mapToGlobal(self.rect().topLeft())
        except Exception:
            pos = self.mapToGlobal(self.rect().topLeft())

        chosen = menu.exec(pos)
        if not chosen:
            return None
        return chosen.text()

    # copy helpers
    def _copy_segment(self, speaker: str | None, text: str, anchor_widget: QWidget | None = None):
        if not speaker:
            self.copy_text(text)
            return
        name = self._choose_nickname(speaker, anchor_widget)
        display_name = name if name else speaker
        self.copy_text(f"{display_name} {text}")

    # helpers
    def copy_text(self, text: str):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text.strip())

    def open_url(self, url: str):
        import webbrowser
        webbrowser.open(url)