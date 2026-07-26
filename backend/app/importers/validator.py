from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from app.core.config import Settings
from app.graph.catalog import NODE_TYPES, RELATIONSHIP_CATALOG


@dataclass
class ValidationMessage:
    level: str
    code: str
    message: str
    location: str | None = None


@dataclass
class ValidationResult:
    digest: str
    nodes: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    messages: list[ValidationMessage] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(message.level == "error" for message in self.messages)

    def summary(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "digest": self.digest,
            "node_count": len(self.nodes),
            "relationship_count": len(self.relationships),
            "messages": [
                {
                    "level": message.level,
                    "code": message.code,
                    "message": message.message,
                    "location": message.location,
                }
                for message in self.messages
            ],
        }


def _has_executable_signature(data: bytes) -> bool:
    return data.startswith((b"MZ", b"\x7fELF", b"#!"))


def _depth(value: Any, current: int = 0) -> int:
    if isinstance(value, dict):
        return max([current, *(_depth(item, current + 1) for item in value.values())])
    if isinstance(value, list):
        return max([current, *(_depth(item, current + 1) for item in value)])
    return current


def _boolean(value: Any, default: bool) -> bool | None:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "1", "yes"}:
        return True
    if isinstance(value, str) and value.lower() in {"false", "0", "no"}:
        return False
    return None


def validate_json_bytes(data: bytes, settings: Settings) -> ValidationResult:
    digest = hashlib.sha256(data).hexdigest()
    if _has_executable_signature(data):
        return ValidationResult(
            digest=digest,
            messages=[
                ValidationMessage(
                    "error",
                    "executable_signature",
                    "Executable content is not accepted.",
                )
            ],
        )
    result = ValidationResult(digest=digest)
    if len(data) > settings.max_upload_bytes:
        result.messages.append(ValidationMessage("error", "file_too_large", "Upload is too large."))
        return result
    try:
        parsed = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        result.messages.append(ValidationMessage("error", "invalid_utf8", "File must be UTF-8."))
        return result
    except json.JSONDecodeError as exc:
        result.messages.append(ValidationMessage("error", "invalid_json", "JSON is malformed.", f"line {exc.lineno}"))
        return result
    if _depth(parsed) > settings.max_json_depth:
        result.messages.append(
            ValidationMessage("error", "json_too_deep", "JSON nesting exceeds the configured limit.")
        )
        return result
    if not isinstance(parsed, dict):
        result.messages.append(ValidationMessage("error", "invalid_root", "JSON root must be an object."))
        return result
    return validate_records(parsed.get("nodes", []), parsed.get("relationships", []), digest, settings)


