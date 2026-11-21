from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from honeyphone.modules.checks.models import CheckSignal, DataSource, Installation, NetworkCheck


class CheckRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def touch_installation(self, installation_id: UUID, app_version: str, user_id: UUID) -> None:
        existing = self.session.get(Installation, installation_id)
        if existing is not None and not existing.active:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail={"code": "DEVICE_REVOKED", "message": "El dispositivo está revocado."})
        if existing is not None and existing.owner_user_id not in (None, user_id):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail={"code": "DEVICE_OWNED_BY_OTHER_ACCOUNT", "message": "Esta instalación está asociada a otra cuenta."})
        from sqlalchemy import or_
        stmt = insert(Installation).values(installation_id=installation_id, app_version=app_version, owner_user_id=user_id)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Installation.installation_id],
            set_={"app_version": app_version, "last_seen_at": func.now(), "owner_user_id": user_id},
            where=or_(Installation.owner_user_id.is_(None), Installation.owner_user_id == user_id),
        )
        self.session.execute(stmt)
        owner = self.session.get(Installation, installation_id)
        if owner is None or owner.owner_user_id != user_id:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail={"code": "DEVICE_OWNED_BY_OTHER_ACCOUNT", "message": "Esta instalación está asociada a otra cuenta."})

    def get(self, check_id: UUID, user_id: UUID | None = None) -> NetworkCheck | None:
        stmt = select(NetworkCheck).options(selectinload(NetworkCheck.signals)).where(NetworkCheck.check_id == check_id)
        if user_id is not None:
            stmt = stmt.join(Installation).where(Installation.owner_user_id == user_id)
        return self.session.scalar(
            stmt
        )

    def add(self, check: NetworkCheck, signals: list[CheckSignal]) -> None:
        self.session.add(check)
        self.session.add_all(signals)
        self.session.flush()

    def list(self, user_id: UUID, installation_id: UUID | None, source: DataSource | None, limit: int, cursor: tuple[datetime, UUID] | None) -> list[NetworkCheck]:
        stmt = select(NetworkCheck).options(selectinload(NetworkCheck.signals))
        stmt = stmt.join(Installation).where(Installation.owner_user_id == user_id)
        if installation_id is not None:
            stmt = stmt.where(NetworkCheck.installation_id == installation_id)
        if source is not None:
            stmt = stmt.where(NetworkCheck.source == source)
        if cursor is not None:
            ts, check_id = cursor
            stmt = stmt.where(or_(NetworkCheck.started_at < ts, and_(NetworkCheck.started_at == ts, NetworkCheck.check_id < check_id)))
        stmt = stmt.order_by(desc(NetworkCheck.started_at), desc(NetworkCheck.check_id)).limit(limit + 1)
        return list(self.session.scalars(stmt).unique().all())

    def delete(self, check_id: UUID, user_id: UUID) -> bool:
        check = self.get(check_id, user_id)
        if check is None:
            return False
        self.session.delete(check)
        self.session.flush()
        return True
