from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

USERS_FIXTURE = {
    "admin": {
        "id": "admin",
        "name": "Demo Administrator",
        "email": "admin@example.invalid",
        "role": "administrator",
    },
    "user-a": {
        "id": "user-a",
        "name": "Demo User A",
        "email": "user-a@example.invalid",
        "role": "user",
    },
    "user-b": {
        "id": "user-b",
        "name": "Demo User B",
        "email": "user-b@example.invalid",
        "role": "user",
    },
}

DOCUMENTS_FIXTURE = {
    "doc-a": {
        "id": "doc-a",
        "owner_id": "user-a",
        "title": "User A quarterly plan",
        "classification": "fictional-demo",
    },
    "doc-b": {
        "id": "doc-b",
        "owner_id": "user-b",
        "title": "User B quarterly plan",
        "classification": "fictional-demo",
    },
}

_lock = RLock()
_users: dict[str, dict[str, Any]] = {}
_documents: dict[str, dict[str, Any]] = {}


def reset_fixtures() -> None:
    with _lock:
        _users.clear()
        _users.update(deepcopy(USERS_FIXTURE))
        _documents.clear()
        _documents.update(deepcopy(DOCUMENTS_FIXTURE))


def users() -> list[dict[str, Any]]:
    with _lock:
        return deepcopy(list(_users.values()))


def user(user_id: str) -> dict[str, Any] | None:
    with _lock:
        value = _users.get(user_id)
        return deepcopy(value) if value else None


def update_user(user_id: str, display_name: str) -> dict[str, Any] | None:
    with _lock:
        value = _users.get(user_id)
        if value is None:
            return None
        value["name"] = display_name
        return deepcopy(value)


def document(document_id: str) -> dict[str, Any] | None:
    with _lock:
        value = _documents.get(document_id)
        return deepcopy(value) if value else None


reset_fixtures()
