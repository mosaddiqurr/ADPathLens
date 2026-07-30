from __future__ import annotations

import base64

import pytest

from app.parsers.request_import import RequestImportError, parse_curl, parse_raw_http
from app.replay.normalization import normalize_response
from app.security.crypto import KeyRing, SecretEncryptionError
from app.security.ssrf import (
    AllowlistRule,
    DestinationPolicyError,
    normalize_hostname,
    normalize_url,
    validate_destination,
)


def _key(byte: int) -> str:
    return base64.urlsafe_b64encode(bytes([byte]) * 32).decode()


def test_ciphertext_is_bound_to_associated_data_and_supports_old_keys() -> None:
    old_ring = KeyRing.from_settings(_key(1))
    original_binding = "test_session:project-one:target-one:profile-one:authorization"
    moved_project_binding = "test_session:project-two:target-one:profile-one:authorization"
    ciphertext = old_ring.encrypt(b"Bearer demo-only", original_binding)
    rotated = KeyRing.from_settings(_key(2), _key(1))

    assert b"Bearer demo-only" not in ciphertext
    assert rotated.decrypt(ciphertext, original_binding) == b"Bearer demo-only"
    with pytest.raises(SecretEncryptionError):
        rotated.decrypt(ciphertext, moved_project_binding)


@pytest.mark.parametrize(
    "value,code",
    [
        ("http://user:pass@example.com/", "embedded_credentials"),
        ("ftp://example.com/", "unsupported_scheme"),
        ("https://example.com/#fragment", "url_fragment"),
        ("http://0177.0.0.1/", "ambiguous_ip_format"),
        ("http://0x7f000001/", "ambiguous_ip_format"),
        ("http://[fe80::1%25eth0]/", "invalid_hostname"),
    ],
)
def test_url_normalization_rejects_ambiguous_destinations(value: str, code: str) -> None:
    with pytest.raises(DestinationPolicyError) as caught:
        normalize_url(value)
    assert caught.value.code == code


def test_idna_and_default_port_are_canonicalized() -> None:
    destination = normalize_url("HTTPS://BÜCHER.example./api")
    assert destination.hostname == "xn--bcher-kva.example"
    assert destination.port == 443
    assert destination.url == "https://xn--bcher-kva.example/api"
    assert normalize_hostname("EXAMPLE.com.") == "example.com"


def test_public_policy_fails_closed_on_mixed_dns_answers() -> None:
    destination = normalize_url("https://example.com/")
    rules = [AllowlistRule("hostname", "example.com", 443)]
    with pytest.raises(DestinationPolicyError) as caught:
        validate_destination(
            destination,
            ["8.8.8.8", "127.0.0.1"],
            "example.com",
            443,
            rules,
            authorization_confirmed=True,
            allow_private_networks=False,
            lab_network_confirmed=False,
        )
    assert caught.value.code == "blocked_network"


def test_private_lab_requires_exact_address_rule() -> None:
    destination = normalize_url("http://demo-target:8001/")
    hostname_only = [AllowlistRule("hostname", "demo-target", 8001)]
    with pytest.raises(DestinationPolicyError) as caught:
        validate_destination(
            destination,
            ["172.20.0.10"],
            "demo-target",
            8001,
            hostname_only,
            authorization_confirmed=True,
            allow_private_networks=True,
            lab_network_confirmed=True,
        )
    assert caught.value.code == "blocked_network"

    rules = hostname_only + [AllowlistRule("cidr", "172.20.0.0/24", 8001)]
    assert validate_destination(
        destination,
        ["172.20.0.10"],
        "demo-target",
        8001,
        rules,
        authorization_confirmed=True,
        allow_private_networks=True,
        lab_network_confirmed=True,
    ) == ["172.20.0.10"]


@pytest.mark.parametrize(
    "command",
    [
        "curl https://example.com/$(whoami)",
        "curl --proxy http://proxy.invalid https://example.com/",
        "curl --data @secrets.txt https://example.com/",
        "curl https://example.com/ | powershell",
    ],
)
def test_curl_import_never_accepts_execution_or_file_features(command: str) -> None:
    with pytest.raises(RequestImportError):
        parse_curl(command)


def test_raw_import_separates_secret_headers() -> None:
    parsed = parse_raw_http(
        "GET /me?view=full HTTP/1.1\r\n"
        "Authorization: Bearer demo-only-token\r\n"
        "Accept: application/json\r\n\r\n"
    )
    assert parsed.headers == [["Accept", "application/json"]]
    assert parsed.secret_headers == [["Authorization", "Bearer demo-only-token"]]
    assert parsed.query == [["view", "full"]]


def test_normalization_redacts_body_and_response_headers() -> None:
    normalized = normalize_response(
        status_code=200,
        headers=[
            ("Content-Type", "application/json"),
            ("Set-Cookie", "session=reusable"),
            ("Location", "/next?token=reusable"),
        ],
        body=(b'{"password":"cleartext","authorization":"Bearer short-token","safe":"visible"}'),
        content_type="application/json",
        max_excerpt_bytes=10_000,
        expected_markers=["visible"],
    )
    assert "cleartext" not in (normalized.excerpt or "")
    assert "short-token" not in (normalized.excerpt or "")
    assert normalized.structural == {
        "authorization": "[REDACTED]",
        "password": "[REDACTED]",
        "safe": "visible",
    }
    assert ["set-cookie", "session=reusable"] not in normalized.safe_headers
    assert ["location", "/next"] in normalized.safe_headers


def test_binary_normalization_persists_hash_and_metadata_only() -> None:
    normalized = normalize_response(
        status_code=200,
        headers=[("Content-Type", "application/octet-stream")],
        body=b"\x00Bearer reusable-binary-secret",
        content_type="application/octet-stream",
        max_excerpt_bytes=10_000,
        expected_markers=[],
    )
    assert normalized.binary is True
    assert normalized.excerpt is None
    assert normalized.structural is None
    assert len(normalized.body_hash) == 64