def validate_records(
    raw_nodes: Any,
    raw_relationships: Any,
    digest: str,
    settings: Settings,
) -> ValidationResult:
    result = ValidationResult(digest=digest)
    if not isinstance(raw_nodes, list) or not isinstance(raw_relationships, list):
        result.messages.append(ValidationMessage("error", "invalid_arrays", "Nodes and relationships must be arrays."))
        return result
    if len(raw_nodes) > settings.max_graph_nodes:
        result.messages.append(ValidationMessage("error", "too_many_nodes", "Dataset exceeds the node limit."))
    if len(raw_relationships) > settings.max_graph_relationships:
        result.messages.append(
            ValidationMessage("error", "too_many_relationships", "Dataset exceeds the relationship limit.")
        )
    node_ids: set[str] = set()
    for position, item in enumerate(raw_nodes):
        location = f"nodes[{position}]"
        if not isinstance(item, dict):
            result.messages.append(ValidationMessage("error", "invalid_node", "Node must be an object.", location))
            continue
        external_id = str(item.get("id", "")).strip()
        node_type = str(item.get("type", "")).strip()
        name = str(item.get("name", "")).strip()
        if not external_id or not node_type or not name:
            result.messages.append(
                ValidationMessage("error", "missing_node_field", "Node requires id, type, and name.", location)
            )
            continue
        if len(external_id) > 256 or len(name) > 256:
            result.messages.append(
                ValidationMessage("error", "field_too_long", "Node id or name is too long.", location)
            )
            continue
        if external_id in node_ids:
            result.messages.append(ValidationMessage("error", "duplicate_node_id", external_id, location))
            continue
        if node_type not in NODE_TYPES:
            result.messages.append(ValidationMessage("error", "unsupported_node_type", node_type, location))
            continue
        enabled = _boolean(item.get("enabled"), True)
        privileged = _boolean(item.get("privileged"), False)
        high_value = _boolean(item.get("high_value"), False)
        if enabled is None or privileged is None or high_value is None:
            result.messages.append(ValidationMessage("error", "invalid_boolean", "Invalid Boolean value.", location))
            continue
        metadata = item.get("metadata", item.get("metadata_json", {})) or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                result.messages.append(
                    ValidationMessage("error", "invalid_metadata", "Metadata is not JSON.", location)
                )
                continue
        if not isinstance(metadata, dict) or len(json.dumps(metadata)) > 65_536:
            result.messages.append(
                ValidationMessage("error", "invalid_metadata", "Metadata must be a small object.", location)
            )
            continue
        node_ids.add(external_id)
        if node_type == "Unknown":
            result.messages.append(
                ValidationMessage(
                    "warning",
                    "unknown_node_type",
                    "Unknown nodes are retained but may reduce analysis quality.",
                    location,
                )
            )
        result.nodes.append(
            {
                "external_id": external_id,
                "node_type": node_type,
                "name": name,
                "display_name": str(item.get("display_name") or name)[:256],
                "description": str(item.get("description") or "")[:4000],
                "domain_name": str(item.get("domain") or "")[:256] or None,
                "enabled": enabled,
                "privileged": privileged,
                "high_value": high_value,
                "risk_level": str(item.get("risk_level") or "informational"),
                "metadata_json": metadata,
            }
        )
    relationship_ids: set[str] = set()
    semantic_edges: set[tuple[str, str, str]] = set()
    for position, item in enumerate(raw_relationships):
        location = f"relationships[{position}]"
        if not isinstance(item, dict):
            result.messages.append(
                ValidationMessage("error", "invalid_relationship", "Relationship must be an object.", location)
            )
            continue
        external_id = str(item.get("id", "")).strip()
        source = str(item.get("source", "")).strip()
        target = str(item.get("target", "")).strip()
        relationship_type = str(item.get("type", "")).strip()
        if not all((external_id, source, target, relationship_type)):
            result.messages.append(
                ValidationMessage(
                    "error",
                    "missing_relationship_field",
                    "Relationship requires id, source, target, and type.",
                    location,
                )
            )
            continue
        if external_id in relationship_ids:
            result.messages.append(ValidationMessage("error", "duplicate_relationship_id", external_id, location))
            continue
        if source not in node_ids or target not in node_ids:
            result.messages.append(
                ValidationMessage("error", "missing_endpoint", "Source or target node does not exist.", location)
            )
            continue
        if source == target:
            result.messages.append(
                ValidationMessage("error", "self_loop", "Self-loops are not supported in v1.", location)
            )
            continue
        definition = RELATIONSHIP_CATALOG.get(relationship_type)
        if definition is None:
            result.messages.append(
                ValidationMessage("error", "unsupported_relationship_type", relationship_type, location)
            )
            continue
        semantic = (source, target, relationship_type)
        if semantic in semantic_edges:
            result.messages.append(
                ValidationMessage("error", "duplicate_relationship", "Duplicate relationship.", location)
            )
            continue
        inherited = _boolean(item.get("inherited"), False)
        active = _boolean(item.get("active"), True)
        if inherited is None or active is None:
            result.messages.append(ValidationMessage("error", "invalid_boolean", "Invalid Boolean value.", location))
            continue
        confidence = str(item.get("confidence") or "high").lower()
        if confidence not in {"high", "medium", "low", "unknown"}:
            result.messages.append(ValidationMessage("error", "invalid_confidence", confidence, location))
            continue
        if confidence in {"low", "unknown"}:
            result.messages.append(
                ValidationMessage(
                    "warning",
                    "uncertain_relationship",
                    "Low-confidence relationship requires analyst acknowledgement.",
                    location,
                )
            )
        evidence = item.get("evidence", item.get("evidence_json", {})) or {}
        metadata = item.get("metadata", item.get("metadata_json", {})) or {}
        try:
            if isinstance(evidence, str):
                evidence = json.loads(evidence)
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
        except json.JSONDecodeError:
            result.messages.append(
                ValidationMessage("error", "invalid_metadata", "Evidence or metadata is invalid.", location)
            )
            continue
        relationship_ids.add(external_id)
        semantic_edges.add(semantic)
        result.relationships.append(
            {
                "external_id": external_id,
                "source_external_id": source,
                "target_external_id": target,
                "relationship_type": relationship_type,
                "direction": definition.direction,
                "inherited": inherited,
                "active": active,
                "risk_weight": definition.weight,
                "confidence": confidence,
                "description": str(item.get("description") or "")[:4000],
                "evidence_json": evidence if isinstance(evidence, dict) else {},
                "metadata_json": metadata if isinstance(metadata, dict) else {},
            }
        )
    if result.valid:
        result.messages.append(
            ValidationMessage(
                "information",
                "validation_complete",
                f"Validated {len(result.nodes)} nodes and {len(result.relationships)} relationships.",
            )
        )
    return result


