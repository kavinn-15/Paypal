import datetime
import uuid
import bcrypt
import jwt
from typing import Optional, Dict, Any
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from backend.app.config import settings

# RFC 9106 recommended Argon2id parameters
_argon2_hasher = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1)


def hash_password(password: str) -> str:
    """Hash password using Argon2id with random salt."""
    return _argon2_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against Argon2id or legacy bcrypt hash."""
    if not hashed_password:
        return False
    # If Argon2 hash
    if hashed_password.startswith("$argon2"):
        try:
            return _argon2_hasher.verify(hashed_password, plain_password)
        except (VerifyMismatchError, VerificationError):
            return False
        except Exception:
            return False
    # Fallback to bcrypt verification for existing hashes
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[datetime.timedelta] = None) -> str:
    to_encode = data.copy()
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    now = datetime.datetime.now(datetime.timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now, "jti": uuid.uuid4().hex})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: int) -> str:
    """Creates a longer-lived refresh token for token rotation."""
    now = datetime.datetime.now(datetime.timezone.utc)
    expire = now + datetime.timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": now,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_refresh_token(token: str) -> Optional[int]:
    """Decodes a refresh token and returns user_id if valid and type=='refresh'."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") == "refresh" and "sub" in payload:
            return int(payload["sub"])
        return None
    except jwt.PyJWTError:
        return None


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") == "refresh":
            return None  # Cannot use refresh token as access token
        if "sub" in payload:
            try:
                payload["sub"] = int(payload["sub"])
            except (ValueError, TypeError):
                pass
        return payload
    except jwt.PyJWTError:
        return None
