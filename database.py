"""SQLite storage for the Task Manager application."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


class DatabaseError(RuntimeError):
    """A friendly, application-level database error."""


@dataclass(frozen=True)
class Task:
    """One task stored in the local database."""

    id: int
    title: str
    completed: bool
    created_at: str


class TaskDatabase:
    """Small SQLite data layer. The database is created beside this file."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = (
            Path(database_path)
            if database_path is not None
            else Path(__file__).resolve().with_name("tasks.db")
        )
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise DatabaseError("Could not prepare the local task database folder.") from error
        self.initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> Task:
        return Task(
            id=int(row["id"]),
            title=str(row["title"]),
            completed=bool(row["completed"]),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _validate_id(task_id: int) -> None:
        if not isinstance(task_id, int) or task_id <= 0:
            raise ValueError("Task ID must be a positive integer.")

    def initialize(self) -> None:
        """Create the tasks table if it does not already exist."""
        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        completed INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS study_time (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        total_seconds INTEGER NOT NULL DEFAULT 0 CHECK (total_seconds >= 0)
                    )
                    """
                )
                connection.execute(
                    "INSERT OR IGNORE INTO study_time (id, total_seconds) VALUES (1, 0)"
                )
        except sqlite3.Error as error:
            raise DatabaseError("Could not open the local task database.") from error

    def get_total_study_seconds(self) -> int:
        """Return the total time recorded by the focus timer."""
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT total_seconds FROM study_time WHERE id = 1"
                ).fetchone()
            if row is None:
                raise DatabaseError("The saved study-time record could not be found.")
            return int(row["total_seconds"])
        except sqlite3.Error as error:
            raise DatabaseError("Could not load your study time.") from error

    def add_study_seconds(self, seconds: int) -> int:
        """Add focus-timer seconds and return the updated total."""
        if not isinstance(seconds, int) or seconds < 0:
            raise ValueError("Study time must be a non-negative number of seconds.")
        try:
            with self._connection() as connection:
                connection.execute(
                    "UPDATE study_time SET total_seconds = total_seconds + ? WHERE id = 1",
                    (seconds,),
                )
                row = connection.execute(
                    "SELECT total_seconds FROM study_time WHERE id = 1"
                ).fetchone()
            if row is None:
                raise DatabaseError("The saved study-time record could not be found.")
            return int(row["total_seconds"])
        except sqlite3.Error as error:
            raise DatabaseError("Could not save your study time.") from error

    def add_task(self, title: str) -> int:
        """Save a new pending task and return its ID."""
        cleaned_title = title.strip()
        if not cleaned_title:
            raise ValueError("Please enter a task before adding it.")
        try:
            with self._connection() as connection:
                cursor = connection.execute(
                    "INSERT INTO tasks (title) VALUES (?)", (cleaned_title,)
                )
                return int(cursor.lastrowid)
        except sqlite3.Error as error:
            raise DatabaseError("Could not save the task. Please try again.") from error

    def get_all_tasks(self) -> list[Task]:
        """Return all tasks, newest first."""
        return self._get_tasks("SELECT * FROM tasks ORDER BY created_at DESC, id DESC")

    def get_pending_tasks(self) -> list[Task]:
        """Return tasks that are not completed."""
        return self._get_tasks(
            "SELECT * FROM tasks WHERE completed = 0 ORDER BY created_at DESC, id DESC"
        )

    def get_completed_tasks(self) -> list[Task]:
        """Return completed tasks."""
        return self._get_tasks(
            "SELECT * FROM tasks WHERE completed = 1 ORDER BY created_at DESC, id DESC"
        )

    def _get_tasks(self, query: str) -> list[Task]:
        try:
            with self._connection() as connection:
                rows = connection.execute(query).fetchall()
            return [self._task_from_row(row) for row in rows]
        except sqlite3.Error as error:
            raise DatabaseError("Could not load your tasks. Please try again.") from error

    def get_task_counts(self) -> dict[str, int]:
        """Return total, pending, and completed task counts."""
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    SELECT COUNT(*) AS total,
                           COALESCE(SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END), 0) AS pending,
                           COALESCE(SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END), 0) AS completed
                    FROM tasks
                    """
                ).fetchone()
            return {key: int(row[key]) for key in ("total", "pending", "completed")}
        except sqlite3.Error as error:
            raise DatabaseError("Could not update the task counts.") from error

    def set_completed(self, task_id: int, completed: bool) -> None:
        """Set a task's status to completed or pending."""
        self._validate_id(task_id)
        try:
            with self._connection() as connection:
                cursor = connection.execute(
                    "UPDATE tasks SET completed = ? WHERE id = ?",
                    (1 if completed else 0, task_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError("That task could not be found.")
        except sqlite3.Error as error:
            raise DatabaseError("Could not update the task. Please try again.") from error

    def delete_task(self, task_id: int) -> None:
        """Permanently delete a task."""
        self._validate_id(task_id)
        try:
            with self._connection() as connection:
                cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                if cursor.rowcount == 0:
                    raise ValueError("That task could not be found.")
        except sqlite3.Error as error:
            raise DatabaseError("Could not delete the task. Please try again.") from error
