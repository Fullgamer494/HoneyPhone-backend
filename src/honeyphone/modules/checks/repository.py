from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from honeyphone.modules.checks.models import CheckSignal, DataSource, Installation, NetworkCheck


class CheckRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def touch_installation(self, installation_id: UUID, app_version: str) -> None:
        existing = self.session.get(Installation, installation_id)
        if existing is not None and not existing.active:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail={"code": "DEVICE_REVOKED", "message": "El dispositivo está revocado."})
        stmt = insert(Installation).values(installation_id=installation_id, app_version=app_version)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Installation.installation_id],
            set_={"app_version": app_version, "last_seen_at": func.now()},
        )
        self.session.execute(stmt)

    def get(self, check_id: UUID) -> NetworkCheck | None:
        return self.session.scalar(
            select(NetworkCheck).options(selectinload(NetworkCheck.signals)).where(NetworkCheck.check_id == check_id)
        )

    def add(self, check: NetworkCheck, signals: list[CheckSignal]) -> None:
        self.session.add(check)
        self.session.add_all(signals)
        self.session.flush()

    def list(self, installation_id: UUID | None, source: DataSource | None, limit: int, cursor: tuple[datetime, UUID] | None) -> list[NetworkCheck]:
        stmt = select(NetworkCheck).options(selectinload(NetworkCheck.signals))
        if installation_id is not None:
            stmt = stmt.where(NetworkCheck.installation_id == installation_id)
        if source is not None:
            stmt = stmt.where(NetworkCheck.source == source)
        if cursor is not None:
            ts, check_id = cursor
            stmt = stmt.where(or_(NetworkCheck.started_at < ts, and_(NetworkCheck.started_at == ts, NetworkCheck.check_id < check_id)))
        stmt = stmt.order_by(desc(NetworkCheck.started_at), desc(NetworkCheck.check_id)).limit(limit + 1)
        return list(self.session.scalars(stmt).unique().all())

    def delete(self, check_id: UUID) -> bool:
        check = self.session.get(NetworkCheck, check_id)
        if check is None:
            return False
        self.session.delete(check)
        self.session.flush()
        return True
