from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QMessageBox, QInputDialog,
    QLabel, QTextEdit, QDialog, QMenu, QToolButton
)
from PySide6.QtCore import QSize, Qt

from pathlib import Path
import logging
import re

from .ui_selector import PersonGroupSelector, DEFAULT_AVATAR
from .write_manager import QuoteModifier
from .storage import QuoteStorage
from .icons import icon
from .file_dialogs import select_file_native

log = logging.getLogger(__name__)


class EditEntriesWidget(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)

        self.storage = storage
        self.modifier = QuoteModifier(self.storage.root)
        self.data_storage = QuoteStorage()

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
            show_global_tags=False,
            group_right_widget_builder=self._group_buttons,
            person_right_widget_builder=self._person_buttons,
            tag_right_widget_builder=self._tag_buttons
        )

        # avatar click handler (toggle set/replace/remove)
        self.selector.avatar_click_handler = self._toggle_person_avatar
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
        # use new icon API
        icon(rename_btn, "edit", 14)
        rename_btn.setFixedSize(QSize(20, 20))
        rename_btn.setCursor(Qt.PointingHandCursor)
        rename_btn.clicked.connect(lambda: self.rename_group(group))

        delete_btn = QPushButton()
        icon(delete_btn, "delete", 14)
        delete_btn.setFixedSize(QSize(20, 20))
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self.remove_group(group))

        lay.addWidget(rename_btn)
        lay.addWidget(delete_btn)
        return container

    def _person_buttons(self, group, person):
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        #Goupe remove
        if group:
            remove_from_group_btn = QPushButton()
            icon(remove_from_group_btn, "group_remove", 14)
            remove_from_group_btn.setFixedSize(QSize(20, 20))
            remove_from_group_btn.setCursor(Qt.PointingHandCursor)
            remove_from_group_btn.clicked.connect(lambda: self.remove_from_group(group, person))
            lay.addWidget(remove_from_group_btn)

        #Group add
        add_to_group_btn = QPushButton()
        icon(add_to_group_btn, "group_add", 14)
        add_to_group_btn.setFixedSize(QSize(20, 20))
        add_to_group_btn.setCursor(Qt.PointingHandCursor)
        add_to_group_btn.clicked.connect(lambda: self.add_to_group(person))
        lay.addWidget(add_to_group_btn)

        #Edit
        edit_btn = QPushButton()
        icon(edit_btn, "edit", 14)
        edit_btn.setFixedSize(QSize(20, 20))
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.clicked.connect(lambda: self._open_person_menu(edit_btn, person))
        lay.addWidget(edit_btn)

        #Tag
        tags_btn = QPushButton()
        icon(tags_btn, "tag", 14)
        tags_btn.setFixedSize(QSize(20, 20))
        tags_btn.setCursor(Qt.PointingHandCursor)
        tags_btn.clicked.connect(lambda: self._edit_tags(person))
        lay.addWidget(tags_btn)

        #Don't copy
        is_dont_copy = self.data_storage.get_dont_copy(person)
        dont_copy_btn = QPushButton()
        
        icon_name = "copy_disabled" if is_dont_copy else "copy_enabled"
        icon(dont_copy_btn, icon_name, 14)
        
        dont_copy_btn.setFixedSize(QSize(20, 20))
        dont_copy_btn.setCursor(Qt.PointingHandCursor)
        
        dont_copy_btn.setCheckable(True)
        dont_copy_btn.setChecked(is_dont_copy)
        
        dont_copy_btn.clicked.connect(lambda: self._toggle_dont_copy(person))
        lay.addWidget(dont_copy_btn)

        #Delete
        delete_btn = QPushButton()
        icon(delete_btn, "delete", 14)
        delete_btn.setFixedSize(QSize(20, 20))
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self.remove_person(person))
        lay.addWidget(delete_btn)

        return container

    def _toggle_dont_copy(self, person: str):
        # Get current state
        current_state = self.data_storage.get_dont_copy(person)
        # Toggle the state
        self.modifier.set_dont_copy(person, not current_state)
        # Reload UI to reflect the change
        self._reload()

    def _tag_buttons(self, tag):
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # Edit Button
        edit_btn = QPushButton()
        icon(edit_btn, "edit", 14)
        edit_btn.setFixedSize(QSize(20, 20))
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.clicked.connect(lambda: self.rename_tag(tag))

        # Delete Button
        delete_btn = QPushButton()
        icon(delete_btn, "delete", 14)
        delete_btn.setFixedSize(QSize(20, 20))
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self.remove_tag(tag))

        lay.addWidget(edit_btn)
        lay.addWidget(delete_btn)
        return container

    def _open_person_menu(self, btn, person: str):
        menu = QMenu(self)

        rename_action = menu.addAction("Rename")
        nick_action = menu.addAction("Edit nicknames")
        dont_copy_action = menu.addAction("Don't Copy")

        # Set the check state of the "Don't Copy" action based on current setting
        dont_copy_action.setCheckable(True)
        dont_copy_action.setChecked(self.data_storage.get_dont_copy(person))

        chosen = menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        if chosen == rename_action:
            self.rename_person(person)
        elif chosen == nick_action:
            self._edit_nicknames(person)
        elif chosen == dont_copy_action:
            self._toggle_dont_copy(person)

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

    def rename_tag(self, tag):
        new_name, ok = QInputDialog.getText(self, "Rename Tag", "New name:", text=tag)
        if ok and new_name and new_name != tag:
            self.modifier.rename_tag(tag, new_name)
            self._reload()

    def remove_tag(self, tag):
        if not self._confirm("Delete Tag", f'Delete tag "{tag}"?'):
            return
        self.modifier.remove_tag(tag)
        self._reload()

    def _toggle_person_avatar(self, person: str):
        # toggle/set/replace/remove profile picture for person
        current = None
        try:
            current = self.storage.people.get(person)
        except Exception:
            current = None

        current_path = Path(current) if current else None

        # treat DEFAULT_AVATAR as not custom
        has_custom = False
        try:
            if current_path and current_path.exists():
                has_custom = current_path.name != Path(DEFAULT_AVATAR).name
        except Exception:
            has_custom = False

        if has_custom:
            # prompt remove/replace/cancel
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
                    self.modifier.remove_person_avatar(person)
                except Exception:
                    log.exception("remove_person_avatar failed")
                self._reload()
                return
            elif clicked == replace_btn:
                file_path = select_file_native(self, "Select Profile Picture", "Images (*.png *.jpg *.jpeg *.webp)")
                if file_path:
                    try:
                        self.modifier.set_person_avatar(person, Path(file_path))
                    except Exception:
                        log.exception("set_person_avatar failed")
                    self._reload()
                return
            else:
                return

        # set new profile picture
        file_path = select_file_native(self, "Select Profile Picture", "Images (*.png *.jpg *.jpeg *.webp)")
        if file_path:
            try:
                self.modifier.set_person_avatar(person, Path(file_path))
            except Exception:
                log.exception("set_person_avatar failed (no custom present)")
            self._reload()

    def _edit_nicknames(self, person: str):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit nicknames — {person}")
        dlg.resize(420, 260)

        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Comma-separated list of nicknames:"))
        te = QTextEdit()
        te.setPlainText(", ".join(self.data_storage.get_nicknames(person)))
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
            lines = [l.strip() for l in te.toPlainText().split(",") if l.strip()]
            self.modifier.set_nicknames(person, lines)
            self._reload()

    def _edit_tags(self, person: str):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit tags — {person}")
        dlg.resize(420, 260)

        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Comma-separated list of tags:"))
        te = QTextEdit()
        te.setPlainText(", ".join(self.data_storage.get_tags(person)))
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
            lines = [l.strip() for l in te.toPlainText().split(",") if l.strip()]
            self.modifier.set_tags(person, lines)
            self._reload()

    def _update_selector_avatar_cursors(self):
        # set cursors and detect group vs person avatars
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

        # strip trailing " (N)" from labels
        def plain_name_from_label_text(text: str) -> str:
            if not text:
                return ""
            m = re.match(r'^(.*?)(?: \(\d+\))?$', text.strip())
            return m.group(1) if m else text.strip()

        widgets = []
        widgets.extend(self.selector.findChildren(QLabel))
        widgets.extend(self.selector.findChildren(QToolButton))

        for w in widgets:
            # detect if widget has pixmap/icon
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

            # default to person avatar
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
        self.storage.load_index()
        self.modifier = QuoteModifier(self.storage.root)
        
        layout = self.layout()
        layout.removeWidget(self.selector)
        self.selector.deleteLater()
        
        # Re-instantiate with the SAME settings as __init__
        self.selector = PersonGroupSelector(
            self.storage,
            show_checkboxes=False,
            show_global_tags=False, 
            group_right_widget_builder=self._group_buttons,
            person_right_widget_builder=self._person_buttons,
            tag_right_widget_builder=self._tag_buttons 
        )
        
        self.selector.avatar_click_handler = self._toggle_person_avatar
        self._update_selector_avatar_cursors()
        layout.addWidget(self.selector)