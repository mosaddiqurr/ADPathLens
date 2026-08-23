from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, unquote, urlsplit

FORBIDDEN_HEADERS = {
    "host",
    "content-length",
    "transfer-encoding",
    "connection",
    "proxy-authorization",
    "proxy-authenticate",
    "upgrade",
    "keep-alive",
    "te",
    "trailer",
    "forwarded",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
}
SECRET_HEADERS = {
    "authorization",
    "cookie",
    "x-api-key",
    "proxy-authorization",
}
SUPPORTED_METHODS = {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}
STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
MAX_PATH_DECODE_LAYERS = 8
PATH_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


class RequestImportError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass
class ParsedRequest:
    method: str
    path: str
    query: list[list[str]] = field(default_factory=list)
    headers: list[list[str]] = field(default_factory=list)
    secret_headers: list[list[str]] = field(default_factory=list)
    body: str = ""
    content_type: str | None = None


def canonicalize_path(value: str) -> str:
    """Return the fully decoded path used for authorization-scope decisions."""

    candidate = value
    for _ in range(MAX_PATH_DECODE_LAYERS):
        if INVALID_PERCENT_ESCAPE.search(candidate):
            raise RequestImportError(
                "invalid_path_encoding", "The request path contains a malformed percent escape."
            )
        try:
            decoded = unquote(candidate, errors="strict")
        except UnicodeDecodeError as exc:
            raise RequestImportError(
                "invalid_path_encoding", "The request path contains invalid percent-encoded text."
            ) from exc
        if "\\" in decoded or PATH_CONTROL_CHARACTERS.search(decoded):
            raise RequestImportError("invalid_path", "The request path is invalid.")
        if not decoded.startswith("/") or decoded.startswith("//"):
            raise RequestImportError(
                "relative_path_required",
                "Requests must use a relative path on the selected target.",
            )
        if any(segment in {".", ".."} for segment in decoded.split("/")):
            raise RequestImportError("path_escape", "Path traversal segments are not allowed.")
        if decoded == candidate:
            return decoded
        candidate = decoded
    raise RequestImportError(
        "path_encoding_too_deep", "The request path uses ambiguous nested percent encoding."
    )


def validate_relative_path(value: str) -> tuple[str, list[list[str]]]:
    if not value or len(value) > 4096 or "\r" in value or "\n" in value or "\\" in value:
        raise RequestImportError("invalid_path", "The request path is invalid.")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith("/"):
        raise RequestImportError(
            "relative_path_required", "Requests must use a relative path on the selected target."
        )
    canonicalize_path(parsed.path)
    return parsed.path, [
        [key, value] for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]


def validate_outbound_path(value: str) -> tuple[str, str]:
    """Validate a rendered outbound path and return raw and canonical representations."""

    if "?" in value or "#" in value:
        raise RequestImportError(
            "rendered_path_delimiter",
            "Rendered path variables cannot introduce query or fragment delimiters.",
        )
    raw_path, query = validate_relative_path(value)
    if query:
        raise RequestImportError(
            "rendered_path_delimiter",
            "Rendered path variables cannot introduce query parameters.",
        )
    return raw_path, canonicalize_path(raw_path)


def validate_method(method: str) -> str:
    normalized = method.upper()
    if normalized not in SUPPORTED_METHODS:
        raise RequestImportError("unsupported_method", "The request method is unsupported.")
    return normalized


def split_headers(headers: list[list[str]]) -> tuple[list[list[str]], list[list[str]]]:
    safe: list[list[str]] = []
    secret: list[list[str]] = []
    for pair in headers:
        if len(pair) != 2:
            raise RequestImportError("invalid_header", "Each header requires a name and value.")
        name, value = pair
        lowered = name.lower()
        if not HEADER_NAME.fullmatch(name) or "\r" in value or "\n" in value:
            raise RequestImportError("invalid_header", "A request header is malformed.")
        if lowered in FORBIDDEN_HEADERS:
            raise RequestImportError(
                "forbidden_header", f"The {name} header cannot be supplied by a request."
            )
        destination = secret if lowered in SECRET_HEADERS else safe
        destination.append([name, value])
    return safe, secret


def parse_raw_http(raw: str) -> ParsedRequest:
    if len(raw.encode()) > 1024 * 1024:
        raise RequestImportError("request_too_large", "The raw request exceeds the size limit.")
    normalized = raw.replace("\r\n", "\n")
    head, separator, body = normalized.partition("\n\n")
    lines = head.splitlines()
    if not lines:
        raise RequestImportError("invalid_raw_request", "The request line is missing.")
    request_parts = lines[0].split()
    if len(request_parts) != 3 or not request_parts[2].startswith("HTTP/"):
        raise RequestImportError("invalid_raw_request", "The request line is malformed.")
    method = validate_method(request_parts[0])
    path, query = validate_relative_path(request_parts[1])
    headers: list[list[str]] = []
    for line in lines[1:]:
        if line.startswith((" ", "\t")) or ":" not in line:
            raise RequestImportError("invalid_header", "Folded or malformed headers are rejected.")
        name, value = line.split(":", 1)
        headers.append([name.strip(), value.strip()])
    safe, secret = split_headers(headers)
    content_type = next((value for name, value in safe if name.lower() == "content-type"), None)
    return ParsedRequest(
        method=method,
        path=path,
        query=query,
        headers=safe,
        secret_headers=secret,
        body=body if separator else "",
        content_type=content_type,
    )


