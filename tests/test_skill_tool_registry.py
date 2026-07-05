from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from skill_tool_registry import allowed_actions_for_training, build_registry, validate_tool


def read_tool() -> dict:
    return {"tool_id": "read_file", "action_type": "observe", "permission": "read_only", "input_schema": {"path": "str"}, "failure_modes": ["missing_file"]}


def test_valid_read_tool_passes() -> None:
    record = validate_tool(read_tool())
    assert record["route"] == "PASS_TOOL_REGISTRY_ENTRY"
    assert record["safe_for_training_surface"] is True


def test_blocks_missing_schema() -> None:
    tool = read_tool()
    tool.pop("input_schema")
    record = validate_tool(tool)
    assert record["route"] == "BLOCK_TOOL_REGISTRY_ENTRY"
    assert "missing_required_fields" in record["failures"]


def test_blocks_dangerous_without_authority() -> None:
    tool = {"tool_id": "rm", "action_type": "act", "permission": "destructive", "input_schema": {"path": "str"}, "failure_modes": ["data_loss"]}
    record = validate_tool(tool)
    assert "dangerous_permission_without_authority" in record["failures"]


def test_dangerous_with_authority_still_not_safe_training_surface() -> None:
    tool = {"tool_id": "network_fetch", "action_type": "observe", "permission": "network", "input_schema": {"url": "str"}, "failure_modes": ["timeout"], "requires_explicit_authority": True}
    record = validate_tool(tool)
    assert record["route"] == "PASS_TOOL_REGISTRY_ENTRY"
    assert record["safe_for_training_surface"] is False


def test_build_registry_counts() -> None:
    card = build_registry([read_tool(), {"tool_id": "bad", "action_type": "act", "permission": "nope", "input_schema": {}, "failure_modes": ["x"]}])
    assert card["metrics"]["passed_tools"] == 1
    assert card["metrics"]["blocked_tools"] == 1


def test_allowed_actions_for_training_only_safe() -> None:
    tools = [read_tool(), {"tool_id": "net", "action_type": "observe", "permission": "network", "input_schema": {}, "failure_modes": ["timeout"], "requires_explicit_authority": True}]
    assert allowed_actions_for_training(tools) == ["read_file"]
