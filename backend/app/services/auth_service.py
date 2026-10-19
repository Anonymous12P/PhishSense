"""Business operations for user registration and authentication."""

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import Token
from app.schemas.user import UserCreate


class AuthenticationService:
    """Register users and authenticate credentials through a repository."""

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def register_user(self, user_data: UserCreate) -> User:
        """Validate uniqueness, hash the password, and persist a new user."""
        if self.repository.get_by_username(user_data.username) is not None:
            raise ValueError("Username already exists")
        if self.repository.get_by_email(str(user_data.email)) is not None:
            raise ValueError("Email already exists")

        user = User(
            username=user_data.username,
            email=str(user_data.email),
            full_name=user_data.full_name,
            password_hash=hash_password(user_data.password),
        )
        return self.repository.create(user)

    def authenticate_user(self, username: str, password: str) -> Token:
        """Verify a user's credentials and return a bearer access token."""
        user = self.repository.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise ValueError("Invalid username or password")

        access_token = create_access_token({"sub": user.username})
        return Token(access_token=access_token, token_type="bearer")

    def get_current_user(self, username: str) -> User | None:
        """Return the user matching a username, without decoding a token."""
        return self.repository.get_by_username(username)