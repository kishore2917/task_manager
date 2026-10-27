# Task Manager

A small offline desktop app for keeping track of personal and study tasks. Tasks are saved to a local SQLite database and remain available when the app is closed and reopened.

## Features

- Add tasks with the button or Enter
- View all, pending, or completed tasks
- Pending task text is red, Pending indicators are yellow, and completed tasks are green
- Mark tasks complete and restore them to pending
- Delete tasks after a confirmation prompt
- Live total, pending, and completed counts
- Switch between black and white themes; the choice is remembered
- Use Full view to expand the task list to full screen; Escape restores the window
- Adjust interface text from 80% to 140% with A−/A+; the preference is remembered
- Use the 25-minute focus timer with Start, Pause/Resume, and Reset controls
- See total study time in hours and minutes; it increases only while the focus timer runs and is saved in SQLite
- Local SQLite storage; no internet connection is needed
- Ctrl + N focuses the task entry field

## Technologies

- Python 3.10 or newer
- PySide6 for the desktop interface
- SQLite through Python's built-in `sqlite3` module
- Qt settings for the saved theme preference

## Installation

Open a terminal in this folder and install the one required package:

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

The app creates `tasks.db` beside `main.py` the first time it runs. Keep that file to preserve your tasks, or copy it as a backup.

## Project structure

```text
task_manager/
├── main.py        # Application entry point
├── database.py    # SQLite setup and task operations
├── ui.py          # PySide6 window and interactions
├── tasks.db       # Created automatically on first run
├── requirements.txt
└── README.md
```

## Future improvements

The code is organized so that features such as task priorities, due dates, categories, search, editing, notifications, recurring tasks, exports, and backup tools can be added later.
