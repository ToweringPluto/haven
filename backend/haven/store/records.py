"""Saved records: renter profiles, user-added properties and reports.

With ``HAVEN_DATABASE_URL`` set (Tiger Cloud Postgres), records live in one table,
``haven_records``, keyed by ``(kind, id)``, with the pydantic model stored as JSON, so they
survive restarts. Without a database they live in memory for the life of the process (the
app still runs offline; nothing is saved).

``owner_sub`` is the Auth0 subject of the signed-in user who created the record, or ``None``
for records created without signing in.
"""

import logging
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel
from sqlalchemy import JSON, Column, Engine, String, select
from sqlmodel import Field, Session, SQLModel

from haven.config import Settings
from haven.store.db import engine_for

logger = logging.getLogger(__name__)

type Kind = Literal["profile", "property", "report"]


class RecordRow(SQLModel, table=True):
    __tablename__ = "haven_records"

    kind: str = Field(sa_column=Column(String(16), primary_key=True))
    id: str = Field(sa_column=Column(String(128), primary_key=True))
    owner_sub: str | None = Field(default=None, sa_column=Column(String(255), index=True))
    created_at: datetime
    data: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class RecordStore(Protocol):
    persistent: bool

    def put(self, kind: Kind, record: BaseModel, *, owner_sub: str | None = None) -> None:
        """Insert or replace the record (its ``id`` attribute is the key)."""
        ...

    def get[M: BaseModel](self, kind: Kind, record_id: str, model: type[M]) -> M | None: ...

    def list[M: BaseModel](
        self, kind: Kind, model: type[M], *, owner_sub: str | None = None
    ) -> list[M]:
        """Records of ``kind`` owned by ``owner_sub`` (all of them when it's ``None``),
        oldest first."""
        ...


def _record_id(record: BaseModel) -> str:
    record_id = getattr(record, "id", None)
    if not isinstance(record_id, str):
        raise TypeError(f"{type(record).__name__} has no string id")
    return record_id


class MemoryRecordStore:
    """Records in memory (no database configured)."""

    persistent = False

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], tuple[str | None, dict[str, Any]]] = {}

    def put(self, kind: Kind, record: BaseModel, *, owner_sub: str | None = None) -> None:
        key = (kind, _record_id(record))
        if owner_sub is None and key in self._rows:
            owner_sub = self._rows[key][0]  # an update keeps the original owner
        self._rows[key] = (owner_sub, record.model_dump(mode="json"))

    def get[M: BaseModel](self, kind: Kind, record_id: str, model: type[M]) -> M | None:
        row = self._rows.get((kind, record_id))
        return None if row is None else model.model_validate(row[1])

    def list[M: BaseModel](
        self, kind: Kind, model: type[M], *, owner_sub: str | None = None
    ) -> list[M]:
        return [
            model.model_validate(data)
            for (k, _), (owner, data) in self._rows.items()
            if k == kind and (owner_sub is None or owner == owner_sub)
        ]


class SqlRecordStore:
    """Records in a SQL database (Postgres in production, SQLite in tests)."""

    persistent = True

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        SQLModel.metadata.create_all(engine, tables=[RecordRow.__table__])  # type: ignore[attr-defined]

    def put(self, kind: Kind, record: BaseModel, *, owner_sub: str | None = None) -> None:
        record_id = _record_id(record)
        data = record.model_dump(mode="json")
        with Session(self.engine) as session:
            row = session.get(RecordRow, (kind, record_id))
            if row is None:
                row = RecordRow(
                    kind=kind,
                    id=record_id,
                    owner_sub=owner_sub,
                    created_at=datetime.now(UTC),
                    data=data,
                )
            else:
                row.data = data
                if owner_sub is not None:
                    row.owner_sub = owner_sub
            session.add(row)
            session.commit()

    def get[M: BaseModel](self, kind: Kind, record_id: str, model: type[M]) -> M | None:
        with Session(self.engine) as session:
            row = session.get(RecordRow, (kind, record_id))
            return None if row is None else model.model_validate(row.data)

    def list[M: BaseModel](
        self, kind: Kind, model: type[M], *, owner_sub: str | None = None
    ) -> list[M]:
        query = select(RecordRow).where(RecordRow.kind == kind)  # type: ignore[arg-type]
        if owner_sub is not None:
            query = query.where(RecordRow.owner_sub == owner_sub)  # type: ignore[arg-type]
        query = query.order_by(RecordRow.created_at)  # type: ignore[arg-type]
        with Session(self.engine) as session:
            return [model.model_validate(row.data) for row in session.scalars(query)]


def make_record_store(settings: Settings) -> RecordStore:
    """The database store when ``HAVEN_DATABASE_URL`` is set and reachable, else memory.

    An unreachable database is logged as an error, not fatal, so the API still starts; in
    that case nothing is saved across restarts.
    """
    if settings.database_url is None:
        return MemoryRecordStore()
    try:
        return SqlRecordStore(engine_for(settings.database_url.get_secret_value()))
    except Exception as exc:  # noqa: BLE001 - any driver/network error falls back to memory
        logger.error(
            "Couldn't use HAVEN_DATABASE_URL (%s); records will not be saved across restarts.",
            type(exc).__name__,
        )
        return MemoryRecordStore()
