import io
import json
import warnings
import zipfile

from app.core.config import get_settings
from app.importers.validator import validate_json_bytes, validate_zip_bytes


def _archive(entries: list[tuple[str, bytes, int | None]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content, external_attr in entries:
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            if external_attr is not None:
                info.external_attr = external_attr
            archive.writestr(info, content)
    return output.getvalue()


def _codes(raw: bytes) -> list[str]:
    return [message.code for message in validate_zip_bytes(raw, get_settings()).messages]


def test_archive_rejects_symlink_nested_duplicate_executable_and_bomb() -> None:
    relationships = b"id,source,target,type\n"
    symlink_mode = (0o120777 << 16) | 0xA1ED
    assert _codes(
        _archive(
            [
                ("nodes.csv", b"target", symlink_mode),
                ("relationships.csv", relationships, None),
            ]
        )
    ) == ["archive_symlink"]
    assert _codes(
        _archive(
            [
                ("nodes.csv", b"id,type,name\nu,User,Lab\n", None),
                ("payload.zip", b"PK\x03\x04", None),
            ]
        )
    ) == ["prohibited_archive_entry"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        duplicate_archive = _archive(
            [
                ("nodes.csv", b"id,type,name\nu,User,Lab\n", None),
                ("nodes.csv", b"id,type,name\nv,User,Lab\n", None),
                ("relationships.csv", relationships, None),
            ]
        )
    assert _codes(duplicate_archive) == ["duplicate_archive_entry"]
    assert _codes(
        _archive(
            [
                ("nodes.csv", b"MZ executable", None),
                ("relationships.csv", relationships, None),
            ]
        )
    ) == ["executable_signature"]
    assert _codes(
        _archive(
            [
                ("nodes.csv", b"A" * 1_100_000, None),
                ("relationships.csv", relationships, None),
            ]
        )
    ) == ["zip_bomb"]


def test_json_rejects_executable_depth_duplicates_and_invalid_semantics() -> None:
    executable = validate_json_bytes(b"MZ executable", get_settings())
    assert executable.messages[0].code == "executable_signature"

    nested: object = "leaf"
    for _ in range(get_settings().max_json_depth + 2):
        nested = {"child": nested}
    too_deep = validate_json_bytes(
        json.dumps({"nodes": [], "relationships": [], "metadata": nested}).encode(),
        get_settings(),
    )
    assert too_deep.messages[0].code == "json_too_deep"

    invalid = {
        "nodes": [
            {"id": "one", "type": "User", "name": "One"},
            {"id": "one", "type": "Unsupported", "name": "Duplicate"},
        ],
        "relationships": [
            {
                "id": "edge",
                "source": "one",
                "target": "one",
                "type": "GenericAll",
            }
        ],
    }
    result = validate_json_bytes(json.dumps(invalid).encode(), get_settings())
    codes = {message.code for message in result.messages}
    assert "duplicate_node_id" in codes
    assert "self_loop" in codes
