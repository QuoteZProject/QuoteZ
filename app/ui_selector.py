from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QPushButton, QFrame, QScrollArea, QToolButton
)
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtCore import Qt, Signal
from pathlib import Path

from .storage import QuoteStorage
from .icons import icon
from .xdg_data import get_resource_file

# Resolve assets relative to package root so app works as Flatpak or locally
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
INDENT = 40
ASSETS = _PACKAGE_ROOT / "assets"
DEFAULT_AVATAR = get_resource_file("default.png", package_root=_PACKAGE_ROOT)


# Return pixmap sized (width, height) with rounded corners (radius).
def _rounded_pixmap_from_pixmap(pix: QPixmap, width: int, height: int, radius: int) -> QPixmap:
    if pix.isNull():
        p = QPixmap(width, height)
        p.fill(Qt.transparent)
        return p

    scaled = pix.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    target = QPixmap(width, height)
    target.fill(Qt.transparent)

    painter = QPainter(target)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setRenderHint(QPainter.Antialiasing, True)

    path = QPainterPath()
    path.addRoundedRect(0.0, 0.0, float(width), float(height), float(radius), float(radius))
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return target


class Row(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pgs_row")
        self.setStyleSheet("""
            QFrame#pgs_row {
                border-radius: 6px;
                background: transparent;
            }
            QFrame#pgs_row:hover {
                background-color: palette(alternate-base);
            }
            QLabel {
                font-size: 11px;
            }
            QCheckBox {
                spacing: 2px;
            }
            QPushButton {
                padding: 0px;
            }
        """)


class PersonGroupSelector(QWidget):

    selection_changed = Signal()

    def __init__(
        self,
        storage: QuoteStorage,
        show_checkboxes: bool = True,
        group_right_widget_builder=None,
        person_right_widget_builder=None,
    ):
        super().__init__()

        self.setObjectName("person_group_selector")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setStyleSheet("""
            QWidget#person_group_selector {
                background-color: palette(base);
                border-radius: 10px;
                padding: 6px;
            }
            QWidget#person_group_selector QLabel { font-size: 11px; }
            QWidget#person_group_selector QCheckBox { spacing: 4px; }
            QWidget#person_group_selector QPushButton { font-size: 11px; }
        """)

        self.storage = storage
        self.show_checkboxes = show_checkboxes
        self.group_right_widget_builder = group_right_widget_builder
        self.person_right_widget_builder = person_right_widget_builder

        # External handlers: avatar_click_handler(person_name), person_right_click_handler(person_name, global_pos)
        self.avatar_click_handler = None
        self.person_right_click_handler = None

        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)

        self._load_data()
        self._build_ui()
        self._refresh_visuals()
        self.setMaximumHeight(170)

    def _load_data(self):
        self.groups = self.storage.load_groups()
        self.people = self.storage.people
        self.quote_counts = self.storage.get_quote_counts()

        self.group_enabled = {g: True for g in self.groups}

        self.person_group_checked = {
            g: {p: True for p in members}
            for g, members in self.groups.items()
        }

        grouped = {p for m in self.groups.values() for p in m}
        self.ungrouped = [p for p in self.people if p not in grouped]

        self.group_checkboxes = {}
        self.group_headers = {}
        self.person_rows = {}
        self.person_checkboxes = {}
        self.ungrouped_rows = {}

    def _clear_layout(self):
        while self.outer_layout.count():
            item = self.outer_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _build_ui(self):
        self._clear_layout()

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        self.outer_layout.addWidget(scroll)

        container = QWidget()
        container.setAttribute(Qt.WA_StyledBackground, True)
        container.setStyleSheet("background: transparent;")
        root = QVBoxLayout(container)
        root.setSpacing(1)
        root.setContentsMargins(6, 6, 6, 6)

        scroll.setWidget(container)

        try:
            vsb = scroll.verticalScrollBar()
            hsb = scroll.horizontalScrollBar()
            vsb.setStyleSheet("")
            hsb.setStyleSheet("")
            vsb.setAttribute(Qt.WA_StyledBackground, False)
            hsb.setAttribute(Qt.WA_StyledBackground, False)
        except Exception:
            pass

        if self.groups:
            lbl = QLabel("Groups")
            lbl.setStyleSheet("font-weight: bold; margin-bottom: 2px;")
            root.addWidget(lbl)

        for group, members in sorted(self.groups.items()):
            root.addWidget(self._create_group(group, members))

        if self.ungrouped:
            lbl = QLabel("Others")
            lbl.setStyleSheet("font-weight: bold; margin-top: 6px;")
            root.addWidget(lbl)

            for p in self.ungrouped:
                row, cb = self._create_person_row(None, p)
                if cb:
                    self.ungrouped_rows[p] = cb
                root.addWidget(row)

        root.addStretch()

    def _create_group(self, group, members):
        wrapper = QWidget(self)
        lay = QVBoxLayout(wrapper)
        lay.setSpacing(1)
        lay.setContentsMargins(0, 0, 0, 0)

        header = Row(wrapper)
        header.setFocusPolicy(Qt.NoFocus)

        h = QHBoxLayout(header)
        h.setContentsMargins(4, 1, 4, 1)

        toggle = QPushButton("▸")
        toggle.setCheckable(True)
        toggle.setFlat(True)
        toggle.setFixedWidth(14)
        toggle.setCursor(Qt.PointingHandCursor)

        icon_btn = QToolButton()
        icon_btn.setAutoRaise(True)
        icon_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        icon_btn.setFixedSize(18, 18)
        icon_btn.setCursor(Qt.ArrowCursor)
        icon_btn.setFocusPolicy(Qt.NoFocus)
        icon_btn.setProperty("is_group_icon", True)
        icon(icon_btn, "group", 14)

        group_count = sum(
            self.quote_counts.get(p, 0)
            for p in members
        )

        label = QLabel(f"{group} ({group_count})")
        label.setStyleSheet("font-weight: bold;")
        label.setProperty("group_name_plain", group)

        gcb = None
        if self.show_checkboxes:
            gcb = QCheckBox()
            gcb.setChecked(True)
            gcb.setCursor(Qt.PointingHandCursor)
            gcb.toggled.connect(
                lambda v, g=group: self._on_group_toggled(g, v)
            )
            self.group_checkboxes[group] = gcb

        self.group_headers[group] = header

        h.addWidget(toggle)
        h.addWidget(icon_btn)
        h.addWidget(label)
        h.addStretch()

        if self.group_right_widget_builder:
            widget = self.group_right_widget_builder(group)
            if widget:
                try:
                    if isinstance(widget, QPushButton):
                        widget.setCursor(Qt.PointingHandCursor)
                    else:
                        widget.setCursor(Qt.ArrowCursor)
                except Exception:
                    widget.setCursor(Qt.ArrowCursor)
                h.addWidget(widget)
        elif gcb:
            h.addWidget(gcb)

        box = QWidget(wrapper)
        v = QVBoxLayout(box)
        v.setContentsMargins(INDENT, 0, 0, 0)
        v.setSpacing(1)
        box.hide()

        for p in sorted(members):
            row, cb = self._create_person_row(group, p)
            self.person_rows[(group, p)] = row
            if cb:
                self.person_checkboxes[(group, p)] = cb
            v.addWidget(row)

        toggle.toggled.connect(
            lambda c, b=box, t=toggle:
            (b.setVisible(c), t.setText("▾" if c else "▸"))
        )

        lay.addWidget(header)
        lay.addWidget(box)

        return wrapper

    def _create_person_row(self, group, person):
        row = Row(self)
        h = QHBoxLayout(row)
        h.setContentsMargins(4, 2, 4, 2)

        avatar = QLabel()

        raw_pix = QPixmap(str(self.people.get(person, DEFAULT_AVATAR)))
        # rounded avatar 16x16 radius 4
        rounded = _rounded_pixmap_from_pixmap(raw_pix, 16, 16, 4)
        avatar.setPixmap(rounded)

        avatar.setProperty("is_person_avatar", True)

        def _on_avatar_clicked(event, p=person):
            if callable(self.avatar_click_handler):
                self.avatar_click_handler(p)

        avatar.mousePressEvent = _on_avatar_clicked
        avatar.setCursor(
            Qt.PointingHandCursor
            if callable(self.avatar_click_handler)
            else Qt.ArrowCursor
        )

        count = self.quote_counts.get(person, 0)
        label = QLabel(f"{person} ({count})")
        label.setProperty("person_name_plain", person)

        def _on_label_clicked(event, p=person):
            try:
                is_left_shift = (
                    event.button() == Qt.LeftButton
                    and (event.modifiers() & Qt.ShiftModifier)
                )
            except Exception:
                is_left_shift = False

            if is_left_shift and callable(self.person_right_click_handler):
                try:
                    global_pos = label.mapToGlobal(event.pos())
                except Exception:
                    global_pos = label.mapToGlobal(label.rect().bottomLeft())
                self.person_right_click_handler(p, global_pos)
                return

        cb = None
        if self.show_checkboxes:
            cb = QCheckBox()
            cb.setChecked(True)
            cb.setCursor(Qt.PointingHandCursor)
            cb.toggled.connect(
                lambda v, g=group, p=person:
                self._on_person_toggled(g, p, v)
            )

        h.addWidget(avatar)
        h.addWidget(label)
        h.addStretch()

        if self.person_right_widget_builder:
            widget = self.person_right_widget_builder(group, person)
            if widget:
                try:
                    if isinstance(widget, QPushButton):
                        widget.setCursor(Qt.PointingHandCursor)
                    else:
                        widget.setCursor(Qt.ArrowCursor)
                except Exception:
                    widget.setCursor(Qt.ArrowCursor)
                h.addWidget(widget)
        elif cb:
            h.addWidget(cb)

        return row, cb

    def _on_person_toggled(self, group, person, checked):
        if group is not None:
            self.person_group_checked[group][person] = checked
        self.selection_changed.emit()

    def _on_group_toggled(self, group, enabled):
        self.group_enabled[group] = enabled
        self._refresh_visuals()
        self.selection_changed.emit()

    def _refresh_visuals(self):
        for (group, _), row in self.person_rows.items():
            row.setEnabled(self.group_enabled.get(group, True))

    def reload_from_storage(self, storage: QuoteStorage):
        self.storage = storage
        self._load_data()
        self._build_ui()
        self._refresh_visuals()

    def get_effective_people(self):
        if not self.show_checkboxes:
            return None

        effective = set()

        for person in self.people:
            for group, members in self.groups.items():
                if person not in members:
                    continue
                if not self.group_enabled.get(group, True):
                    continue

                cb = self.person_checkboxes.get((group, person))
                checked = cb.isChecked() if cb else True

                if checked:
                    effective.add(person)
                    break

        for person in self.ungrouped:
            cb = self.ungrouped_rows.get(person)
            if cb is None or cb.isChecked():
                effective.add(person)

        if effective == set(self.people):
            return None

        return effective

    def clear_selection(self):
        for cb in self.group_checkboxes.values():
            cb.setChecked(True)

        for cb in self.person_checkboxes.values():
            cb.setChecked(True)

        for cb in self.ungrouped_rows.values():
            cb.setChecked(True)

        self.group_enabled = {g: True for g in self.groups}

        self._refresh_visuals()
        self.selection_changed.emit()