def parse_curl(command: str) -> ParsedRequest:
    if len(command) > 64 * 1024:
        raise RequestImportError("curl_too_large", "The cURL command exceeds the size limit.")
    if any(marker in command for marker in ("$(", "`", "\n", "\r", "&&", "||", "|", ";")):
        raise RequestImportError("unsafe_curl", "Shell operators are not allowed.")
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        raise RequestImportError("invalid_curl", "The cURL command could not be parsed.") from exc
    if not tokens or tokens[0].lower() not in {"curl", "curl.exe"}:
        raise RequestImportError("invalid_curl", "The input must begin with curl.")
    method = "GET"
    headers: list[list[str]] = []
    body = ""
    url: str | None = None
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in {"-X", "--request"}:
            index += 1
            method = validate_method(tokens[index] if index < len(tokens) else "")
        elif token in {"-H", "--header"}:
            index += 1
            header = tokens[index] if index < len(tokens) else ""
            if ":" not in header:
                raise RequestImportError("invalid_header", "A cURL header is malformed.")
            name, value = header.split(":", 1)
            headers.append([name.strip(), value.strip()])
        elif token in {"-b", "--cookie"}:
            index += 1
            value = tokens[index] if index < len(tokens) else ""
            headers.append(["Cookie", value])
        elif token in {"-d", "--data", "--data-raw"}:
            index += 1
            value = tokens[index] if index < len(tokens) else ""
            if value.startswith("@"):
                raise RequestImportError("curl_file_read", "File-backed cURL data is not allowed.")
            body = value
            if method == "GET":
                method = "POST"
        elif token.startswith("-"):
            raise RequestImportError(
                "unsupported_curl_option", f"The cURL option {token} is not supported."
            )
        elif url is None:
            url = token
        else:
            raise RequestImportError("invalid_curl", "Unexpected cURL argument.")
        index += 1
    if not url:
        raise RequestImportError("invalid_curl", "The cURL URL is missing.")
    parsed_url = urlsplit(url)
    relative = (
        f"{parsed_url.path or '/'}?{parsed_url.query}"
        if parsed_url.scheme and parsed_url.netloc
        else url
    )
    path, query = validate_relative_path(relative)
    safe, secret = split_headers(headers)
    content_type = next((value for name, value in safe if name.lower() == "content-type"), None)
    return ParsedRequest(method, path, query, safe, secret, body, content_type)


def json_nesting_depth(value: object, current: int = 0) -> int:
    if current > 50:
        return current
    if isinstance(value, dict):
        return max([current, *(json_nesting_depth(item, current + 1) for item in value.values())])
    if isinstance(value, list):
        return max([current, *(json_nesting_depth(item, current + 1) for item in value)])
    return current


def parse_har(data: bytes) -> list[ParsedRequest]:
    try:
        document = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RequestImportError("invalid_har", "The HAR file is not valid JSON.") from exc
    if json_nesting_depth(document) > 30:
        raise RequestImportError("har_too_deep", "The HAR structure is excessively nested.")
    try:
        entries = document["log"]["entries"]
    except (KeyError, TypeError) as exc:
        raise RequestImportError("invalid_har", "The HAR request entries are missing.") from exc
    if not isinstance(entries, list) or len(entries) > 500:
        raise RequestImportError("har_entry_limit", "The HAR contains too many request entries.")
    parsed_requests: list[ParsedRequest] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise RequestImportError("invalid_har_entry", "Each HAR entry must be a JSON object.")
        request = entry.get("request", {})
        if not isinstance(request, dict):
            raise RequestImportError(
                "invalid_har_request", "Each HAR entry must contain a request object."
            )
        url = urlsplit(str(request.get("url", "")))
        if url.scheme not in {"http", "https"}:
            continue
        path, query = validate_relative_path(
            f"{url.path or '/'}?{url.query}" if url.query else (url.path or "/")
        )
        raw_headers = request.get("headers", [])
        if not isinstance(raw_headers, list) or any(
            not isinstance(item, dict) for item in raw_headers
        ):
            raise RequestImportError(
                "invalid_har_headers", "HAR request headers must be a list of objects."
            )
        headers = [[str(item.get("name", "")), str(item.get("value", ""))] for item in raw_headers]
        safe, secret = split_headers(headers)
        post_data = request.get("postData", {})
        if post_data is None:
            post_data = {}
        if not isinstance(post_data, dict):
            raise RequestImportError(
                "invalid_har_post_data", "HAR postData must be an object when present."
            )
        parsed_requests.append(
            ParsedRequest(
                method=validate_method(str(request.get("method", "GET"))),
                path=path,
                query=query,
                headers=safe,
                secret_headers=secret,
                body=str(post_data.get("text", "")),
                content_type=post_data.get("mimeType"),
            )
        )
    return parsed_requests
