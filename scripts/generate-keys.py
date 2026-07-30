from __future__ import annotations

import base64
import secrets

print(f"APP_SECRET_KEY={base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}")
print(
    f"ENCRYPTION_MASTER_KEY={base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}"
)
print(f"FIRST_ADMIN_SETUP_TOKEN={secrets.token_urlsafe(32)}")
print(f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}")
