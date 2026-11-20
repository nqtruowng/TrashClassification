"""JWT cookie authentication and PostgreSQL user storage."""

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import DateTime, String, create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://greenlens:greenlens@localhost:5432/greenlens"
)
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "greenlens"
JWT_ACCESS_TOKEN_MINUTES = int(os.environ.get("JWT_ACCESS_TOKEN_MINUTES", "720"))
AUTH_COOKIE_SECURE = os.environ.get("AUTH_COOKIE_SECURE", "false").lower() == "true"
AUTH_COOKIE_NAME = "greenlens_access"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
password_hash = PasswordHash.recommended()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


def get_session():
    with SessionLocal() as session:
        yield session


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user.id,
            "email": user.email,
            "iss": JWT_ISSUER,
            "iat": now,
            "exp": now + timedelta(minutes=JWT_ACCESS_TOKEN_MINUTES),
            "jti": str(uuid4()),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def get_current_user(
    access_cookie: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
    authorization: Annotated[str | None, Header()] = None,
    session: Session = Depends(get_session),
) -> User:
    token = access_cookie
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vui lòng đăng nhập.")

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER)
        user_id = payload.get("sub")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.") from None

    user = session.get(User, user_id) if isinstance(user_id, str) else None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không còn tồn tại.")
    return user


def register_user(session: Session, credentials: Credentials) -> User:
    user = User(email=str(credentials.email), password_hash=password_hash.hash(credentials.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email này đã được đăng ký.") from None
    session.refresh(user)
    return user


def authenticate_user(session: Session, credentials: Credentials) -> User:
    user = session.scalar(select(User).where(User.email == str(credentials.email)))
    if not user or not password_hash.verify(credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không chính xác.")
    return user


def public_user(user: User) -> dict[str, str]:
    return {"id": user.id, "email": user.email}
