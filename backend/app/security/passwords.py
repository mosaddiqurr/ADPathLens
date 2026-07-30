from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from argon2.low_level import Type

password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def validate_password(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")
    if len(password) > 128:
        raise ValueError("Password must contain at most 128 characters.")


def hash_password(password: str) -> str:
    validate_password(password)
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True
