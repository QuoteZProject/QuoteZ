from PySide6.QtWidgets import QLayout
from PySide6.QtCore import QRect, QSize, Qt

class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self.items = []
        self._height = 0
        self.setSpacing(spacing)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, i):
        return self.items[i] if i < len(self.items) else None

    def takeAt(self, i: int) -> QLayoutItem | None:
        # remove and delete item at index i
        if i < 0 or i >= len(self.items):
            return None

        item = self.items.pop(i)

        widget = item.widget()
        if widget:
            # detach widget and schedule deletion
            widget.setParent(None)
            widget.deleteLater()

        # delete plain QLayoutItem if no widget
        if not widget:
            del item

        return item

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._height = self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return QSize(400, self._height)

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0

        for item in self.items:
            size = item.sizeHint()
            if x + size.width() > rect.x() + rect.width():
                x = rect.x()
                y += line_height + self.spacing()
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(x, y, size.width(), size.height()))

            x += size.width() + self.spacing()
            line_height = max(line_height, size.height())

        return y + line_height - rect.y()