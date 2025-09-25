"""Authentication utilities for user management"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import secrets
import jwt
from datetime import datetime, timedelta
from functools import wraps
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from decision_data.backend.config.config import backend_config

ph = PasswordHasher()
security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash password for database storage using Argon2"""
    return ph.hash(password)


def verify_password(password: str, hash: str) -> bool:
    """Verify password against stored Argon2 hash"""
    try:
        ph.verify(hash, password)
        return True
    except VerifyMismatchError:
        return False


def generate_key_salt() -> bytes:
    """Generate random salt for key derivation (32 bytes)"""
    return secrets.token_bytes(32)


def generate_jwt_token(user_id: str) -> str:
    """Generate JWT token for user authentication"""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(days=30),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, backend_config.SECRET_KEY, algorithm='HS256')


def verify_jwt_token(token: str) -> dict:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, backend_config.SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Dependency to get current user from JWT token"""
    token = credentials.credentials

    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Token is invalid or expired"
        )

    return payload['user_id']