def validate_csv_bytes(nodes_data: bytes, relationships_data: bytes, settings: Settings) -> ValidationResult:
    digest = hashlib.sha256(nodes_data + b"\0" + relationships_data).hexdigest()
    if _has_executable_signature(nodes_data) or _has_executable_signature(relationships_data):
        return ValidationResult(
            digest=digest,
            messages=[
                ValidationMessage(
                    "error",
                    "executable_signature",
                    "Executable content is not accepted.",
                )
            ],
        )
    if len(nodes_data) + len(relationships_data) > settings.max_upload_bytes:
        return ValidationResult(
            digest=digest,
            messages=[ValidationMessage("error", "file_too_large", "Upload is too large.")],
        )
    try:
        node_rows = list(csv.DictReader(io.StringIO(nodes_data.decode("utf-8-sig"))))
        relationship_rows = list(csv.DictReader(io.StringIO(relationships_data.decode("utf-8-sig"))))
    except UnicodeDecodeError:
        return ValidationResult(
            digest=digest,
            messages=[ValidationMessage("error", "invalid_utf8", "CSV must be UTF-8.")],
        )
    if len(node_rows) + len(relationship_rows) > settings.max_csv_rows:
        return ValidationResult(
            digest=digest,
            messages=[ValidationMessage("error", "too_many_rows", "CSV row limit exceeded.")],
        )
    return validate_records(node_rows, relationship_rows, digest, settings)


def validate_zip_bytes(data: bytes, settings: Settings) -> ValidationResult:
    digest = hashlib.sha256(data).hexdigest()
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return ValidationResult(
            digest=digest,
            messages=[ValidationMessage("error", "malformed_zip", "ZIP archive is malformed.")],
        )
    entries = archive.infolist()
    if len(entries) > settings.max_archive_entries:
        return ValidationResult(
            digest=digest,
            messages=[ValidationMessage("error", "too_many_entries", "Archive has too many entries.")],
        )
    names: set[str] = set()
    entries_by_name: dict[str, zipfile.ZipInfo] = {}
    total_size = 0
    for entry in entries:
        path = PurePosixPath(entry.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
            return ValidationResult(
                digest=digest,
                messages=[ValidationMessage("error", "unsafe_archive_entry", entry.filename)],
            )
        if entry.external_attr >> 16 & 0o170000 == 0o120000:
            return ValidationResult(
                digest=digest,
                messages=[ValidationMessage("error", "archive_symlink", entry.filename)],
            )
        if entry.filename.lower().endswith((".zip", ".exe", ".dll", ".ps1", ".bat", ".cmd")):
            return ValidationResult(
                digest=digest,
                messages=[ValidationMessage("error", "prohibited_archive_entry", entry.filename)],
            )
        normalized_name = path.name.lower()
        if normalized_name in names:
            return ValidationResult(
                digest=digest,
                messages=[ValidationMessage("error", "duplicate_archive_entry", entry.filename)],
            )
        names.add(normalized_name)
        entries_by_name[normalized_name] = entry
        total_size += entry.file_size
        if entry.file_size > 1_000_000 and entry.file_size / max(entry.compress_size, 1) > 100:
            return ValidationResult(
                digest=digest,
                messages=[ValidationMessage("error", "zip_bomb", "Unsafe compression ratio detected.")],
            )
    if names != {"nodes.csv", "relationships.csv"}:
        return ValidationResult(
            digest=digest,
            messages=[
                ValidationMessage(
                    "error", "unexpected_archive_layout", "ZIP requires only the two documented CSV files."
                )
            ],
        )
    if total_size > settings.max_uncompressed_bytes:
        return ValidationResult(
            digest=digest,
            messages=[ValidationMessage("error", "zip_bomb", "Uncompressed size limit exceeded.")],
        )
    nodes_bytes = archive.read(entries_by_name["nodes.csv"])
    relationships_bytes = archive.read(entries_by_name["relationships.csv"])
    result = validate_csv_bytes(nodes_bytes, relationships_bytes, settings)
    result.digest = digest
    return result
