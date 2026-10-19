import builtins

from app.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    """Provide business operations for User entities."""

    def __init__(self, repository: UserRepository):
        self.repository = repository

    def create_user(self, user: User) -> User:
        if self.repository.get_by_username(user.username) is not None:
            raise ValueError("Username already exists")
        if self.repository.get_by_email(user.email) is not None:
            raise ValueError("Email already exists")
        return self.repository.create(user)

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.repository.get_by_id(user_id)

    def get_user_by_email(self, email: str) -> User | None:
        return self.repository.get_by_email(email)

    def get_user_by_username(self, username: str) -> User | None:
        return self.repository.get_by_username(username)

    def list_users(self, skip: int = 0, limit: int = 100) -> builtins.list[User]:
        return self.repository.list(skip=skip, limit=limit)

    def delete_user(self, user_id: int) -> bool:
        user = self.repository.get_by_id(user_id)
        if user is None:
            return False
        self.repository.delete(user)
        return True
