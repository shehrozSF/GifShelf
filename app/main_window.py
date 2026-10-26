from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QActionGroup, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app import db, storage
from app.add_dialog import AddEditDialog
from app.card_widget import CardWidget
from app.settings_dialog import SettingsDialog
from app.theme import build_stylesheet

SEARCH_DEBOUNCE_MS = 200


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(storage.APP_NAME)
        self.resize(900, 600)
        self.settings = storage.settings()

        self._build_menu()
        self._build_central()

        self.apply_theme()
        self.refresh_tag_list()
        self.refresh_entries()

    # ---------- UI construction ----------

    def _build_menu(self) -> None:
        settings_menu = self.menuBar().addMenu("Settings")
        database_action = settings_menu.addAction("Database")
        database_action.triggered.connect(self.open_settings)

        view_menu = self.menuBar().addMenu("View")
        theme_menu = view_menu.addMenu("Theme")
        theme_group = QActionGroup(self)
        for mode, label in (("light", "Light"), ("dark", "Dark"), ("system", "System")):
            action = theme_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.current_theme() == mode)
            action.triggered.connect(lambda _checked, m=mode: self.set_theme(m))
            theme_group.addAction(action)

        self.setStatusBar(QStatusBar())

    def _build_central(self) -> None:
        splitter = QSplitter()

        # Left: tag filter panel
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Filter by tags"))
        self.tag_filter_list = QListWidget()
        self.tag_filter_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.tag_filter_list.itemSelectionChanged.connect(self.refresh_entries)
        left_layout.addWidget(self.tag_filter_list)
        clear_btn = QPushButton("Clear filters")
        clear_btn.clicked.connect(self.tag_filter_list.clearSelection)
        left_layout.addWidget(clear_btn)
        left.setMaximumWidth(220)
        splitter.addWidget(left)

        # Right: search + list
        right = QWidget()
        right_layout = QVBoxLayout(right)

        top_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search title, URL or tags...")
        # Rebuilding every card (and its QMovie) per keystroke is wasteful.
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self.refresh_entries)
        self.search_edit.textChanged.connect(lambda _text: self._search_timer.start())
        top_row.addWidget(self.search_edit)
        add_btn = QPushButton("Add GIF")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self.open_add_dialog)
        top_row.addWidget(add_btn)
        right_layout.addLayout(top_row)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.addStretch()
        self.scroll_area.setWidget(self.list_container)
        right_layout.addWidget(self.scroll_area)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    # ---------- data refresh ----------

    def refresh_tag_list(self) -> None:
        selected = {item.text() for item in self.tag_filter_list.selectedItems()}
        self.tag_filter_list.blockSignals(True)
        self.tag_filter_list.clear()
        for name in db.get_all_tags():
            item = QListWidgetItem(name)
            self.tag_filter_list.addItem(item)
            if name in selected:
                item.setSelected(True)
        self.tag_filter_list.blockSignals(False)

    def refresh_entries(self) -> None:
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        selected_tags = [item.text() for item in self.tag_filter_list.selectedItems()]
        text = self.search_edit.text()
        entries = db.search_entries(selected_tags, text)

        if not entries:
            empty_label = QLabel("No GIFs found.")
            empty_label.setObjectName("muted")
            self.list_layout.insertWidget(0, empty_label)
            return

        for entry in entries:
            card = CardWidget(entry)
            card.copy_requested.connect(self.copy_link)
            card.edit_requested.connect(self.edit_entry)
            card.delete_requested.connect(self.delete_entry)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)

        # Horizontal scrolling is off, so keep the window from shrinking below
        # a card's width (which would clip its buttons).
        scrollbar_w = self.scroll_area.verticalScrollBar().sizeHint().width()
        self.scroll_area.setMinimumWidth(
            self.list_container.minimumSizeHint().width() + scrollbar_w + 2 * self.scroll_area.frameWidth()
        )

    # ---------- actions ----------

    def open_add_dialog(self) -> None:
        self._run_dialog(AddEditDialog(db.get_all_tags(), parent=self))

    def edit_entry(self, entry_id: int) -> None:
        entry = db.get_entry(entry_id)
        if not entry:
            return
        self._run_dialog(AddEditDialog(db.get_all_tags(), entry=entry, parent=self))

    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.library_changed.connect(self._on_library_changed)
        dialog.exec()
        dialog.deleteLater()

    def _on_library_changed(self) -> None:
        self.refresh_tag_list()
        self.refresh_entries()
        self.statusBar().showMessage(f"Library: {storage.app_dir()}", 4000)

    def _run_dialog(self, dialog: AddEditDialog) -> None:
        accepted = dialog.exec()
        dialog.deleteLater()
        if accepted:
            self.refresh_tag_list()
            self.refresh_entries()

    def delete_entry(self, entry_id: int) -> None:
        confirm = QMessageBox.question(
            self, "Delete GIF", "Remove this entry? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            entry = db.get_entry(entry_id)
            db.delete_entry(entry_id)
            if entry:
                storage.remove_thumb(entry.thumb_path)
            self.refresh_tag_list()
            self.refresh_entries()

    def copy_link(self, entry_id: int) -> None:
        entry = db.get_entry(entry_id)
        if not entry:
            return
        QGuiApplication.clipboard().setText(entry.url)
        self.statusBar().showMessage("Copied to clipboard", 2000)

    # ---------- theme ----------

    def current_theme(self) -> str:
        return self.settings.value("theme", "system")

    def set_theme(self, mode: str) -> None:
        self.settings.setValue("theme", mode)
        self.apply_theme()

    def apply_theme(self) -> None:
        app = QGuiApplication.instance()
        app.setStyleSheet(build_stylesheet(self.current_theme()))
