"""Authentication endpoints for user registration and login."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.dependencies import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import AuthenticationService


router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """Build the user repository from the request-scoped database session."""
    return UserRepository(db)


def get_authentication_service(
    repository: UserRepository = Depends(get_user_repository),
) -> AuthenticationService:
    """Build the authentication service from its repository dependency."""
    return AuthenticationService(repository)


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user",
    description="Create a user account and return its public profile.",
)
def register_user(
    user_data: UserCreate,
    service: AuthenticationService = Depends(get_authentication_service),
) -> UserRead:
    """Register a user and return the public user representation."""
    try:
        user: User = service.register_user(user_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Authenticate a user",
    description="Validate user credentials and return a bearer access token.",
)
def login_user(
    credentials: LoginRequest,
    service: AuthenticationService = Depends(get_authentication_service),
) -> Token:
    """Authenticate the supplied credentials and return an access token."""
    try:
        return service.authenticate_user(credentials.username, credentials.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Get the current user",
    description="Return the public profile for the authenticated user.",
)
def read_current_user(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Return the authenticated user's public profile."""
    return UserRead.model_validate(current_user)