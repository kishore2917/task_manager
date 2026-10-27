"""PySide6 user interface for the Task Manager."""

from __future__ import annotations

import re

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from database import DatabaseError, Task, TaskDatabase


class TaskManagerWindow(QMainWindow):
    """Main application window and task-list interactions."""

    FOCUS_DURATION_SECONDS = 25 * 60

    FILTERS = {
        "All Tasks": "all",
        "Pending": "pending",
        "Completed": "completed",
    }

    THEME_PALETTES = {
        "light": {
            "page_bg": "#f4f4f4",
            "surface": "#ffffff",
            "soft_surface": "#fbfbfb",
            "done_surface": "#f7f7f7",
            "text": "#1b1b1b",
            "secondary": "#666666",
            "muted": "#929292",
            "border": "#e5e5e5",
            "accent": "#171717",
            "accent_text": "#ffffff",
            "accent_hover": "#333333",
            "control_bg": "#eeeeee",
            "control_hover": "#e3e3e3",
            "selected_bg": "#e9e9e9",
            "scroll_handle": "#d0d0d0",
            "selection": "#dddddd",
            "pending_red": "#bd2828",
            "pending_yellow_bg": "#fff2bf",
            "pending_yellow_text": "#886200",
            "pending_card_bg": "#fff9e8",
            "pending_card_border": "#f0e0a9",
            "completed_green_bg": "#e9f6ed",
            "completed_green_border": "#c8e5cf",
            "completed_green_text": "#1f7743",
        },
        "dark": {
            "page_bg": "#111111",
            "surface": "#1b1b1b",
            "soft_surface": "#202020",
            "done_surface": "#181818",
            "text": "#f2f2f2",
            "secondary": "#b8b8b8",
            "muted": "#858585",
            "border": "#333333",
            "accent": "#f2f2f2",
            "accent_text": "#111111",
            "accent_hover": "#d9d9d9",
            "control_bg": "#333333",
            "control_hover": "#414141",
            "selected_bg": "#343434",
            "scroll_handle": "#505050",
            "selection": "#555555",
            "pending_red": "#ff7777",
            "pending_yellow_bg": "#4a3c17",
            "pending_yellow_text": "#ffd76a",
            "pending_card_bg": "#252116",
            "pending_card_border": "#5b4a20",
            "completed_green_bg": "#173622",
            "completed_green_border": "#285b37",
            "completed_green_text": "#75d092",
        },
    }

    def __init__(self, database: TaskDatabase, settings: QSettings | None = None) -> None:
        super().__init__()
        self.database = database
        self.settings = settings or QSettings("Codex", "Task Manager")
        saved_theme = self.settings.value("theme", "light")
        self.theme = saved_theme if saved_theme in self.THEME_PALETTES else "light"
        try:
            self.text_scale = float(self.settings.value("text_scale", 1.0))
        except (TypeError, ValueError):
            self.text_scale = 1.0
        self.text_scale = max(0.8, min(1.4, self.text_scale))
        self.current_filter = "all"
        self.full_view = False
        self._saved_window_geometry = None
        self._was_maximized = False
        self.focus_seconds_remaining = self.FOCUS_DURATION_SECONDS
        self.focus_timer = QTimer(self)
        self.focus_timer.setInterval(1000)
        self.focus_timer.timeout.connect(self._tick_focus_timer)
        self.nav_buttons: dict[str, QPushButton] = {}
        self.stat_values: dict[str, QLabel] = {}

        self.setWindowTitle("Task Manager")
        self.setMinimumSize(720, 620)
        self.resize(960, 780)
        self._build_ui()
        self._set_stylesheet()
        self._install_shortcuts()
        self.refresh()

    def _build_ui(self) -> None:
        page = QWidget()
        page.setObjectName("page")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(38, 28, 38, 30)
        page_layout.setSpacing(22)

        # Title and local-storage note
        header = QHBoxLayout()
        title_group = QVBoxLayout()
        eyebrow = QLabel("YOUR PERSONAL WORKSPACE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Task Manager")
        title.setObjectName("pageTitle")
        subtitle = QLabel("A clear place to keep your next steps moving.")
        subtitle.setObjectName("subtitle")
        title_group.addWidget(eyebrow)
        title_group.addWidget(title)
        title_group.addWidget(subtitle)
        header.addLayout(title_group)
        header.addStretch(1)

        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.clicked.connect(self.toggle_theme)
        self._update_theme_button()
        header.addWidget(self.theme_button, alignment=Qt.AlignmentFlag.AlignTop)

        text_size_controls = QHBoxLayout()
        text_size_controls.setContentsMargins(0, 0, 0, 0)
        text_size_controls.setSpacing(3)
        self.text_size_down = QPushButton("A−")
        self.text_size_down.setObjectName("textSizeButton")
        self.text_size_down.setToolTip("Make text smaller")
        self.text_size_down.setAccessibleName("Make text smaller")
        self.text_size_down.clicked.connect(lambda: self.adjust_text_size(-0.1))
        self.text_size_value = QLabel()
        self.text_size_value.setObjectName("textSizeValue")
        self.text_size_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_text_size_label()
        self.text_size_up = QPushButton("A+")
        self.text_size_up.setObjectName("textSizeButton")
        self.text_size_up.setToolTip("Make text larger")
        self.text_size_up.setAccessibleName("Make text larger")
        self.text_size_up.clicked.connect(lambda: self.adjust_text_size(0.1))
        text_size_controls.addWidget(self.text_size_down)
        text_size_controls.addWidget(self.text_size_value)
        text_size_controls.addWidget(self.text_size_up)
        text_size_widget = QWidget()
        text_size_widget.setLayout(text_size_controls)
        header.addWidget(text_size_widget, alignment=Qt.AlignmentFlag.AlignTop)

        self.full_view_button = QPushButton("Full view")
        self.full_view_button.setObjectName("themeButton")
        self.full_view_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.full_view_button.setToolTip("Expand the task manager to full screen")
        self.full_view_button.clicked.connect(self.toggle_full_view)
        header.addWidget(self.full_view_button, alignment=Qt.AlignmentFlag.AlignTop)

        local_badge = QLabel("●  SAVED ON THIS DEVICE")
        local_badge.setObjectName("localBadge")
        local_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(local_badge, alignment=Qt.AlignmentFlag.AlignTop)
        page_layout.addLayout(header)

        timer_panel = QFrame()
        timer_panel.setObjectName("timerPanel")
        timer_layout = QHBoxLayout(timer_panel)
        timer_layout.setContentsMargins(18, 12, 16, 12)
        timer_layout.setSpacing(16)

        timer_info = QVBoxLayout()
        timer_info.setSpacing(3)
        timer_heading = QLabel("FOCUS TIMER")
        timer_heading.setObjectName("timerHeading")
        self.timer_status = QLabel("Ready when you are")
        self.timer_status.setObjectName("timerStatus")
        timer_info.addWidget(timer_heading)
        timer_info.addWidget(self.timer_status)
        timer_layout.addLayout(timer_info, 1)

        self.timer_display = QLabel()
        self.timer_display.setObjectName("timerDisplay")
        self.timer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_timer_display()
        timer_layout.addWidget(self.timer_display)

        self.timer_toggle_button = QPushButton("Start")
        self.timer_toggle_button.setObjectName("timerStartButton")
        self.timer_toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timer_toggle_button.clicked.connect(self.toggle_focus_timer)
        timer_layout.addWidget(self.timer_toggle_button)

        self.timer_reset_button = QPushButton("Reset")
        self.timer_reset_button.setObjectName("timerResetButton")
        self.timer_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timer_reset_button.clicked.connect(self.reset_focus_timer)
        timer_layout.addWidget(self.timer_reset_button)
        page_layout.addWidget(timer_panel)

        # At-a-glance counts
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        for key, label in (
            ("total", "Total tasks"),
            ("pending", "Pending"),
            ("completed", "Completed"),
            ("study", "Study time"),
        ):
            card, value_label = self._make_stat_card(label, key)
            self.stat_values[key] = value_label
            stats_row.addWidget(card, 1)
        page_layout.addLayout(stats_row)

        # Add-task composer
        composer = QFrame()
        composer.setObjectName("composer")
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(12, 12, 12, 12)
        composer_layout.setSpacing(12)
        self.task_input = QLineEdit()
        self.task_input.setObjectName("taskInput")
        self.task_input.setPlaceholderText("Enter a task...")
        self.task_input.setClearButtonEnabled(True)
        self.task_input.returnPressed.connect(self.add_task)
        self.add_button = QPushButton("＋  Add Task")
        self.add_button.setObjectName("addButton")
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.clicked.connect(self.add_task)
        composer_layout.addWidget(self.task_input, 1)
        composer_layout.addWidget(self.add_button)
        page_layout.addWidget(composer)

        # Filter navigation
        nav = QHBoxLayout()
        nav.setSpacing(8)
        for label, key in self.FILTERS.items():
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setProperty("filterKey", key)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, filter_key=key: self.set_filter(filter_key))
            self.nav_buttons[key] = button
            nav.addWidget(button)
        nav.addStretch(1)
        page_layout.addLayout(nav)

        # List surface
        self.list_panel = QFrame()
        self.list_panel.setObjectName("listPanel")
        self.list_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        panel_layout = QVBoxLayout(self.list_panel)
        panel_layout.setContentsMargins(20, 18, 20, 16)
        panel_layout.setSpacing(14)

        panel_header = QHBoxLayout()
        self.list_title = QLabel("All Tasks")
        self.list_title.setObjectName("listTitle")
        self.list_count = QLabel("0 tasks")
        self.list_count.setObjectName("listCount")
        panel_header.addWidget(self.list_title)
        panel_header.addStretch(1)
        panel_header.addWidget(self.list_count)
        panel_layout.addLayout(panel_header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("taskScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.viewport().setStyleSheet("background: transparent;")
        self.task_container = QWidget()
        self.task_container.setObjectName("taskContainer")
        self.task_list_layout = QVBoxLayout(self.task_container)
        self.task_list_layout.setContentsMargins(0, 2, 4, 4)
        self.task_list_layout.setSpacing(10)
        self.task_list_layout.addStretch(1)
        self.scroll_area.setWidget(self.task_container)
        panel_layout.addWidget(self.scroll_area, 1)
        page_layout.addWidget(self.list_panel, 1)

        footer = QLabel("Tip: press Enter to add a task, or Ctrl + N to start a new one.")
        footer.setObjectName("footer")
        page_layout.addWidget(footer)

        self.setCentralWidget(page)
        self.nav_buttons["all"].setChecked(True)

    def _make_stat_card(self, label: str, key: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("statCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(3)
        name = QLabel(label)
        name.setObjectName(f"statName{key.title()}")
        value = QLabel("0")
        value.setObjectName(f"statValue{key.title()}")
        layout.addWidget(name)
        layout.addWidget(value)
        return card, value

    def _set_stylesheet(self) -> None:
        palette = self.THEME_PALETTES[self.theme]
        stylesheet = """
            QMainWindow, QWidget#page { background: @page_bg@; color: @text@; }
            QLabel#eyebrow { color: @muted@; font-size: 10px; font-weight: 700; letter-spacing: 1.2px; }
            QLabel#pageTitle { color: @text@; font-size: 29px; font-weight: 700; }
            QLabel#subtitle { color: @secondary@; font-size: 13px; }
            QLabel#localBadge { background: @control_bg@; color: @secondary@; border-radius: 13px; padding: 8px 12px; font-size: 9px; font-weight: 700; }
            QFrame#statCard, QFrame#composer, QFrame#listPanel { background: @surface@; border: 1px solid @border@; border-radius: 15px; }
            QFrame#timerPanel { background: @surface@; border: 1px solid @border@; border-radius: 15px; }
            QLabel#timerHeading { color: @muted@; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
            QLabel#timerStatus { color: @secondary@; font-size: 11px; }
            QLabel#timerDisplay { color: @text@; min-width: 100px; font-size: 25px; font-weight: 700; }
            QPushButton#timerStartButton { background: @accent@; color: @accent_text@; border: 0; border-radius: 8px; min-width: 66px; padding: 8px 12px; font-size: 11px; font-weight: 700; }
            QPushButton#timerStartButton:hover { background: @accent_hover@; }
            QPushButton#timerResetButton { background: @control_bg@; color: @text@; border: 0; border-radius: 8px; min-width: 56px; padding: 8px 12px; font-size: 11px; font-weight: 600; }
            QPushButton#timerResetButton:hover { background: @control_hover@; }
            QLabel#statNameTotal, QLabel#statNamePending, QLabel#statNameCompleted, QLabel#statNameStudy { color: @secondary@; font-size: 11px; font-weight: 600; }
            QLabel#statValueTotal, QLabel#statValuePending, QLabel#statValueCompleted, QLabel#statValueStudy { color: @text@; font-size: 24px; font-weight: 700; }
            QLabel#statNamePending, QLabel#statValuePending { color: @pending_yellow_text@; }
            QLabel#statNameCompleted, QLabel#statValueCompleted { color: @completed_green_text@; }
            QLineEdit#taskInput { background: transparent; border: 0; padding: 0 8px; color: @text@; font-size: 14px; min-height: 42px; selection-background-color: @selection@; }
            QLineEdit#taskInput::placeholder { color: @muted@; }
            QPushButton#addButton { background: @accent@; color: @accent_text@; border: 0; border-radius: 10px; padding: 0 19px; min-height: 44px; font-size: 13px; font-weight: 700; }
            QPushButton#addButton:hover { background: @accent_hover@; }
            QPushButton#themeButton { background: @surface@; color: @text@; border: 1px solid @border@; border-radius: 9px; padding: 8px 11px; font-size: 10px; font-weight: 600; }
            QPushButton#themeButton:hover { background: @control_bg@; }
            QPushButton#textSizeButton { background: @surface@; color: @text@; border: 1px solid @border@; border-radius: 7px; min-width: 27px; padding: 6px 5px; font-size: 10px; font-weight: 700; }
            QPushButton#textSizeButton:hover { background: @control_bg@; }
            QLabel#textSizeValue { color: @secondary@; min-width: 34px; text-align: center; font-size: 9px; }
            QPushButton#navButton { background: transparent; color: @secondary@; border: 0; border-radius: 9px; padding: 10px 15px; font-size: 12px; font-weight: 600; }
            QPushButton#navButton:hover { background: @control_bg@; color: @text@; }
            QPushButton#navButton:checked { background: @selected_bg@; color: @text@; }
            QPushButton#navButton[filterKey="pending"]:checked { background: @pending_yellow_bg@; color: @pending_yellow_text@; }
            QPushButton#navButton[filterKey="completed"]:checked { background: @completed_green_bg@; color: @completed_green_text@; }
            QLabel#listTitle { color: @text@; font-size: 15px; font-weight: 700; }
            QLabel#listCount { color: @secondary@; font-size: 11px; }
            QScrollArea#taskScroll { background: transparent; }
            QWidget#taskContainer { background: transparent; }
            QFrame#taskCardPending { background: @pending_card_bg@; border: 1px solid @pending_card_border@; border-radius: 12px; }
            QFrame#taskCardDone { background: @completed_green_bg@; border: 1px solid @completed_green_border@; border-radius: 12px; }
            QLabel#taskMarkPending { color: @pending_red@; font-size: 21px; font-weight: 500; }
            QLabel#taskTitlePending { color: @pending_red@; }
            QLabel#taskMarkDone, QLabel#taskTitleDone { color: @completed_green_text@; }
            QLabel#taskMarkDone { font-size: 19px; font-weight: 700; }
            QLabel#taskTitlePending, QLabel#taskTitleDone { font-size: 13px; }
            QPushButton#statusButtonPending { background: @pending_yellow_bg@; color: @pending_yellow_text@; border: 0; border-radius: 8px; padding: 8px 10px; font-size: 10px; font-weight: 700; }
            QPushButton#statusButtonPending:hover { background: @control_hover@; }
            QPushButton#statusButtonDone { background: @completed_green_bg@; color: @completed_green_text@; border: 1px solid @completed_green_border@; border-radius: 8px; padding: 8px 10px; font-size: 10px; font-weight: 700; }
            QPushButton#statusButtonDone:hover { background: @completed_green_border@; }
            QPushButton#deleteButton { background: transparent; color: @secondary@; border: 1px solid @border@; border-radius: 8px; padding: 7px 10px; font-size: 10px; font-weight: 600; }
            QPushButton#deleteButton:hover { background: @control_hover@; color: @text@; }
            QLabel#emptyTitle { color: @text@; font-size: 14px; font-weight: 700; }
            QLabel#emptyHint { color: @muted@; font-size: 12px; }
            QLabel#footer { color: @muted@; font-size: 10px; }
            QScrollBar:vertical { background: transparent; width: 8px; margin: 2px 0; }
            QScrollBar::handle:vertical { background: @scroll_handle@; min-height: 24px; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QMessageBox { background: @surface@; color: @text@; }
            """
        for color_name, color_value in palette.items():
            stylesheet = stylesheet.replace(f"@{color_name}@", color_value)
        stylesheet = re.sub(
            r"font-size:\s*(\d+(?:\.\d+)?)px",
            lambda match: f"font-size: {float(match.group(1)) * self.text_scale:.1f}px",
            stylesheet,
        )
        self.setStyleSheet(stylesheet)

    def _update_theme_button(self) -> None:
        if hasattr(self, "theme_button"):
            target = "black" if self.theme == "light" else "white"
            self.theme_button.setText(f"Use {target} theme")

    def toggle_theme(self) -> None:
        """Switch between the black and white themes and remember the choice."""
        self.theme = "dark" if self.theme == "light" else "light"
        self.settings.setValue("theme", self.theme)
        self._set_stylesheet()
        self._update_theme_button()

    def _update_text_size_label(self) -> None:
        if hasattr(self, "text_size_value"):
            self.text_size_value.setText(f"{round(self.text_scale * 100)}%")

    def adjust_text_size(self, amount: float) -> None:
        """Scale interface text and save the user's preferred size."""
        self.text_scale = round(max(0.8, min(1.4, self.text_scale + amount)), 2)
        self.settings.setValue("text_scale", self.text_scale)
        self._update_text_size_label()
        self._set_stylesheet()

    def toggle_full_view(self) -> None:
        """Expand the app to full screen or return to its previous window size."""
        if not self.full_view:
            self._saved_window_geometry = self.saveGeometry()
            self._was_maximized = self.isMaximized()
            self.full_view = True
            self.full_view_button.setText("Exit full view")
            self.showFullScreen()
            return

        self.exit_full_view()

    def exit_full_view(self) -> None:
        if not self.full_view:
            return
        self.full_view = False
        self.full_view_button.setText("Full view")
        self.showNormal()
        if self._saved_window_geometry is not None:
            self.restoreGeometry(self._saved_window_geometry)
        if self._was_maximized:
            self.showMaximized()

    def _update_timer_display(self) -> None:
        minutes, seconds = divmod(max(0, self.focus_seconds_remaining), 60)
        if hasattr(self, "timer_display"):
            self.timer_display.setText(f"{minutes:02d}:{seconds:02d}")

    @staticmethod
    def _format_study_time(total_seconds: int) -> str:
        hours, remaining_seconds = divmod(max(0, total_seconds), 3600)
        minutes = remaining_seconds // 60
        return f"{hours}h {minutes:02d}m"

    def toggle_focus_timer(self) -> None:
        """Start or pause the 25-minute focus countdown."""
        if self.focus_timer.isActive():
            self.focus_timer.stop()
            self.timer_toggle_button.setText("Resume")
            self.timer_status.setText("Paused")
            return

        if self.focus_seconds_remaining <= 0:
            self.focus_seconds_remaining = self.FOCUS_DURATION_SECONDS
            self._update_timer_display()
        self.focus_timer.start()
        self.timer_toggle_button.setText("Pause")
        self.timer_status.setText("Focus session in progress")

    def _tick_focus_timer(self) -> None:
        try:
            total_study_seconds = self.database.add_study_seconds(1)
        except (DatabaseError, ValueError) as error:
            self.focus_timer.stop()
            self.timer_toggle_button.setText("Resume")
            self.timer_status.setText("Paused")
            QMessageBox.critical(self, "Could not save study time", str(error))
            return

        self.stat_values["study"].setText(self._format_study_time(total_study_seconds))
        self.focus_seconds_remaining = max(0, self.focus_seconds_remaining - 1)
        self._update_timer_display()
        if self.focus_seconds_remaining == 0:
            self.focus_timer.stop()
            self.timer_toggle_button.setText("Start again")
            self.timer_status.setText("Focus session complete")

    def reset_focus_timer(self) -> None:
        self.focus_timer.stop()
        self.focus_seconds_remaining = self.FOCUS_DURATION_SECONDS
        self._update_timer_display()
        self.timer_toggle_button.setText("Start")
        self.timer_status.setText("Ready when you are")

    def _install_shortcuts(self) -> None:
        new_task = QShortcut(QKeySequence("Ctrl+N"), self)
        new_task.activated.connect(self.focus_task_input)
        exit_full_view = QShortcut(QKeySequence("Escape"), self)
        exit_full_view.activated.connect(self.exit_full_view)

    def focus_task_input(self) -> None:
        self.task_input.setFocus()
        self.task_input.selectAll()

    def add_task(self) -> None:
        title = self.task_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Add a task", "Please enter a task first.")
            self.task_input.setFocus()
            return
        try:
            self.database.add_task(title)
            self.task_input.clear()
            self.refresh()
            self.task_input.setFocus()
        except (DatabaseError, ValueError) as error:
            QMessageBox.critical(self, "Could not add task", str(error))

    def set_filter(self, filter_key: str) -> None:
        self.current_filter = filter_key
        for key, button in self.nav_buttons.items():
            button.setChecked(key == filter_key)
        self.refresh()

    def refresh(self) -> None:
        try:
            counts = self.database.get_task_counts()
            for key, value in counts.items():
                self.stat_values[key].setText(str(value))
            self.stat_values["study"].setText(
                self._format_study_time(self.database.get_total_study_seconds())
            )

            if self.current_filter == "pending":
                tasks = self.database.get_pending_tasks()
                heading = "Pending Tasks"
            elif self.current_filter == "completed":
                tasks = self.database.get_completed_tasks()
                heading = "Completed Tasks"
            else:
                tasks = self.database.get_all_tasks()
                heading = "All Tasks"

            self.list_title.setText(heading)
            self.list_count.setText(f"{len(tasks)} task" + ("s" if len(tasks) != 1 else ""))
            self._clear_task_list()
            if tasks:
                for task in tasks:
                    self.task_list_layout.insertWidget(
                        self.task_list_layout.count() - 1, self._make_task_card(task)
                    )
            else:
                self.task_list_layout.insertWidget(
                    0, self._make_empty_state(self.current_filter)
                )
        except DatabaseError as error:
            QMessageBox.critical(self, "Could not load tasks", str(error))

    def _clear_task_list(self) -> None:
        while self.task_list_layout.count() > 1:
            item = self.task_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _make_task_card(self, task: Task) -> QFrame:
        card = QFrame()
        card.setObjectName("taskCardDone" if task.completed else "taskCardPending")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 11, 12, 11)
        row.setSpacing(12)

        mark = QLabel("✓" if task.completed else "○")
        mark.setObjectName("taskMarkDone" if task.completed else "taskMarkPending")
        mark.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        mark.setFixedWidth(22)

        title = QLabel(task.title)
        title.setObjectName("taskTitleDone" if task.completed else "taskTitlePending")
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if task.completed:
            font = QFont(title.font())
            font.setStrikeOut(True)
            title.setFont(font)

        row.addWidget(mark)
        row.addWidget(title, 1)

        status = QPushButton("Mark pending" if task.completed else "Complete")
        status.setObjectName("statusButtonDone" if task.completed else "statusButtonPending")
        status.setCursor(Qt.CursorShape.PointingHandCursor)
        status.clicked.connect(
            lambda checked=False, task_id=task.id, done=task.completed: self.change_status(
                task_id, not done
            )
        )
        delete = QPushButton("Delete")
        delete.setObjectName("deleteButton")
        delete.setCursor(Qt.CursorShape.PointingHandCursor)
        delete.clicked.connect(
            lambda checked=False, task_id=task.id, task_title=task.title: self.confirm_delete(
                task_id, task_title
            )
        )
        row.addWidget(status)
        row.addWidget(delete)
        return card

    def _make_empty_state(self, filter_key: str) -> QWidget:
        state = QWidget()
        layout = QVBoxLayout(state)
        layout.setContentsMargins(12, 55, 12, 55)
        layout.setSpacing(7)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if filter_key == "pending":
            message, hint = "🎉 No pending tasks!", "You’re all caught up."
        elif filter_key == "completed":
            message, hint = "No completed tasks yet.", "Finished tasks will show up here."
        else:
            message, hint = "No tasks yet.", "Add your first task above."

        title = QLabel(message)
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel(hint)
        subtitle.setObjectName("emptyHint")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return state

    def change_status(self, task_id: int, completed: bool) -> None:
        try:
            self.database.set_completed(task_id, completed)
            self.refresh()
        except (DatabaseError, ValueError) as error:
            QMessageBox.critical(self, "Could not update task", str(error))

    def confirm_delete(self, task_id: int, title: str) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Delete task?")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText("Are you sure you want to delete this task?")
        dialog.setInformativeText(title)
        delete_button = dialog.addButton("Delete", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        if dialog.clickedButton() != delete_button:
            return
        try:
            self.database.delete_task(task_id)
            self.refresh()
        except (DatabaseError, ValueError) as error:
            QMessageBox.critical(self, "Could not delete task", str(error))


def apply_application_font(application: QApplication) -> None:
    """Use a readable system font without depending on bundled font files."""
    application.setFont(QFont("Segoe UI", 10))
