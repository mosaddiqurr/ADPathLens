from __future__ import annotations

import asyncio
import hmac
import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.store import document, reset_fixtures, update_user, user, users

if os.environ.get("APP_ENV", "development").lower() == "production":
    raise RuntimeError(
        "The intentionally vulnerable demo target cannot run in production."
    )

app = FastAPI(
    title="AuthZDiff intentionally vulnerable demo target",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)


@dataclass(frozen=True)
class DemoIdentity:
    user_id: str
    role: str


# These are intentionally public, synthetic fixture tokens—not production credentials.
DEMO_IDENTITIES = {
    "demo-admin-token": DemoIdentity("admin", "administrator"),
    "demo-user-a-token": DemoIdentity("user-a", "user"),
    "demo-user-b-token": DemoIdentity("user-b", "user"),
}


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)


async def current_identity(
    authorization: Annotated[str | None, Header()] = None,
) -> DemoIdentity:
    scheme, _, token = (authorization or "").partition(" ")
    identity = DEMO_IDENTITIES.get(token) if scheme.lower() == "bearer" else None
    if identity is None:
        raise HTTPException(
            status_code=401, detail="A valid demo bearer token is required."
        )
    return identity


async def require_administrator(
    identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> DemoIdentity:
    if identity.role != "administrator":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return identity


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "authzdiff-demo-target"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready", "service": "authzdiff-demo-target"}


@app.get("/secure/authenticated")
async def secure_authenticated(
    identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, str]:
    return {"user_id": identity.user_id, "fixture": "secure-authentication-control"}


@app.get("/secure/admin/users")
async def secure_admin_users(
    _identity: Annotated[DemoIdentity, Depends(require_administrator)],
) -> dict[str, object]:
    return {"users": users(), "fixture": "secure-vertical-control"}


@app.get("/vulnerable/admin/users")
async def vulnerable_admin_users(
    _identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, object]:
    # Intentionally vulnerable: authenticated non-administrators receive the admin listing.
    return {"users": users(), "fixture": "vulnerable-vertical-control"}


@app.get("/secure/documents/{document_id}")
async def secure_document(
    document_id: str,
    identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, object]:
    value = document(document_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if identity.role != "administrator" and value["owner_id"] != identity.user_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    return value


@app.get("/vulnerable/documents/{document_id}")
async def vulnerable_document(
    document_id: str,
    _identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, object]:
    # Intentionally vulnerable: object ownership is not checked.
    value = document(document_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return value


@app.get("/secure/accounts/{user_id}")
async def secure_account(
    user_id: str,
    identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, object]:
    if identity.role != "administrator" and identity.user_id != user_id:
        raise HTTPException(status_code=404, detail="Account not found.")
    value = user(user_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    return {
        "id": value["id"],
        "name": value["name"],
        "role": value["role"],
        "fixture": "secure-sensitive-field-control",
    }


@app.get("/vulnerable/accounts/{user_id}")
async def vulnerable_account(
    user_id: str,
    _identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, object]:
    value = user(user_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    # Synthetic sensitive values used to verify response redaction and field comparisons.
    return {
        **value,
        "national_id": f"DEMO-NATIONAL-ID-{user_id.upper()}",
        "api_key": f"demo_fixture_key_{user_id}_not_real",
        "fixture": "vulnerable-sensitive-field-exposure",
    }


@app.get("/secure/existence/documents/{document_id}")
async def secure_existence_control(
    document_id: str,
    identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, object]:
    value = document(document_id)
    if value is None or (
        identity.role != "administrator" and value["owner_id"] != identity.user_id
    ):
        raise HTTPException(status_code=404, detail="Document not found.")
    return value


@app.get("/vulnerable/existence/documents/{document_id}")
async def vulnerable_existence_leak(
    document_id: str,
    identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, object]:
    value = document(document_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if identity.role != "administrator" and value["owner_id"] != identity.user_id:
        # Intentionally leaks that the object exists through a distinguishable response.
        raise HTTPException(
            status_code=403, detail="Document exists but belongs to another user."
        )
    return value


@app.delete("/secure/method-protection/documents/{document_id}")
async def secure_method_protection(
    document_id: str,
    _identity: Annotated[DemoIdentity, Depends(require_administrator)],
) -> dict[str, str]:
    if document(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"status": "simulated-delete", "fixture": "secure-method-control"}


@app.delete("/vulnerable/method-protection/documents/{document_id}")
async def vulnerable_method_protection(
    document_id: str,
    _identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, str]:
    # Intentionally vulnerable: read authorization was not applied to this method.
    if document(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"status": "simulated-delete", "fixture": "vulnerable-method-control"}


@app.patch("/secure/profiles/{user_id}")
async def secure_profile_update(
    user_id: str,
    payload: ProfileUpdate,
    identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, object]:
    if identity.role != "administrator" and identity.user_id != user_id:
        raise HTTPException(status_code=403, detail="Profile ownership is required.")
    updated = update_user(user_id, payload.display_name)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return updated


@app.patch("/vulnerable/profiles/{user_id}")
async def vulnerable_profile_update(
    user_id: str,
    payload: ProfileUpdate,
    _identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, object]:
    # Intentionally vulnerable: any authenticated identity can update any profile.
    updated = update_user(user_id, payload.display_name)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return updated


@app.get("/ambiguous")
async def ambiguous(
    identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, object]:
    # Deliberately gives weak evidence: 200 with generic role-independent content.
    return {
        "status": "accepted",
        "message": "The fictional request is being processed.",
        "authenticated": bool(identity.user_id),
    }


@app.get("/slow")
async def slow_fixture(
    identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, str]:
    await asyncio.sleep(1.5)
    return {
        "status": "complete",
        "user_id": identity.user_id,
        "fixture": "bounded-slow",
    }


@app.post("/internal/reset")
async def reset(
    reset_token: Annotated[str | None, Header(alias="X-Demo-Reset-Token")] = None,
) -> dict[str, str]:
    if os.environ.get("DEMO_MODE", "").lower() != "true":
        raise HTTPException(status_code=403, detail="Demo reset is disabled.")
    expected = os.environ.get("DEMO_RESET_TOKEN", "")
    if (
        not expected
        or not reset_token
        or not hmac.compare_digest(reset_token, expected)
    ):
        raise HTTPException(status_code=403, detail="The demo reset token is invalid.")
    reset_fixtures()
    return {"status": "reset"}


@app.get("/profiles/{user_id}")
async def profile(
    user_id: str,
    identity: Annotated[DemoIdentity, Depends(current_identity)],
) -> dict[str, object]:
    if identity.role != "administrator" and identity.user_id != user_id:
        raise HTTPException(status_code=403, detail="Profile ownership is required.")
    value = user(user_id)
    if value is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return value
