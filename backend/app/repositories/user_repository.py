import builtins

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Provide persistence operations for User entities."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return self.db.scalars(statement).first()

    def get_by_username(self, username: str) -> User | None:
        statement = select(User).where(User.username == username)
        return self.db.scalars(statement).first()

    def list(self, skip: int = 0, limit: int = 100) -> builtins.list[User]:
        statement = select(User).offset(skip).limit(limit)
        return list(self.db.scalars(statement).all())

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()
