from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9013_codex_sessions_no_content_inventory_contract import (  # noqa: E402
    ALLOWED_METADATA_FIELDS,
    AUTHORITY_CLOSED,
    FORBIDDEN_CONTENT_FIELDS,
    FORBIDDEN_OPERATIONS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9013_allows_only_metadata_inventory_fields() -> None:
    card = build_contract(registry())
    assert "relative_path_hash" in ALLOWED_METADATA_FIELDS
    assert "file_size_bytes" in ALLOWED_METADATA_FIELDS
    assert "mtime_utc" in ALLOWED_METADATA_FIELDS
    assert "message_text" in FORBIDDEN_CONTENT_FIELDS
    assert "tool_output_text" in FORBIDDEN_CONTENT_FIELDS
    assert "session_json_payload" in FORBIDDEN_CONTENT_FIELDS
    assert card["metrics"]["allowed_metadata_fields"] >= 7


def test_stage9013_keeps_session_inventory_unexecuted() -> None:
    card = build_contract(registry())
    assert "READ_SESSION_FILE_CONTENT_NOW" in FORBIDDEN_OPERATIONS
    assert "PARSE_SESSION_JSON_NOW" in FORBIDDEN_OPERATIONS
    assert "COPY_SESSION_FILES_NOW" in FORBIDDEN_OPERATIONS
    assert card["metrics"]["session_inventory_authorized_now"] is False
    assert card["metrics"]["session_file_content_read_now"] is False
    assert card["metrics"]["session_json_parsed_now"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9013_validation_rejects_content_or_training_side_effects() -> None:
    assert validate_contract(build_contract(registry())) == []
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["metrics"]["session_json_parsed_now"] = True
    assert "session_json_parsed_now" in validate_contract(unsafe)
