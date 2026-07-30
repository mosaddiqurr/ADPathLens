from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit

import idna

CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
AMBIGUOUS_IPV4 = re.compile(
    r"^(?:0[xX][0-9a-fA-F]+|0[0-7]+|\d+)(?:\.(?:0[xX][0-9a-fA-F]+|0[0-7]+|\d+)){0,3}$"
)

EXPLICITLY_BLOCKED_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.0.2.0/24",
        "192.88.99.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "224.0.0.0/4",
        "240.0.0.0/4",
        "::/128",
        "::1/128",
        "::ffff:0:0/96",
        "64:ff9b::/96",
        "100::/64",
        "2001:db8::/32",
        "2001:10::/28",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
    )
)

METADATA_ADDRESSES = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("169.254.170.2"),
    ipaddress.ip_address("100.100.100.200"),
}


class DestinationPolicyError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class NormalizedDestination:
    scheme: str
    hostname: str
    port: int
    path: str
    query: str

    @property
    def url(self) -> str:
        host = f"[{self.hostname}]" if ":" in self.hostname else self.hostname
        default_port = 443 if self.scheme == "https" else 80
        authority = host if self.port == default_port else f"{host}:{self.port}"
        return urlunsplit((self.scheme, authority, self.path, self.query, ""))


@dataclass(frozen=True)
class AllowlistRule:
    entry_type: str
    value: str
    port: int


def normalize_hostname(hostname: str) -> str:
    candidate = hostname.rstrip(".").lower()
    if not candidate or len(candidate) > 253 or CONTROL_CHARACTERS.search(candidate):
        raise DestinationPolicyError("invalid_hostname", "The destination hostname is invalid.")
    if "%" in candidate:
        raise DestinationPolicyError("invalid_hostname", "IPv6 zone identifiers are not supported.")
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        pass
    if AMBIGUOUS_IPV4.fullmatch(candidate):
        raise DestinationPolicyError(
            "ambiguous_ip_format", "Ambiguous numeric IP address formats are not supported."
        )
    try:
        ascii_host = idna.encode(candidate, uts46=True, std3_rules=True).decode("ascii")
    except idna.IDNAError as exc:
        raise DestinationPolicyError(
            "invalid_hostname", "The destination hostname is invalid."
        ) from exc
    if any(not label or len(label) > 63 for label in ascii_host.split(".")):
        raise DestinationPolicyError("invalid_hostname", "The destination hostname is invalid.")
    return ascii_host


def normalize_url(value: str) -> NormalizedDestination:
    if len(value) > 4096 or CONTROL_CHARACTERS.search(value):
        raise DestinationPolicyError("invalid_url", "The destination URL is invalid.")
    try:
        parsed: SplitResult = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise DestinationPolicyError(
                "unsupported_scheme", "Only HTTP and HTTPS destinations are supported."
            )
        if parsed.username is not None or parsed.password is not None:
            raise DestinationPolicyError(
                "embedded_credentials", "Credentials in destination URLs are not allowed."
            )
        if parsed.fragment:
            raise DestinationPolicyError(
                "url_fragment", "Destination URL fragments are not supported."
            )
        if not parsed.hostname:
            raise DestinationPolicyError("invalid_url", "The destination hostname is required.")
        scheme = parsed.scheme.lower()
        port = parsed.port or (443 if scheme == "https" else 80)
    except DestinationPolicyError:
        raise
    except ValueError as exc:
        raise DestinationPolicyError("invalid_url", "The destination URL is invalid.") from exc
    if not 1 <= port <= 65535:
        raise DestinationPolicyError("invalid_port", "The destination port is invalid.")
    hostname = normalize_hostname(parsed.hostname)
    path = parsed.path or "/"
    return NormalizedDestination(scheme, hostname, port, path, parsed.query)


def is_explicitly_blocked(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if address in METADATA_ADDRESSES:
        return True
    return any(address in network for network in EXPLICITLY_BLOCKED_NETWORKS)


def _rule_allows_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    port: int,
    rules: list[AllowlistRule],
) -> bool:
    for rule in rules:
        if rule.port != port or rule.entry_type not in {"ip", "cidr"}:
            continue
        try:
            if rule.entry_type == "ip" and address == ipaddress.ip_address(rule.value):
                return True
            if rule.entry_type == "cidr" and address in ipaddress.ip_network(
                rule.value, strict=False
            ):
                return True
        except ValueError:
            continue
    return False


def validate_destination(
    destination: NormalizedDestination,
    resolved_addresses: list[str],
    target_hostname: str,
    target_port: int,
    rules: list[AllowlistRule],
    *,
    authorization_confirmed: bool,
    allow_private_networks: bool,
    lab_network_confirmed: bool,
) -> list[str]:
    if not authorization_confirmed:
        raise DestinationPolicyError(
            "target_not_authorized", "The target authorization acknowledgement is required."
        )
    if destination.hostname != target_hostname or destination.port != target_port:
        raise DestinationPolicyError(
            "target_mismatch", "The destination does not match the selected target."
        )
    hostname_allowed = any(
        rule.entry_type == "hostname"
        and normalize_hostname(rule.value) == destination.hostname
        and rule.port == destination.port
        for rule in rules
    )
    literal_address: ipaddress.IPv4Address | ipaddress.IPv6Address | None
    try:
        literal_address = ipaddress.ip_address(destination.hostname)
    except ValueError:
        literal_address = None
    if not hostname_allowed and not (
        literal_address and _rule_allows_address(literal_address, destination.port, rules)
    ):
        raise DestinationPolicyError(
            "destination_not_allowlisted", "The destination is not on the target allowlist."
        )
    if not resolved_addresses:
        raise DestinationPolicyError("dns_no_results", "DNS resolution returned no addresses.")
    validated: list[str] = []
    for raw_address in resolved_addresses:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise DestinationPolicyError(
                "invalid_dns_result", "DNS resolution returned an invalid address."
            ) from exc
        if is_explicitly_blocked(address) or not address.is_global:
            if not (
                allow_private_networks
                and lab_network_confirmed
                and _rule_allows_address(address, destination.port, rules)
            ):
                raise DestinationPolicyError(
                    "blocked_network",
                    "The destination resolved to a network that is blocked by target policy.",
                )
        validated.append(str(address))
    return sorted(set(validated), key=lambda item: (":" in item, item))


async def resolve_all(hostname: str, port: int) -> list[str]:
    try:
        results = await asyncio.get_running_loop().getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise DestinationPolicyError(
            "dns_resolution_failed", "The destination hostname could not be resolved."
        ) from exc
    return sorted({str(item[4][0]) for item in results})
