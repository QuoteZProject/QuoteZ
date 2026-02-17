from pathlib import Path

from PySide6.QtWidgets import (
    QListWidget, QListWidgetItem, QGraphicsDropShadowEffect, QApplication
)
from PySide6.QtGui import (
    QPixmap, QIcon, QTextCursor, QTextImageFormat,
    QPainter, QPainterPath, QTextDocument
)
from PySide6.QtCore import Qt, QPoint, QEvent, QUrl

from .xdg_data import get_resource_file

# assets path
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
ASSETS = _PACKAGE_ROOT / "assets"
DEFAULT_AVATAR = get_resource_file("default.png", package_root=_PACKAGE_ROOT)

# property key for inline :name: tag
IMAGE_TAG_PROPERTY = 12345


# return pixmap sized (width, height) with rounded corners
def _rounded_pixmap_from_pixmap(pix: QPixmap, width: int, height: int, radius: int) -> QPixmap:
    if pix.isNull():
        p = QPixmap(width, height)
        p.fill(Qt.transparent)
        return p

    # scale to cover target
    scaled = pix.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    target = QPixmap(width, height)
    target.fill(Qt.transparent)

    painter = QPainter(target)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setRenderHint(QPainter.Antialiasing, True)

    path = QPainterPath()
    path.addRoundedRect(0.0, 0.0, float(width), float(height), float(radius), float(radius))
    painter.setClipPath(path)
    # draw scaled, cropped if necessary
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return target


class ColonSuggestionPopup(QListWidget):
    def __init__(self, text_edit, storage, parent=None):
        # popup parent=text_edit so it stays on top
        super().__init__(parent or text_edit)
        self.text_edit = text_edit
        self.storage = storage

        # tooltip-like window
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        # allow transparent bg
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # no focus
        self.setFocusPolicy(Qt.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMaximumHeight(180)
        self.setMinimumWidth(220)

        # styling
        self.setStyleSheet(
            """
            QListWidget {
                background-color: rgba(28, 30, 33, 240);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 10px;
                padding: 6px;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 8px;
            }
            QListWidget::item:selected {
                background-color: rgba(255,255,255,0.06);
            }
            QListWidget::item:hover {
                background-color: rgba(255,255,255,0.03);
            }
            """
        )

        # drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(Qt.black)
        self.setGraphicsEffect(shadow)

        # watch text_edit focus
        self.text_edit.installEventFilter(self)

        # hide on app focus change
        app = QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._on_focus_changed)

        # activation handlers
        self.itemClicked.connect(self._on_item_clicked)
        self.itemActivated.connect(self._on_item_activated)

        self.prefix = ""
        self.names = []

        self.hide()

    def eventFilter(self, obj, event):
        # hide on text_edit focus out
        if obj is self.text_edit:
            if event.type() == QEvent.FocusOut:
                self.hide()
        return super().eventFilter(obj, event)

    def _on_focus_changed(self, old_widget, new_widget):
        # hide if app/window focus changed
        if not self.isVisible():
            return

        if new_widget is None:
            self.hide()
            return

        try:
            new_win = new_widget.window()
            my_win = self.text_edit.window()
            if new_win is not my_win:
                self.hide()
        except Exception:
            # hide on error
            self.hide()

    def show_for_prefix(self, prefix: str):
        self.prefix = prefix.lower()
        self.clear()

        self.names = sorted(self.storage.people.keys())

        filtered = [
            name for name in self.names
            if name.lower().startswith(self.prefix)
        ]

        if not filtered:
            self.hide()
            return

        for name in filtered:
            avatar_path = self.storage.people.get(name, DEFAULT_AVATAR)
            raw_pix = QPixmap(str(avatar_path))
            # small rounded icon 16x16
            rounded = _rounded_pixmap_from_pixmap(raw_pix, 16, 16, 4)

            item = QListWidgetItem(name)
            # set icon
            item.setIcon(QIcon(rounded))
            self.addItem(item)

        self.setCurrentRow(0)
        self._move_to_cursor()
        self.show()

    def _move_to_cursor(self):
        cursor = self.text_edit.textCursor()
        rect = self.text_edit.cursorRect(cursor)
        pos = self.text_edit.mapToGlobal(rect.bottomRight())
        # small offset
        self.move(pos + QPoint(4, 4))

    # Mouse/activation handlers behave like Enter
    def _on_item_clicked(self, item: QListWidgetItem):
        # require left click
        if QApplication.mouseButtons() & Qt.LeftButton:
            name = item.text()
            # insert and close
            try:
                self.insert_avatar_inline(name)
            finally:
                self.hide()

    def _on_item_activated(self, item: QListWidgetItem):
        # keyboard activation
        name = item.text()
        try:
            self.insert_avatar_inline(name)
        finally:
            self.hide()

    def move_up(self):
        if not self.isVisible():
            return
        row = (self.currentRow() - 1) % self.count()
        self.setCurrentRow(row)

    def move_down(self):
        if not self.isVisible():
            return
        row = (self.currentRow() + 1) % self.count()
        self.setCurrentRow(row)

    def accept_current(self):
        if not self.isVisible():
            return None

        item = self.currentItem()
        if not item:
            return None

        name = item.text()
        self.hide()
        return name

    # insert avatar and tag
    def insert_avatar_inline(self, name: str):
        cursor = self.text_edit.textCursor()

        # delete ':'+prefix
        del_len = len(self.prefix) + 1  # +1 for ':'
        cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, del_len)
        cursor.removeSelectedText()

        avatar_path = self.storage.people.get(name, DEFAULT_AVATAR)

        # size from font metrics
        fm = self.text_edit.fontMetrics()
        h = fm.height()
        size = max(12, int(h))
        radius = max(3, int(size * 0.25))

        raw_pix = QPixmap(str(avatar_path))
        rounded = _rounded_pixmap_from_pixmap(raw_pix, size, size, radius)

        # register image as document resource
        url_str = f"avatar://{name}?w={size}&r={radius}"
        qurl = QUrl(url_str)
        # add QImage resource
        self.text_edit.document().addResource(QTextDocument.ImageResource, qurl, rounded.toImage())

        img_fmt = QTextImageFormat()
        img_fmt.setName(qurl.toString())

        img_fmt.setHeight(float(size))
        img_fmt.setWidth(float(size))

        # set tag property
        img_fmt.setProperty(IMAGE_TAG_PROPERTY, f":{name}:")

        cursor.insertImage(img_fmt)
        cursor.insertText(" ")