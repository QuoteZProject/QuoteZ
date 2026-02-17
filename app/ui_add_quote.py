from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QDateEdit, QMessageBox
)
from PySide6.QtCore import QDate, Qt, QEvent, QUrl
from PySide6.QtGui import (
    QTextImageFormat, QImage, QTextCursor,
    QPixmap, QPainter, QPainterPath, QTextDocument
)
from typing import Set, Optional
import re

from .timestamp_finder import find_timestamp_seconds, ensure_timestamp_in_url
from .quote_utils import (
    parse_masked_timestamp,
    seconds_to_mask_string,
    is_valid_url,
    # don't call find_colon_tags/replace_colon_tags from quote_utils
    ensure_first_is_quote_tag,
    has_real_text_outside_tags,
)
from .write_manager import QuoteModifier
from .ui_suggestion import ColonSuggestionPopup, IMAGE_TAG_PROPERTY


def _rounded_pixmap_from_pixmap(pix: QPixmap, width: int, height: int, radius: int) -> QPixmap:
    """Return a pixmap sized (width, height) with rounded corners (radius)."""
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


class TimeEditExtended(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setInputMask("000:00:00")
        self.setText("000:00:00")

    def to_seconds(self):
        return parse_masked_timestamp(self.text())


class QuoteDialog(QDialog):

    def __init__(self, storage, parent=None, quote=None):
        super().__init__(parent)

        self.storage = storage
        self.root = self.storage.root
        self.modifier = QuoteModifier(self.storage.root)
        self.quote = quote

        self.setWindowTitle("Edit Quote" if quote else "Add Quote")
        self.resize(700, 480)

        self._ts_user_edited = False

        layout = QVBoxLayout(self)

        # UI setup
        label_width = 110
        input_width = 140

        date_row = QHBoxLayout()
        date_label = QLabel("Date:")
        date_label.setFixedWidth(label_width)
        self.date_edit = QDateEdit()
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setFixedWidth(input_width)
        self.date_edit.setDate(
            QDate.fromString(quote.date, "yyyy-MM-dd") if quote else QDate.currentDate()
        )
        date_row.addWidget(date_label)
        date_row.addStretch()
        date_row.addWidget(self.date_edit)
        layout.addLayout(date_row)

        ts_row = QHBoxLayout()
        ts_label = QLabel("Timestamp:")
        ts_label.setFixedWidth(label_width)
        self.ts_edit = TimeEditExtended()
        self.ts_edit.setFixedWidth(input_width)
        self.ts_edit.textEdited.connect(self._on_ts_user_edited)
        if quote:
            self.ts_edit.setText(quote.timestamp)
        self.url_ts_button = QPushButton("↺")
        self.url_ts_button.setFixedWidth(32)
        self.url_ts_button.clicked.connect(self._force_timestamp_from_url)
        ts_row.addWidget(ts_label)
        ts_row.addStretch()
        ts_row.addWidget(self.ts_edit)
        ts_row.addWidget(self.url_ts_button)
        layout.addLayout(ts_row)

        url_row = QHBoxLayout()
        url_label = QLabel("URL:")
        url_label.setFixedWidth(label_width)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com/video?t=60")
        self.url_edit.editingFinished.connect(self._auto_fill_timestamp_from_url)
        if quote:
            self.url_edit.setText(quote.url)
        url_row.addWidget(url_label)
        url_row.addStretch()
        url_row.addWidget(self.url_edit)
        layout.addLayout(url_row)

        layout.addWidget(QLabel("Quote text:"))
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(":Speaker 1: Hello world")
        self.text_edit.setToolTip("Use :name: to tag speakers.")
        layout.addWidget(self.text_edit, 1)

        # suggestion popup
        self.suggestion_popup = ColonSuggestionPopup(self.text_edit, self.storage)
        self.text_edit.textChanged.connect(self._on_text_changed)
        self.text_edit.installEventFilter(self)

        # populate existing quote
        if quote:
            original_colon_text = "".join(
                f":{seg.speaker}:{seg.text}" if seg.speaker else seg.text
                for seg in quote.segments
            )
            self._populate_text_edit_from_colon_text(original_colon_text)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        action_btn = QPushButton("Save changes" if quote else "Add Quote")
        action_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(action_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    # Autocomplete

    def _on_text_changed(self):
        cursor = self.text_edit.textCursor()
        text = cursor.block().text()
        pos = cursor.positionInBlock()

        left = text[:pos]
        if ":" not in left:
            self.suggestion_popup.hide()
            return

        idx = left.rfind(":")
        prefix = left[idx + 1:]

        if " " in prefix:
            self.suggestion_popup.hide()
            return

        self.suggestion_popup.show_for_prefix(prefix)

    def eventFilter(self, obj, event):
        if obj is self.text_edit and event.type() == QEvent.KeyPress:
            if self.suggestion_popup.isVisible():

                if event.key() == Qt.Key_Down:
                    self.suggestion_popup.move_down()
                    return True

                if event.key() == Qt.Key_Up:
                    self.suggestion_popup.move_up()
                    return True

                if event.key() == Qt.Key_Tab:
                    self.suggestion_popup.move_down()
                    return True

                if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                    # On accept, convert immediately to canonical quote tag
                    name = self.suggestion_popup.accept_current()
                    if name:
                        self._insert_quote_tag(name)
                        return True

                if event.key() == Qt.Key_Escape:
                    self.suggestion_popup.hide()

        return super().eventFilter(obj, event)

    # Helpers

    def _existing_people(self) -> Set[str]:
        return set(self.storage.people.keys())

    def _on_ts_user_edited(self, _text: str):
        self._ts_user_edited = True

    def _auto_fill_timestamp_from_url(self):
        url = self.url_edit.text().strip()
        if not url or self._ts_user_edited or self.ts_edit.text().strip() != "000:00:00":
            return
        sec, _ = find_timestamp_seconds(url)
        if sec is not None:
            self.ts_edit.setText(seconds_to_mask_string(sec))

    def _force_timestamp_from_url(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a URL first.")
            return
        sec, _ = find_timestamp_seconds(url)
        if sec is None:
            QMessageBox.warning(self, "No timestamp in URL", "URL has no ?t=...")
            return
        self.ts_edit.setText(seconds_to_mask_string(sec))
        self._ts_user_edited = False

    # Populate QTextEdit with images for :name: tags

    # Insert :name: as inline image or canonical tag {quote:"name"}.
    def _populate_text_edit_from_colon_text(self, colon_text: str):
        self.text_edit.clear()
        cursor = self.text_edit.textCursor()
        cursor.beginEditBlock()

        pattern = re.compile(r":([^:\s][^:]*?):")

        idx = 0
        for m in pattern.finditer(colon_text):
            start, end = m.span()
            name = m.group(1)

            # preceding plain text
            if start > idx:
                cursor.insertText(colon_text[idx:start])

            # left space unless at start
            if start != 0:
                cursor.insertText(" ")

            # find avatar
            avatar_path: Optional[Path] = None
            people = getattr(self.storage, "people", {}) or {}
            person_entry = people.get(name)

            if isinstance(person_entry, (str, Path)):
                p = Path(person_entry)
                if p.is_file():
                    avatar_path = p
            elif isinstance(person_entry, dict):
                for k in ("avatar", "pfp", "image", "avatar_path"):
                    val = person_entry.get(k)
                    if isinstance(val, (str, Path)):
                        p = Path(val)
                        if p.is_file():
                            avatar_path = p
                            break

            if avatar_path is None:
                candidate = Path(self.root) / name
                for fname in ("avatar.png", "avatar.jpg", "pfp.png", "pfp.jpg", "avatar.webp"):
                    p = candidate / fname
                    if p.is_file():
                        avatar_path = p
                        break

            # canonical quote tag
            quote_tag = f'{{quote:"{name}"}}'

            # insert image or tag (use rounded image resource)
            if avatar_path:
                size = 18
                radius = max(3, int(size * 0.25))
                raw_pix = QPixmap(str(avatar_path))
                rounded = _rounded_pixmap_from_pixmap(raw_pix, size, size, radius)

                # unique resource URL so different sizes/radii don't collide
                url_str = f"avatar://{name}?w={size}&r={radius}"
                qurl = QUrl(url_str)
                self.text_edit.document().addResource(QTextDocument.ImageResource, qurl, rounded.toImage())

                imgfmt = QTextImageFormat()
                imgfmt.setWidth(float(size))
                imgfmt.setHeight(float(size))
                imgfmt.setName(qurl.toString())
                imgfmt.setProperty(IMAGE_TAG_PROPERTY, quote_tag)
                cursor.insertImage(imgfmt)
            else:
                cursor.insertText(quote_tag)

            # right space
            cursor.insertText(" ")

            idx = end

        # remaining text
        if idx < len(colon_text):
            cursor.insertText(colon_text[idx:])

        cursor.endEditBlock()

    # Insert suggestion as canonical quote tag (immediate conversion)

    # Insert avatar image or {quote:"name"} text, adding spaces appropriately.
    def _insert_quote_tag(self, name: str):
        cursor = self.text_edit.textCursor()
        cursor.beginEditBlock()

        # remove the typed colon prefix
        block_text = cursor.block().text()
        pos_in_block = cursor.positionInBlock()
        last_colon_idx = block_text.rfind(":", 0, pos_in_block)
        if last_colon_idx != -1:
            start = cursor.position() - pos_in_block + last_colon_idx
            end = cursor.position()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()

        # left space if not at block start
        pos_in_block_after = cursor.positionInBlock()
        if pos_in_block_after != 0:
            cursor.insertText(" ")

        # find avatar
        avatar_path: Optional[Path] = None
        people = getattr(self.storage, "people", {}) or {}
        person_entry = people.get(name)

        if isinstance(person_entry, (str, Path)):
            p = Path(person_entry)
            if p.is_file():
                avatar_path = p
        elif isinstance(person_entry, dict):
            for k in ("avatar", "pfp", "image", "avatar_path"):
                val = person_entry.get(k)
                if isinstance(val, (str, Path)):
                    p = Path(val)
                    if p.is_file():
                        avatar_path = p
                        break

        if avatar_path is None:
            candidate = Path(self.root) / name
            for fname in ("avatar.png", "avatar.jpg", "pfp.png", "pfp.jpg", "avatar.webp"):
                p = candidate / fname
                if p.is_file():
                    avatar_path = p
                    break

        quote_tag = f'{{quote:"{name}"}}'

        if avatar_path:
            size = 18
            radius = max(3, int(size * 0.25))
            raw_pix = QPixmap(str(avatar_path))
            rounded = _rounded_pixmap_from_pixmap(raw_pix, size, size, radius)

            url_str = f"avatar://{name}?w={size}&r={radius}"
            qurl = QUrl(url_str)
            self.text_edit.document().addResource(QTextDocument.ImageResource, qurl, rounded.toImage())

            imgfmt = QTextImageFormat()
            imgfmt.setWidth(float(size))
            imgfmt.setHeight(float(size))
            imgfmt.setName(qurl.toString())
            imgfmt.setProperty(IMAGE_TAG_PROPERTY, quote_tag)
            cursor.insertImage(imgfmt)
        else:
            cursor.insertText(quote_tag)

        # right space
        cursor.insertText(" ")
        cursor.endEditBlock()

    # Backend-safe text extraction

    # Return text with images replaced by their IMAGE_TAG_PROPERTY tag.
    def _get_text_with_images_as_colon_tags(self) -> str:
        doc = self.text_edit.document()
        parts = []

        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    if fmt.isImageFormat():
                        imgfmt = fmt.toImageFormat()
                        tag = imgfmt.property(IMAGE_TAG_PROPERTY)
                        parts.append(str(tag) if tag else "")
                    else:
                        parts.append(frag.text())
                it += 1

            if block.next().isValid():
                parts.append("\n")
            block = block.next()

        return "".join(parts)

    # Local safe colon-tag scanning and replacing

    # Find :name: tags not overlapping existing {quote:"..."} tags.
    def _find_colon_tags_local(self, text: str):
        quote_spans = [(m.start(), m.end()) for m in re.finditer(r'\{quote:"[^"]*"\}', text)]

        def overlaps_quote(span_start, span_end):
            for qs, qe in quote_spans:
                if not (span_end <= qs or span_start >= qe):
                    return True
            return False

        names = []
        for m in re.finditer(r':([^:\s][^:]*?):', text):
            s, e = m.span()
            inner = m.group(1)
            whole = m.group(0)
            if overlaps_quote(s, e):
                continue
            if '{quote:"' in whole:
                continue
            names.append(inner)
        return names

    # Replace allowed :name: with {quote:"name"}.
    def _replace_colon_tags_local(self, text: str, to_convert: Set[str]) -> str:
        quote_spans = [(m.start(), m.end()) for m in re.finditer(r'\{quote:"[^"]*"\}', text)]

        def overlaps_quote(span_start, span_end):
            for qs, qe in quote_spans:
                if not (span_end <= qs or span_start >= qe):
                    return True
            return False

        out = []
        last_idx = 0
        for m in re.finditer(r':([^:\s][^:]*?):', text):
            s, e = m.span()
            name = m.group(1)
            whole = m.group(0)
            out.append(text[last_idx:s])
            if overlaps_quote(s, e) or ('{quote:"' in whole) or (name not in to_convert):
                out.append(whole)
            else:
                out.append(f'{{quote:"{name}"}}')
            last_idx = e
        out.append(text[last_idx:])
        return "".join(out)

    # Remove one space either side of {quote:"..."}.
    def _strip_spaces_around_quote_tags(self, text: str) -> str:
        text = re.sub(r' (\{quote:"[^"]*"\})', r'\1', text)
        text = re.sub(r'(\{quote:"[^"]*"\}) ', r'\1', text)
        return text

    # Submit

    def _on_submit(self):
        url = self.url_edit.text().strip()

        if not url:
            QMessageBox.warning(self, "URL required", "Please enter a valid URL.")
            return

        if not is_valid_url(url):
            QMessageBox.warning(self, "Invalid URL", "Invalid URL.")
            return

        seconds = self.ts_edit.to_seconds()
        if seconds is None:
            QMessageBox.warning(self, "Invalid timestamp", "Timestamp must be h:mm:ss")
            return

        timestamp_hms = seconds_to_mask_string(seconds)

        extracted_seconds, _ = find_timestamp_seconds(url)
        if extracted_seconds is None:
            url = ensure_timestamp_in_url(url, seconds)

        # use reconstructed text, not toPlainText()
        raw_text = self._get_text_with_images_as_colon_tags()

        # Use local find/replace
        colon_names = self._find_colon_tags_local(raw_text)
        existing = self._existing_people()
        missing = [n for n in colon_names if n not in existing]

        created = set()
        for name in sorted(missing):
            if QMessageBox.question(self, "Create person?", f"Create '{name}'?") == QMessageBox.Yes:
                (self.root / name).mkdir(parents=True, exist_ok=True)
                created.add(name)

        to_convert = set(n for n in colon_names if n in existing or n in created)

        converted_text = self._replace_colon_tags_local(raw_text, to_convert).strip()

        # strip one space either side of quote tags before validation/saving
        converted_text = self._strip_spaces_around_quote_tags(converted_text)

        if not ensure_first_is_quote_tag(converted_text):
            QMessageBox.warning(self, "Missing speaker", "Quote must start with :name:")
            return

        if not has_real_text_outside_tags(converted_text):
            QMessageBox.warning(self, "Empty quote", "Quote has no text.")
            return

        try:
            if self.quote:
                self.modifier.edit_quote(
                    self.quote.date,
                    self.quote.timestamp,
                    self.quote.url,
                    self.date_edit.date().toString("yyyy-MM-dd"),
                    timestamp_hms,
                    url,
                    converted_text,
                )
            else:
                self.modifier.add_quote(
                    self.date_edit.date().toString("yyyy-MM-dd"),
                    timestamp_hms,
                    url,
                    converted_text,
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save quote:\n{e}")
            return

        self.accept()