from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel

from core.config import config


router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def verify_password(plain_password: str, hashed_password: Optional[str], fallback_plain: Optional[str]) -> bool:
    if hashed_password:
        try:
            if pwd_context.verify(plain_password, hashed_password):
                return True
        except Exception:
            pass
    if fallback_plain:
        return plain_password == fallback_plain
    return False


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = {
        "sub": subject,
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(seconds=config.security.session_timeout or 3600)
    )
    to_encode.update({"exp": int(expire.timestamp())})
    secret = config.security.jwt_secret or "change-me"
    return jwt.encode(to_encode, secret, algorithm="HS256")


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    username = form_data.username
    password = form_data.password

    expected_username = getattr(config.security, "admin_username", "admin") or "admin"
    if username != expected_username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(
        password,
        getattr(config.security, "admin_password_hash", ""),
        getattr(config.security, "admin_password", ""),
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=username)
    return TokenResponse(access_token=token)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    secret = config.security.jwt_secret or "change-me"
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        sub = payload.get("sub")
        if not sub or sub != (getattr(config.security, "admin_username", "admin") or "admin"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return sub
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

