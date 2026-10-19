"""Persistence operations for Scan entities."""

import builtins

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scan import Scan


class ScanRepository:
    """Provide database operations for URL scan records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, scan: Scan) -> Scan:
        """Persist a scan, then refresh it with database-generated values."""
        self.db.add(scan)
        self.db.commit()
        self.db.refresh(scan)
        return scan

    def get_by_id(self, scan_id: int) -> Scan | None:
        """Return the scan with the given primary key, if it exists."""
        return self.db.get(Scan, scan_id)

    def list_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> builtins.list[Scan]:
        """Return a page of scans owned by the specified user."""
        statement = (
            select(Scan)
            .where(Scan.user_id == user_id)
            .order_by(Scan.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def list(self, skip: int = 0, limit: int = 100) -> builtins.list[Scan]:
        """Return a page of all scans, newest first."""
        statement = (
            select(Scan)
            .order_by(Scan.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def delete(self, scan: Scan) -> None:
        """Delete a scan and commit the database transaction."""
        self.db.delete(scan)
        self.db.commit()