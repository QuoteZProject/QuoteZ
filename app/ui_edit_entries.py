from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QMessageBox, QInputDialog,
    QLabel, QTextEdit, QDialog, QMenu, QToolButton
)
from PySide6.QtCore import QSize, Qt, QCoreApplication

from pathlib import Path
import logging
import re

from .ui_selector import PersonGroupSelector, DEFAULT_AVATAR
from .write_manager import QuoteModifier
from .icons import icon
from .file_dialogs import select_file_native

log = logging.getLogger(__name__)


class EditEntriesWidget(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)

        self.storage = storage
        self.modifier = QuoteModifier(self.storage.root)

        try:
            self.storage.load_index()
        except Exception:
            log.exception("self.storage.load_index() failed")
            raise

        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        self.add_person_btn = QPushButton("Add Person")
        self.add_person_btn.setCursor(Qt.PointingHandCursor)
        top_bar.addWidget(self.add_person_btn)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        self.selector = PersonGroupSelector(
            self.storage,
            show_checkboxes=False,
            group_right_widget_builder=self._group_buttons,
            person_right_widget_builder=self._person_buttons
        )

        # avatar click handler
        self.selector.avatar_click_handler = self._toggle_person_pfp
        self._update_selector_avatar_cursors()

        layout.addWidget(self.selector)
        self.add_person_btn.clicked.connect(self.add_person)

    def _confirm(self, title: str, message: str) -> bool:
        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes

    def _group_buttons(self, group):
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        rename_btn = QPushButton()
        # icon
        icon(rename_btn, "edit", 14)
        rename_btn.setFixedSize(QSize(20, 20))
        rename_btn.setCursor(Qt.PointingHandCursor)
        # bind in closure
        rename_btn.clicked.connect(lambda g=group: self.rename_group(g))

        delete_btn = QPushButton()
        icon(delete_btn, "delete", 14)
        delete_btn.setFixedSize(QSize(20, 20))
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda g=group: self.remove_group(g))

        lay.addWidget(rename_btn)
        lay.addWidget(delete_btn)
        return container

    def _person_buttons(self, group, person):
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        if group:
            remove_from_group_btn = QPushButton()
            icon(remove_from_group_btn, "group_remove", 14)
            remove_from_group_btn.setFixedSize(QSize(20, 20))
            remove_from_group_btn.setCursor(Qt.PointingHandCursor)
            # bind closure
            remove_from_group_btn.clicked.connect(lambda g=group, p=person: self.remove_from_group(g, p))
            lay.addWidget(remove_from_group_btn)

        add_to_group_btn = QPushButton()
        icon(add_to_group_btn, "group_add", 14)
        add_to_group_btn.setFixedSize(QSize(20, 20))
        add_to_group_btn.setCursor(Qt.PointingHandCursor)
        add_to_group_btn.clicked.connect(lambda p=person: self.add_to_group(p))
        lay.addWidget(add_to_group_btn)

        edit_btn = QPushButton()
        icon(edit_btn, "edit", 14)
        edit_btn.setFixedSize(QSize(20, 20))
        edit_btn.setCursor(Qt.PointingHandCursor)
        # stable menu & person
        edit_btn.clicked.connect(lambda b=edit_btn, p=person: self._open_person_menu(b, p))
        lay.addWidget(edit_btn)

        delete_btn = QPushButton()
        icon(delete_btn, "delete", 14)
        delete_btn.setFixedSize(QSize(20, 20))
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda p=person: self.remove_person(p))
        lay.addWidget(delete_btn)

        return container

    def _open_person_menu(self, btn, person: str):
        menu = QMenu(self)

        rename_action = menu.addAction("Rename")
        nick_action = menu.addAction("Edit nicknames")

        chosen = menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        if chosen == rename_action:
            self.rename_person(person)
        elif chosen == nick_action:
            self._edit_nicknames(person)

    def add_person(self):
        name, ok = QInputDialog.getText(self, "Add Person", "Name:")
        if ok and name:
            self.modifier.add_person(name)
            self._reload()

    def rename_person(self, person):
        new, ok = QInputDialog.getText(self, "Rename Person", "New name:")
        if ok and new:
            self.modifier.rename_person(person, new)
            self._reload()

    def remove_person(self, person):
        if not self._confirm("Delete Person", f'Delete "{person}"?'):
            return
        self.modifier.remove_person(person)
        self._reload()

    def rename_group(self, group):
        new, ok = QInputDialog.getText(self, "Rename Group", "New name:")
        if ok and new:
            self.modifier.rename_group(group, new)
            self._reload()

    def remove_group(self, group):
        if not self._confirm("Delete Group", f'Delete "{group}"?'):
            return
        self.modifier.remove_group(group)
        self._reload()

    def remove_from_group(self, group, person):
        data = self.modifier._load_groups()
        if group in data and person in data[group]:
            data[group].remove(person)
            self.modifier._save_groups(data)
            self._reload()

    def add_to_group(self, person):
        data = self.modifier._load_groups()
        groups = sorted(list(data.keys()))
        NEW_OPTION = "<New group>"
        items = groups + [NEW_OPTION]

        group, ok = QInputDialog.getItem(self, "Select Group", "Group:", items, 0, False)
        if not ok:
            return

        if group == NEW_OPTION:
            new_name, ok2 = QInputDialog.getText(self, "New Group", "Group name:")
            if ok2 and new_name:
                self.modifier.add_group(new_name, members=[person])
                self._reload()
            return

        if person not in data.get(group, []):
            data.setdefault(group, []).append(person)
            self.modifier._save_groups(data)
            self._reload()

    def _toggle_person_pfp(self, person: str):
        # toggle/set/replace/remove profile picture
        current = None
        try:
            current = self.storage.people.get(person)
        except Exception:
            current = None

        current_path = Path(current) if current else None

        # DEFAULT_AVATAR not custom
        has_custom = False
        try:
            if current_path and current_path.exists():
                has_custom = current_path.name != Path(DEFAULT_AVATAR).name
        except Exception:
            has_custom = False

        if has_custom:
            # prompt options
            msg = QMessageBox(self)
            msg.setWindowTitle("Profile Picture")
            msg.setText(f'"{person}" already has a profile picture. What would you like to do?')
            remove_btn = msg.addButton("Remove", QMessageBox.DestructiveRole)
            replace_btn = msg.addButton("Replace", QMessageBox.AcceptRole)
            cancel_btn = msg.addButton("Cancel", QMessageBox.RejectRole)

            msg.exec()

            clicked = msg.clickedButton()
            if clicked == remove_btn:
                try:
                    self.modifier.remove_person_pfp(person)
                except Exception:
                    log.exception("remove_person_pfp failed")
                self._reload()
                return
            elif clicked == replace_btn:
                file_path = select_file_native(self, "Select Profile Picture", "Images (*.png *.jpg *.jpeg *.webp)")
                if file_path:
                    try:
                        self.modifier.set_person_pfp(person, Path(file_path))
                    except Exception:
                        log.exception("set_person_pfp failed")
                    self._reload()
                return
            else:
                return

        # set new profile picture
        file_path = select_file_native(self, "Select Profile Picture", "Images (*.png *.jpg *.jpeg *.webp)")
        if file_path:
            try:
                self.modifier.set_person_pfp(person, Path(file_path))
            except Exception:
                log.exception("set_person_pfp failed (no custom present)")
            self._reload()

    def _edit_nicknames(self, person: str):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit nicknames — {person}")
        dlg.resize(420, 260)

        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("One nickname per line:"))

        te = QTextEdit()
        te.setPlainText("\n".join(self.modifier.get_nicknames(person)))
        v.addWidget(te, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("Save")
        save_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        v.addLayout(btn_row)

        save_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)

        if dlg.exec() == QDialog.Accepted:
            lines = [l.strip() for l in te.toPlainText().splitlines() if l.strip()]
            self.modifier.set_nicknames(person, lines)
            self._reload()

    def _update_selector_avatar_cursors(self):
        # set avatar cursors
        for btn in self.selector.findChildren(QPushButton):
            btn.setCursor(Qt.PointingHandCursor)

        try:
            groups = set(self.modifier._load_groups().keys())
        except Exception:
            groups = set()
        try:
            people_keys = set(self.storage.people.keys())
        except Exception:
            people_keys = set()

        # strip trailing ' (N)'
        def plain_name_from_label_text(text: str) -> str:
            if not text:
                return ""
            m = re.match(r'^(.*?)(?: \(\d+\))?$', text.strip())
            return m.group(1) if m else text.strip()

        widgets = []
        widgets.extend(self.selector.findChildren(QLabel))
        widgets.extend(self.selector.findChildren(QToolButton))

        for w in widgets:
            # detect pixmap/icon
            has_pix = False
            try:
                if isinstance(w, QLabel):
                    has_pix = bool(w.pixmap())
                elif isinstance(w, QToolButton):
                    has_pix = not w.icon().isNull()
            except Exception:
                has_pix = False

            # explicit properties override
            try:
                if w.property("is_group_icon"):
                    w.setCursor(Qt.ArrowCursor)
                    continue
                if w.property("is_person_avatar"):
                    w.setCursor(Qt.PointingHandCursor)
                    continue
            except Exception:
                pass

            if not has_pix:
                continue

            desired_cursor = Qt.PointingHandCursor

            parent = w.parent()
            if parent:
                for sibling in parent.findChildren(QLabel):
                    if sibling is w:
                        continue
                    text = sibling.text().strip() if hasattr(sibling, "text") else ""
                    if not text:
                        continue
                    plain = plain_name_from_label_text(text)
                    if plain in groups:
                        desired_cursor = Qt.ArrowCursor
                        break
                    if plain in people_keys:
                        desired_cursor = Qt.PointingHandCursor
                        break
                    try:
                        if sibling.property("group_name_plain"):
                            if sibling.property("group_name_plain") == plain:
                                desired_cursor = Qt.ArrowCursor
                                break
                        if sibling.property("person_name_plain"):
                            if sibling.property("person_name_plain") == plain:
                                desired_cursor = Qt.PointingHandCursor
                                break
                    except Exception:
                        pass

            w.setCursor(desired_cursor)

    def _reload(self):
        # reload storage and rebuild selector
        try:
            self.storage.load_index()
        except Exception:
            log.exception("storage.load_index failed during reload")

        self.modifier = QuoteModifier(self.storage.root)

        layout = self.layout()

        # remove previous selector to avoid artifacts
        try:
            if hasattr(self, "selector") and self.selector is not None:
                try:
                    layout.removeWidget(self.selector)
                except Exception:
                    pass
                try:
                    self.selector.setParent(None)
                except Exception:
                    pass
                try:
                    self.selector.deleteLater()
                except Exception:
                    pass
                QCoreApplication.processEvents()
        except Exception:
            log.exception("error while removing old selector")

        # create new selector
        self.selector = PersonGroupSelector(
            self.storage,
            show_checkboxes=False,
            group_right_widget_builder=self._group_buttons,
            person_right_widget_builder=self._person_buttons
        )

        # avatar click handler
        self.selector.avatar_click_handler = self._toggle_person_pfp

        layout.addWidget(self.selector)
        self.selector.show()

        # update cursors
        self._update_selector_avatar_cursors()

        # final repaint
        try:
            self.selector.update()
            self.selector.repaint()
            self.updateGeometry()
        except Exception:
            pass