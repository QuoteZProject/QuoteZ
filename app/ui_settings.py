from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel,
    QFileDialog, QWidget, QTabWidget, QMessageBox
)

from .settings import Settings
from .ui_edit_entries import EditEntriesWidget
from .storage import QuoteStorage
from .file_dialogs import select_folder_native


class SettingsDialog(QDialog):
    # Settings dialog
    def __init__(self, config_path: Path, storage, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(500, 350)

        # load settings
        self.settings = Settings(config_path)
        self.storage = storage

        # main layout
        vlay = QVBoxLayout(self)

        self.tabs = QTabWidget()
        vlay.addWidget(self.tabs)

        # general tab
        self.general_tab = QWidget()
        self.general_layout = QVBoxLayout(self.general_tab)

        self.quotez_label = QLabel("Path to Quotez Folder:")
        self.general_layout.addWidget(self.quotez_label)

        # input + browse button
        h_layout = QHBoxLayout()

        self.quotez_path_edit = QLineEdit(
            str(self.settings.data.get("quotez_location", ""))
        )
        h_layout.addWidget(self.quotez_path_edit)

        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.select_quotez_folder)
        h_layout.addWidget(self.browse_button)

        self.general_layout.addLayout(h_layout)

        self.general_layout.addStretch()

        self.tabs.addTab(self.general_tab, "General")

        # people tab
        self.people_tab = None
        self._create_people_tab()

        # Add buttons for quote management
        quote_management_layout = QVBoxLayout()
        quote_management_layout.addWidget(QLabel("Destructive operations:"))
        
        self.sort_quotes_btn = QPushButton("Remove Quote Order")
        self.sort_quotes_btn.setStyleSheet("color: red;")
        self.sort_quotes_btn.clicked.connect(self.sort_quotes)
        quote_management_layout.addWidget(self.sort_quotes_btn)
        
        self.remove_all_quotes_btn = QPushButton("Remove All Quotes")
        self.remove_all_quotes_btn.setStyleSheet("color: red;")
        self.remove_all_quotes_btn.clicked.connect(self.remove_all_quotes)
        quote_management_layout.addWidget(self.remove_all_quotes_btn)
        
        self.general_layout.addLayout(quote_management_layout)
        self.general_layout.addStretch()

        # dialog buttons
        btns_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")

        btns_layout.addStretch()
        btns_layout.addWidget(self.save_btn)
        btns_layout.addWidget(self.cancel_btn)

        vlay.addLayout(btns_layout)

        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

        self._load_data()

    # people tab builder
    def _create_people_tab(self):
        quotez_path = Path(self.settings.data.get("quotez_location", ""))

        # remove existing tab if present
        if self.people_tab:
            index = self.tabs.indexOf(self.people_tab)
            if index != -1:
                self.tabs.removeTab(index)
            self.people_tab.deleteLater()

        if quotez_path.exists():
            # update storage root and load index
            self.storage.root = quotez_path
            self.storage.load_index()

            # use same storage instance for editor
            self.people_tab = EditEntriesWidget(self.storage, self)
        else:
            self.people_tab = QWidget()
            layout = QVBoxLayout(self.people_tab)
            layout.addWidget(QLabel("Please set a valid Quotez folder first."))
            layout.addStretch()

        self.tabs.addTab(self.people_tab, "People")

    # data handling
    def _load_data(self):
        quotez_path = self.settings.data.get("quotez_location", "")
        self.quotez_path_edit.setText(quotez_path)

    def select_quotez_folder(self):
        folder = select_folder_native(
            self,
            "Select Quotez Folder",
            str(Path(self.settings.data.get("quotez_location", "")))
        )

        if folder:
            self.quotez_path_edit.setText(folder)

    def accept(self):
        # save updated path
        new_path = self.quotez_path_edit.text()
        self.settings.data["quotez_location"] = new_path
        self.settings.save()

        # rebuild people tab if path changed
        self._create_people_tab()

        super().accept()

    def sort_quotes(self):
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm",
            "WARNING: Are you sure you want to remove quote add order? This will sort all quotes by date in the stored data. This action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            quotez_path = Path(self.settings.data.get("quotez_location", ""))
            if quotez_path.exists():
                # Create quote modifier to call sort_quotes
                from .write_manager import QuoteModifier
                modifier = QuoteModifier(quotez_path)
                modifier.sort_quotes()

    def remove_all_quotes(self):
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm",
            "WARNING: Are you sure you want to remove all quotes? This will also remove all person data. This action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            quotez_path = Path(self.settings.data.get("quotez_location", ""))
            if quotez_path.exists():
                # Create quote modifier to call remove_all_quotes
                from .write_manager import QuoteModifier
                modifier = QuoteModifier(quotez_path)
                modifier.remove_all_quotes()