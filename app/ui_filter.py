from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QPushButton, QComboBox, QDateEdit,
    QSizePolicy
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem

from .ui_selector import PersonGroupSelector


# RangeSpinBox: Off = None
class RangeSpinBox(QSpinBox):
    def __init__(self, minimum: int, maximum: int, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._min = minimum
        self._max = maximum

        self.setRange(self._min, self._max)
        self.setSpecialValueText("Off")
        self.setValue(self._min)

    def textFromValue(self, value: int) -> str:
        if value in (self._min, self._max):
            return "Off"
        return str(value)

    def effective_value(self):
        value = self.value()
        if value in (self._min, self._max):
            return None
        return value

    def setEffectiveValue(self, value):
        if value is None:
            self.setValue(self._min)
        else:
            self.setValue(value)


# OffDateEdit: DateEdit with Off = None
class OffDateEdit(QDateEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._date: QDate | None = None

        self.setDisplayFormat("dd.MM.yyyy")
        self.setCalendarPopup(True)
        self.lineEdit().setText("Off")

        self.lineEdit().editingFinished.connect(self._line_edit_finished)
        self.dateChanged.connect(self._calendar_selected)

    def showEvent(self, event):
        super().showEvent(event)
        if self._date is None:
            self.blockSignals(True)
            self.lineEdit().setText("Off")
            self.blockSignals(False)

    def _line_edit_finished(self):
        text = self.lineEdit().text().strip().lower()
        if text in ("off", "", "none"):
            self.clear()
            return

        date = QDate.fromString(text, "dd.MM.yyyy")
        if date.isValid():
            self._set_real_date(date)
        else:
            self.clear()

    def _calendar_selected(self, date: QDate):
        if date.isValid():
            self._set_real_date(date)

    def _set_real_date(self, date: QDate):
        self._date = date
        self.blockSignals(True)
        super().setDate(date)
        self.blockSignals(False)

    def clear(self):
        self._date = None
        self.blockSignals(True)
        self.lineEdit().setText("Off")
        self.blockSignals(False)

    def date(self):
        return self._date

    def setDate(self, date: QDate | None):
        if date is None:
            self.clear()
        else:
            self._set_real_date(date)


# FilterPanel widget
class FilterPanel(QWidget):
    filters_changed = Signal(dict)

    def __init__(self, storage):
        super().__init__()
        self.storage = storage

        # Latched filters (Apply-only)
        self._active_filters: dict = {}

        root_layout = QVBoxLayout(self)

        # split_layout used for refresh
        split_container = QWidget()
        self.split_layout = QHBoxLayout(split_container)
        self.split_layout.setContentsMargins(0, 0, 0, 0)
        self.split_layout.setAlignment(Qt.AlignTop)
        root_layout.addWidget(split_container)

        # -------- LEFT --------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.split_layout.addWidget(left_panel, 3)
        self.split_layout.setStretch(0, 1)

        # Sort by row
        sort_row = QHBoxLayout()
        sort_label = QLabel("Sort by:")
        sort_row.addWidget(sort_label)
        sort_row.addStretch(1)
        self.sort_reset_button = QPushButton("↺")
        self.sort_reset_button.setToolTip("Reset Sort filter")
        self.sort_reset_button.setFixedSize(28, 28)
        sort_row.addWidget(self.sort_reset_button)
        left_layout.addLayout(sort_row)

        self.sort_by_combo = QComboBox()

        # Use an explicit model so we can enable/disable entries
        self._sort_model = QStandardItemModel()
        sort_items = [
            "Newest quote",
            "Oldest quote",
            "Newest added (Can only check one!)",
            "Oldest added (Can only check one!)",
        ]
        for text in sort_items:
            item = QStandardItem(text)
            item.setEditable(False)
            self._sort_model.appendRow(item)

        self.sort_by_combo.setModel(self._sort_model)

        # Indexes of the "added" sort options
        self._added_sort_indexes = [2, 3]

        left_layout.addWidget(self.sort_by_combo)

        # Date Range row
        date_label_row = QHBoxLayout()
        date_label = QLabel("Date Range:")
        date_label_row.addWidget(date_label)
        date_label_row.addStretch(1)
        self.date_reset_button = QPushButton("↺")
        self.date_reset_button.setToolTip("Reset Date Range")
        self.date_reset_button.setFixedSize(28, 28)
        date_label_row.addWidget(self.date_reset_button)
        left_layout.addLayout(date_label_row)

        date_layout = QHBoxLayout()
        self.date_from_input = OffDateEdit()
        self.date_to_input = OffDateEdit()
        date_layout.addWidget(self.date_from_input)
        date_layout.addWidget(self.date_to_input)
        left_layout.addLayout(date_layout)

        # Character Length row
        char_label_row = QHBoxLayout()
        char_label = QLabel("Character Length (1–10000):")
        char_label_row.addWidget(char_label)
        char_label_row.addStretch(1)
        self.char_reset_button = QPushButton("↺")
        self.char_reset_button.setToolTip("Reset Character Length")
        self.char_reset_button.setFixedSize(28, 28)
        char_label_row.addWidget(self.char_reset_button)
        left_layout.addLayout(char_label_row)

        char_layout = QHBoxLayout()
        self.char_from_input = RangeSpinBox(0, 10001)
        self.char_to_input = RangeSpinBox(0, 10001)
        char_layout.addWidget(self.char_from_input)
        char_layout.addWidget(self.char_to_input)
        left_layout.addLayout(char_layout)

        left_layout.addStretch(1)
        self.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Fixed
        )

        # -------- RIGHT (PEOPLE) --------
        people_panel = QWidget()
        people_panel_layout = QVBoxLayout(people_panel)
        people_label_row = QHBoxLayout()
        people_label = QLabel("People / Groups:")
        people_label_row.addWidget(people_label)
        people_label_row.addStretch(1)
        self.people_reset_button = QPushButton("↺")
        self.people_reset_button.setToolTip("Reset People selection")
        self.people_reset_button.setFixedSize(28, 28)
        people_label_row.addWidget(self.people_reset_button)
        people_panel_layout.addLayout(people_label_row)

        # Place selector directly; it manages its own layout/scrolling
        self.person_group_selector = PersonGroupSelector(self.storage)
        self.person_group_selector.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Expanding
        )
        people_panel_layout.addWidget(self.person_group_selector)
        self.split_layout.addWidget(people_panel, 2)
        self.split_layout.setStretch(1, 1)

        # connect selection-changed signal(s)
        self._connect_person_selector()

        # Ensure state is correct on startup
        self.on_people_selection_changed()

        # -------- Keywords --------
        operators_text = (
            "Operators:\n"
            "* – wildcard for any sequence of characters\n"
            "? – single-character wildcard\n"
            "AND (or [space]) – requires both terms\n"
            "OR – includes either term\n"
            "NOT (or -) – excludes a term\n"
            "() – group terms\n"
            "Example: f?ke AND (love OR affection) NOT poetry"
        )

        keyword_label_row = QHBoxLayout()
        keyword_label = QLabel("🛈 Keyword Filter:")
        keyword_label.setToolTip(operators_text)
        keyword_label_row.addWidget(keyword_label)
        keyword_label_row.addStretch(1)
        self.keyword_reset_button = QPushButton("↺")
        self.keyword_reset_button.setToolTip("Reset Keywords")
        self.keyword_reset_button.setFixedSize(28, 28)
        keyword_label_row.addWidget(self.keyword_reset_button)
        root_layout.addLayout(keyword_label_row)

        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("Enter keywords")
        self.keyword_input.setToolTip(operators_text)
        root_layout.addWidget(self.keyword_input)

        # -------- Buttons --------
        buttons_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply Filters")
        self.clear_button = QPushButton("✖")
        self.clear_button.setFixedSize(30, 30)
        buttons_layout.addWidget(self.apply_button)
        buttons_layout.addWidget(self.clear_button)
        root_layout.addLayout(buttons_layout)

        # set pointing-hand cursor for buttons
        self._set_buttons_pointing_cursor()

        # --- Connections ---
        self.apply_button.clicked.connect(self.apply_filters)
        self.clear_button.clicked.connect(self.clear_filters)

        # Per-panel reset buttons
        self.sort_reset_button.clicked.connect(self.reset_sort)
        self.date_reset_button.clicked.connect(self.reset_date_range)
        self.char_reset_button.clicked.connect(self.reset_char_length)
        self.people_reset_button.clicked.connect(self.reset_people)
        self.keyword_reset_button.clicked.connect(self.reset_keywords)

        self.date_from_input.dateChanged.connect(self.on_date_from_changed)
        self.date_to_input.dateChanged.connect(self.on_date_to_changed)
        self.char_from_input.valueChanged.connect(self.on_char_from_changed)
        self.char_to_input.valueChanged.connect(self.on_char_to_changed)

    # helpers
    def _set_buttons_pointing_cursor(self):
        # set pointing-hand cursor for all QPushButton children
        for btn in self.findChildren(QPushButton):
            btn.setCursor(Qt.PointingHandCursor)

    def _clear_layout(self, layout):
        # remove and delete all widgets from layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _connect_person_selector(self):
        connected = False
        if hasattr(self.person_group_selector, "selectionChanged"):
            try:
                self.person_group_selector.selectionChanged.connect(
                    self.on_people_selection_changed
                )
                connected = True
            except Exception:
                connected = False

        if not connected and hasattr(self.person_group_selector, "selection_changed"):
            try:
                self.person_group_selector.selection_changed.connect(
                    self.on_people_selection_changed
                )
                connected = True
            except Exception:
                connected = False

    def on_date_from_changed(self, _):
        if self.date_from_input.date() and self.date_to_input.date():
            if self.date_from_input.date() > self.date_to_input.date():
                self.date_to_input.setDate(self.date_from_input.date())

    def on_date_to_changed(self, _):
        if self.date_from_input.date() and self.date_to_input.date():
            if self.date_to_input.date() < self.date_from_input.date():
                self.date_from_input.setDate(self.date_to_input.date())

    def on_char_from_changed(self, value):
        if value and self.char_to_input.value() and value > self.char_to_input.value():
            self.char_to_input.setValue(value)

    def on_char_to_changed(self, value):
        if value and self.char_from_input.value() and value < self.char_from_input.value():
            self.char_from_input.setValue(value)

    def on_people_selection_changed(self):
        # Disable 'added' sort options when more than one person is selected.
        multiple_people = True

        try:
            if hasattr(self.person_group_selector, "get_effective_people"):
                people = self.person_group_selector.get_effective_people()
                if people is None:
                    multiple_people = True
                else:
                    try:
                        multiple_people = len(people) > 1
                    except Exception:
                        multiple_people = True
            else:
                multiple_people = True
        except Exception:
            multiple_people = True

        for index in self._added_sort_indexes:
            item: QStandardItem | None = self._sort_model.item(index)
            if item is not None:
                item.setEnabled(not multiple_people)

        if multiple_people and self.sort_by_combo.currentIndex() in self._added_sort_indexes:
            self.sort_by_combo.setCurrentIndex(0)

    # Apply / Clear
    def apply_filters(self):
        # ensure sort selection valid for current people selection
        try:
            people = (
                self.person_group_selector.get_effective_people()
                if hasattr(self.person_group_selector, "get_effective_people")
                else None
            )
            if people is None:
                many = True
            else:
                many = len(people) > 1
        except Exception:
            many = True

        if many and self.sort_by_combo.currentIndex() in self._added_sort_indexes:
            self.sort_by_combo.setCurrentIndex(0)

        self._active_filters = {
            "sort": self.sort_by_combo.currentText(),
            "date_from": self.date_from_input.date(),
            "date_to": self.date_to_input.date(),
            "char_from": self.char_from_input.effective_value(),
            "char_to": self.char_to_input.effective_value(),
            "keywords": self.keyword_input.text() or None,
            "people": (
                self.person_group_selector.get_effective_people()
                if hasattr(self.person_group_selector, "get_effective_people")
                else None
            ),
        }

        self.filters_changed.emit(self._active_filters)

    def clear_filters(self):
        # Reset sort
        self.sort_by_combo.setCurrentIndex(0)

        # Clear people selection
        if hasattr(self.person_group_selector, "clear_selection"):
            try:
                self.person_group_selector.clear_selection()
            except Exception:
                import logging
                logging.exception("self.person_group_selector.clear_selection() failed")
                raise

        # Clear other controls
        self.date_from_input.clear()
        self.date_to_input.clear()
        self.char_from_input.setEffectiveValue(None)
        self.char_to_input.setEffectiveValue(None)
        self.keyword_input.clear()

        # Re-evaluate sort availability
        self.on_people_selection_changed()

        self._active_filters = {}
        self.filters_changed.emit(self._active_filters)

    # Per-panel resets
    def reset_sort(self):
        # reset only sort controls
        self.sort_by_combo.setCurrentIndex(0)

    def reset_date_range(self):
        # reset only date range
        self.date_from_input.clear()
        self.date_to_input.clear()

    def reset_char_length(self):
        # reset only character length
        self.char_from_input.setEffectiveValue(None)
        self.char_to_input.setEffectiveValue(None)

    def reset_people(self):
        # reset people selector
        if hasattr(self.person_group_selector, "clear_selection"):
            try:
                self.person_group_selector.clear_selection()
            except Exception:
                import logging
                logging.exception("self.person_group_selector.clear_selection() failed")
        self.on_people_selection_changed()

    def reset_keywords(self):
        # reset keyword input
        self.keyword_input.clear()

    # MainWindow calls this
    def get_filters(self):
        return self._active_filters

    # In-place refresh API
    def refresh(self):
        # Refresh people/groups selector after storage.reload_index()
        try:
            if hasattr(self.person_group_selector, "reload_from_storage"):
                self.person_group_selector.reload_from_storage(self.storage)
            else:
                try:
                    self.split_layout.removeWidget(self.person_group_selector)
                    self.person_group_selector.deleteLater()
                except Exception:
                    pass

                self.person_group_selector = PersonGroupSelector(self.storage)
                self.person_group_selector.setSizePolicy(
                    QSizePolicy.Preferred,
                    QSizePolicy.Expanding
                )
                self.split_layout.addWidget(self.person_group_selector, 2)
                self._connect_person_selector()

            self.on_people_selection_changed()

        except Exception as e:
            print("FilterPanel refresh failed:", e)