"""Start the Task Manager desktop application."""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from database import DatabaseError, TaskDatabase
from ui import TaskManagerWindow, apply_application_font


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("Task Manager")
    apply_application_font(application)

    try:
        database = TaskDatabase()
    except DatabaseError as error:
        QMessageBox.critical(None, "Task Manager", str(error))
        return 1

    window = TaskManagerWindow(database)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
