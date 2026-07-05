from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

REQUIRED_TOOL_FIELDS = {"tool_id", "action_type", "permission", "input_schema", "failure_modes"}
VALID_PERMISSIONS = {"read_only", "workspace_write", "runtime_execution", "network", "external_write", "destructive"}
SAFE_FOR_TRAINING_PERMISSIONS = {"read_only", "workspace_write"}


def validate_tool(tool: dict[str, Any]) -> dict[str, Any]:
    tool_id = str(tool.get("tool_id") or tool.get("name") or "unknown_tool")
    missing = sorted(field for field in REQUIRED_TOOL_FIELDS if field not in tool)
    permission = str(tool.get("permission") or "")
    failures: list[str] = []
    if missing:
        failures.append("missing_required_fields")
    if permission not in VALID_PERMISSIONS:
        failures.append("invalid_permission")
    if not isinstance(tool.get("input_schema"), dict):
        failures.append("input_schema_not_object")
    if not isinstance(tool.get("failure_modes"), list) or not tool.get("failure_modes"):
        failures.append("failure_modes_missing")
    if permission in {"network", "external_write", "destructive"} and tool.get("requires_explicit_authority") is not True:
        failures.append("dangerous_permission_without_authority")
    route = "BLOCK_TOOL_REGISTRY_ENTRY" if failures else "PASS_TOOL_REGISTRY_ENTRY"
    return {
        "tool_id": tool_id,
        "action_type": tool.get("action_type"),
        "permission": permission,
        "route": route,
        "safe_for_training_surface": permission in SAFE_FOR_TRAINING_PERMISSIONS and not failures,
        "requires_explicit_authority": bool(tool.get("requires_explicit_authority")),
        "missing_required_fields": missing,
        "failures": failures,
    }


def build_registry(tools: list[dict[str, Any]]) -> dict[str, Any]:
    records = [validate_tool(tool) for tool in tools]
    route_counts = Counter(record["route"] for record in records)
    permission_counts = Counter(record["permission"] for record in records)
    action_counts = Counter(str(record["action_type"]) for record in records)
    return {
        "tools": len(tools),
        "records": records,
        "metrics": {
            "tools": len(tools),
            "passed_tools": route_counts.get("PASS_TOOL_REGISTRY_ENTRY", 0),
            "blocked_tools": route_counts.get("BLOCK_TOOL_REGISTRY_ENTRY", 0),
            "safe_for_training_surface": sum(int(record["safe_for_training_surface"]) for record in records),
            "route_counts": dict(route_counts),
            "permission_counts": dict(permission_counts),
            "action_counts": dict(action_counts),
        },
    }


def allowed_actions_for_training(tools: list[dict[str, Any]]) -> list[str]:
    return sorted(record["tool_id"] for record in build_registry(tools)["records"] if record["safe_for_training_surface"])


def read_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        data = json.loads(stripped)
        return data if isinstance(data, list) else []
    rows = []
    for line in text.splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a typed tool/action registry for observe-orient-act training surfaces.")
    parser.add_argument("tools", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    card = build_registry(read_json_or_jsonl(args.tools))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
