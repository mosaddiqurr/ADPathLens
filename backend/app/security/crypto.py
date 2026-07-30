from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class SecretEncryptionError(ValueError):
    pass


def _decode_key(value: str) -> bytes:
    try:
        key = base64.urlsafe_b64decode(value.encode("ascii"))
    except (ValueError, UnicodeError) as exc:
        raise SecretEncryptionError("Encryption key must be URL-safe base64.") from exc
    if len(key) != 32:
        raise SecretEncryptionError("Encryption keys must decode to exactly 32 bytes.")
    return key


def key_identifier(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()[:16]


@dataclass(frozen=True)
class KeyRing:
    active_key: bytes
    keys: dict[str, bytes]
    fingerprint_key: bytes

    @classmethod
    def from_settings(cls, active: str, old_keys: str = "") -> KeyRing:
        decoded = [_decode_key(active)]
        decoded.extend(_decode_key(value.strip()) for value in old_keys.split(",") if value.strip())
        keys = {key_identifier(key): key for key in decoded}
        fingerprint_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"authzdiff-key-derivation-v1",
            info=b"credential-fingerprints",
        ).derive(decoded[0])
        return cls(active_key=decoded[0], keys=keys, fingerprint_key=fingerprint_key)

    def encrypt(self, plaintext: bytes, associated_data: str) -> bytes:
        nonce = os.urandom(12)
        ciphertext = AESGCM(self.active_key).encrypt(
            nonce, plaintext, associated_data.encode("utf-8")
        )
        envelope = {
            "v": 1,
            "kid": key_identifier(self.active_key),
            "n": base64.urlsafe_b64encode(nonce).decode("ascii"),
            "c": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        }
        return json.dumps(envelope, separators=(",", ":")).encode("utf-8")

    def decrypt(self, envelope_bytes: bytes, associated_data: str) -> bytes:
        try:
            envelope = json.loads(envelope_bytes)
            if envelope.get("v") != 1:
                raise SecretEncryptionError("Unsupported encrypted-secret version.")
            key = self.keys[envelope["kid"]]
            nonce = base64.urlsafe_b64decode(envelope["n"])
            ciphertext = base64.urlsafe_b64decode(envelope["c"])
            return AESGCM(key).decrypt(nonce, ciphertext, associated_data.encode("utf-8"))
        except SecretEncryptionError:
            raise
        except (InvalidTag, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise SecretEncryptionError("Encrypted secret could not be decrypted.") from exc

    def fingerprint(self, secret: bytes) -> str:
        digest = hmac.new(self.fingerprint_key, secret, hashlib.sha256).hexdigest()
        return f"hmac:{digest[:16]}"
