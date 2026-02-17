import time
import math
from functools import partial
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QScrollArea, QLabel, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QPoint

from .storage import QuoteStorage
from .ui_quote_item import QuoteItem
from .quote_loader import QuoteLoaderThread
from .icons import icon
from .ui_filter import FilterPanel
from .xdg_data import get_config_file  # use xdg helper

# Main window with infinite scroll and background loading
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("QuoteZ")
        self.resize(800, 600)

        # package root
        self.package_root = Path(__file__).resolve().parent.parent

        # -------- State --------
        self.storage = QuoteStorage()
        self.storage.load_index()

        self.page_size = 20
        self.current_page = 0
        self.shown_indices = set()
        self.loading = False
        self.loader_thread = None
        self.search_version = 0
        self.seen_keys = set()
        self.active_filters = {}
        self.no_more_pages = False

        # skeletons + throttling
        self._skeletons = []
        self.pending_pages = set()
        self._skeletons_pending = False
        self._last_check_time = 0.0
        self._scroll_throttle = 0.08
        self._approx_item_height = 96

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(lambda: self._perform_search(self.search.text()))

        # -------- UI --------
        central = QWidget()
        self.setCentralWidget(central)
        self.central_layout = QVBoxLayout(central)
        main = self.central_layout

        self._setup_top_bar(main)

        self.filter_panel = FilterPanel(self.storage)
        self.filter_panel.setVisible(False)
        main.addWidget(self.filter_panel)
        self.filter_panel.filters_changed.connect(self.on_filters_changed)

        self._setup_scroll_area(main)

        # Initial search / fill
        self.on_search_changed(self.search.text())

    # STORAGE REFRESH
    def refresh_storage(self):
        # Reload filesystem data and refresh UI
        self.storage.load_index()
        try:
            self.filter_panel.refresh()
        except Exception:
            import logging as _logging
            _logging.exception("self.filter_panel.refresh() failed")
            raise

        self.search_version += 1
        self.current_page = 0
        self.shown_indices.clear()
        self.seen_keys.clear()
        self.no_more_pages = False
        self.pending_pages.clear()

        # allow layout to reflow
        self.inner.setMinimumHeight(0)

        self._clear_quotes()
        QTimer.singleShot(0, self.load_next_page)

    # UI Setup
    def _setup_top_bar(self, layout):
        top = QHBoxLayout()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search quotes…")
        self.search.textChanged.connect(lambda _: self.search_timer.start(150))

        # create icon-only button
        def make_icon_button(key: str, tooltip: str, outer_size: int = 32, icon_size: int = 16) -> QPushButton:
            btn = QPushButton()
            btn.setToolTip(tooltip)
            btn.setFlat(True)
            btn.setCursor(Qt.PointingHandCursor)
            icon(btn, key, icon_size)
            btn.setFixedSize(outer_size, outer_size)
            return btn

        filter_btn = make_icon_button("filter", "Filter", outer_size=32, icon_size=16)
        settings_btn = make_icon_button("settings", "Settings", outer_size=32, icon_size=16)
        add_btn = make_icon_button("add", "Add quote", outer_size=32, icon_size=16)

        top.addWidget(self.search, 1)
        top.addWidget(filter_btn)
        top.addWidget(add_btn)
        top.addWidget(settings_btn)
        layout.addLayout(top)

        filter_btn.clicked.connect(self.toggle_filter_panel)
        settings_btn.clicked.connect(self.open_settings)
        add_btn.clicked.connect(self.add_quote)

    def toggle_filter_panel(self):
        self.filter_panel.setVisible(not self.filter_panel.isVisible())

    def _setup_scroll_area(self, layout):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.inner = QWidget()
        self.inner_layout = QVBoxLayout(self.inner)
        self.inner_layout.setSpacing(10)
        self.inner_layout.setContentsMargins(0, 0, 0, 0)
        self.inner_layout.setAlignment(Qt.AlignTop)

        self.scroll.setWidget(self.inner)
        layout.addWidget(self.scroll)

        # connect scroll handlers
        self.scroll.verticalScrollBar().valueChanged.connect(self.check_scroll)
        self.scroll.viewport().resizeEvent = self._viewport_resize_wrapper(self.scroll.viewport().resizeEvent)

    def _viewport_resize_wrapper(self, original_resize):
        def wrapped(event):
            try:
                if original_resize:
                    original_resize(event)
            except Exception:
                pass
            QTimer.singleShot(10, self.check_scroll)
        return wrapped

    # Search / Filters
    def on_filters_changed(self, filters):
        self.active_filters = filters
        self.on_search_changed(self.search.text())

    def on_search_changed(self, text):
        self.search_version += 1
        self.seen_keys.clear()
        self.current_page = 0
        self.shown_indices.clear()
        self.no_more_pages = False
        self.pending_pages.clear()

        self.inner.setMinimumHeight(0)

        self._clear_quotes()
        QTimer.singleShot(0, self.load_next_page)

    def _clear_quotes(self):
        self._clear_skeletons()
        while self.inner_layout.count():
            widget = self.inner_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()

    # Skeleton helpers
    def _add_skeletons(self, count=None):
        # Add placeholders to avoid layout jumps
        if self._skeletons_pending:
            return
        viewport_h = self.scroll.viewport().height()
        approx = max(40, int(self._approx_item_height))
        if count is None:
            count = int(math.ceil(viewport_h / approx)) + 2
        count = min(count, self.page_size)
        approx_height = approx
        for _ in range(count):
            lbl = QLabel("Loading…")
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            lbl.setFixedHeight(approx_height)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: gray; font-style: italic;")
            self.inner_layout.addWidget(lbl)
            self._skeletons.append(lbl)
        self._skeletons_pending = True
        QTimer.singleShot(50, self.check_scroll)

    def _clear_skeletons(self):
        for w in self._skeletons:
            try:
                self.inner_layout.removeWidget(w)
                w.deleteLater()
            except Exception:
                pass
        self._skeletons = []
        self._skeletons_pending = False

    # Finalize when no more pages
    def _finalize_no_more_pages(self):
        # remove skeletons and ensure inner widget fills viewport
        self._clear_skeletons()

        for i in reversed(range(self.inner_layout.count())):
            item = self.inner_layout.itemAt(i)
            if item is None:
                continue
            try:
                if item.spacerItem() is not None:
                    self.inner_layout.takeAt(i)
            except Exception:
                pass

        self.inner.adjustSize()
        viewport_h = self.scroll.viewport().height()
        content_h = self.inner.sizeHint().height()
        min_h = max(content_h, viewport_h)
        self.inner.setMinimumHeight(min_h)

        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    # Loading
    def check_scroll(self):
        # Throttled trigger to load next page when near bottom
        now = time.time()
        if now - self._last_check_time < self._scroll_throttle:
            return
        self._last_check_time = now

        if self.no_more_pages:
            return

        if self.inner_layout.count() == 0:
            self._add_skeletons()
            QTimer.singleShot(0, self.load_next_page)
            return

        last_index = self.inner_layout.count() - 1
        last_item = self.inner_layout.itemAt(last_index)
        if last_item is None:
            return

        last_widget = last_item.widget()
        if last_widget is None:
            return

        try:
            top_left_in_view = last_widget.mapTo(self.scroll.viewport(), QPoint(0, 0))
        except Exception:
            bar = self.scroll.verticalScrollBar()
            if bar.value() >= bar.maximum() - 50:
                if not self._skeletons_pending:
                    self._add_skeletons()
                QTimer.singleShot(0, self.load_next_page)
            return

        bottom_in_view = top_left_in_view.y() + last_widget.height()
        viewport_height = self.scroll.viewport().height()

        prefetch_threshold = 300
        if bottom_in_view <= viewport_height + prefetch_threshold:
            if not self._skeletons_pending:
                self._add_skeletons(count=None)
            QTimer.singleShot(0, self.load_next_page)
            return

        bar = self.scroll.verticalScrollBar()
        if bar.value() >= bar.maximum() - 20:
            if not self._skeletons_pending:
                self._add_skeletons()
            QTimer.singleShot(0, self.load_next_page)

    def load_next_page(self):
        # Start background loader for next page
        if self.no_more_pages:
            return

        start = self.current_page * self.page_size
        end = start + self.page_size

        if start >= len(self.storage.index):
            self.no_more_pages = True
            self._finalize_no_more_pages()
            self.loading = False
            return

        if start in self.pending_pages:
            return

        if self.loader_thread and self.loader_thread.isRunning():
            return

        self.pending_pages.add(start)

        query = self.search.text()
        filters = self.filter_panel.get_filters()

        self.loading = True
        self.loader_thread = QuoteLoaderThread(
            query=query,
            storage=self.storage,
            start_idx=start,
            end_idx=end,
            search_version=self.search_version,
            filters=filters,
        )
        self.loader_thread.quotes_loaded.connect(partial(self.on_thread_finished, start))
        self.loader_thread.start()

    def on_thread_finished(self, start, quotes, version):
        # Handle loader completion for a specific start index
        try:
            self.pending_pages.discard(start)
        except Exception:
            pass

        if version != self.search_version:
            self.loading = False
            self._clear_skeletons()
            return

        self._clear_skeletons()

        if not quotes:
            self.no_more_pages = True
            self._finalize_no_more_pages()
            self.loading = False
            return

        seen_keys = set()
        unique_quotes = []
        for idx, quote in quotes:
            key = self.storage.quote_key(quote)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_quotes.append((idx, quote))

        self._add_quotes_to_ui(unique_quotes)

        if start == self.current_page * self.page_size:
            self.current_page += 1

        self.loading = False

        QTimer.singleShot(120, self.check_scroll)

    def _add_quotes_to_ui(self, quotes):
        # resolve default avatar
        default_avatar = (self.package_root / "assets" / "default.png").resolve()
        added = 0
        for idx, quote in quotes:
            if idx not in self.shown_indices:
                self.shown_indices.add(idx)
                item = QuoteItem(quote, self.storage.people, default_avatar, self.storage)
                self.inner_layout.addWidget(item)
                added += 1

        QTimer.singleShot(30 if added else 10, self.check_scroll)

    def _perform_search(self, text):
        self.on_search_changed(text)

    # Helpers
    def open_settings(self):
        # use xdg-aware config path
        cfg = get_config_file(filename="settings.json", package_root=self.package_root)
        from .ui_settings import SettingsDialog
        dlg = SettingsDialog(cfg, self.storage, self)
        if dlg.exec():
            self.refresh_storage()

    def add_quote(self):
        from .ui_add_quote import QuoteDialog
        dlg = QuoteDialog(self.storage, self)
        if dlg.exec():
            self.refresh_storage()
