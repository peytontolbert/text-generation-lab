from __future__ import annotations

from typing import Any

from curriculum_compiler import REQUIRED_RECOVERED_GATE_REFERENCES


def default_gate_status(value: bool = False, **overrides: bool) -> dict[str, bool]:
    """Return a complete recovered-gate status card.

    Builders should emit a complete card even when a row is still pending audit.
    Missing keys are intentionally treated as failed by the curriculum compiler,
    so this helper keeps all builders aligned to one gate list.
    """
    status = {key: bool(value) for key in REQUIRED_RECOVERED_GATE_REFERENCES}
    for key, override in overrides.items():
        if key not in status:
            raise KeyError(f"unknown recovered gate: {key}")
        status[key] = bool(override)
    return status


def passed_gate_status(**overrides: bool) -> dict[str, bool]:
    return default_gate_status(True, **overrides)


def failed_gate_names(status: dict[str, Any] | None) -> list[str]:
    if not isinstance(status, dict):
        return list(REQUIRED_RECOVERED_GATE_REFERENCES)
    return [key for key in REQUIRED_RECOVERED_GATE_REFERENCES if status.get(key) is not True]


def has_complete_gate_status(row: dict[str, Any]) -> bool:
    status = row.get("gate_status")
    return isinstance(status, dict) and set(REQUIRED_RECOVERED_GATE_REFERENCES).issubset(status)


def gate_status_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    incomplete = [str(row.get("row_id") or i) for i, row in enumerate(rows) if not has_complete_gate_status(row)]
    failed_counts = {key: 0 for key in REQUIRED_RECOVERED_GATE_REFERENCES}
    for row in rows:
        for key in failed_gate_names(row.get("gate_status")):
            failed_counts[key] += 1
    return {
        "rows": len(rows),
        "required_recovered_gate_references": list(REQUIRED_RECOVERED_GATE_REFERENCES),
        "complete_gate_status_rows": len(rows) - len(incomplete),
        "incomplete_gate_status_rows": len(incomplete),
        "incomplete_gate_status_examples": incomplete[:50],
        "failed_gate_counts": failed_counts,
        "all_rows_have_complete_gate_status": not incomplete,
    }
