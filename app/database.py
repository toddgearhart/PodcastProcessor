from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import ACTIVE_STATUSES, Base, Job, JobStatus


class Database:
    def __init__(self, settings: Settings):
        connect_args = (
            {"check_same_thread": False}
            if settings.resolved_database_url.startswith("sqlite")
            else {}
        )
        self.engine = create_engine(
            settings.resolved_database_url, connect_args=connect_args
        )
        if settings.resolved_database_url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._configure_sqlite)
        self.session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False, class_=Session
        )

    @staticmethod
    def _configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def recover_interrupted_jobs(self) -> None:
        with self.session_factory.begin() as session:
            session.execute(
                update(Job)
                .where(Job.status.in_([status.value for status in ACTIVE_STATUSES]))
                .values(
                    status=JobStatus.QUEUED.value,
                    error_message="Recovered after an application restart",
                )
            )

    def session(self) -> Generator[Session, None, None]:
        with self.session_factory() as session:
            yield session

