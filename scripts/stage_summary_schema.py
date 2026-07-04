from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json
import re

AUTHORITY_KEYS = (
    "model_execution_authorized_next",
    "decoder_ce_training_authorized_next",
    "runtime_authorized",
    "source_emission_authorized",
    "body_emission_authorized",
    "gemma_execution_authorized_next",
    "harness_execution_authorized_next",
    "scoring_authorized_next",
    "controller_complete_merge_authorized_next",
    "promotion_ready",
)

_STAGE_RE = re.compile(r"stage(\d+)")


class StageSummaryError(ValueError):
    pass


def closed_authority() -> dict[str, bool]:
    return {key: False for key in AUTHORITY_KEYS}


def stage_from_name(path_or_name: str) -> int | None:
    m = _STAGE_RE.search(str(path_or_name))
    return int(m.group(1)) if m else None


def normalize_authority(payload: dict[str, Any]) -> dict[str, bool]:
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    authority = payload.get("authority") if isinstance(payload.get("authority"), dict) else {}
    merged = {**decision, **authority, **payload}
    return {key: bool(merged.get(key, False)) for key in AUTHORITY_KEYS}


def validate_stage_summary(payload: dict[str, Any], *, require_closed: bool = False) -> list[str]:
    errors: list[str] = []
    stage = payload.get("stage")
    if not isinstance(stage, int):
        errors.append("stage must be an integer")
    name = payload.get("stage_name") or payload.get("name")
    if not isinstance(name, str) or not name:
        errors.append("stage_name/name must be a non-empty string")
    if "passed" not in payload or not isinstance(payload.get("passed"), bool):
        errors.append("passed must be present as a boolean")
    auth = normalize_authority(payload)
    missing = [key for key in AUTHORITY_KEYS if key not in auth]
    if missing:
        errors.append(f"missing authority keys: {missing}")
    if require_closed:
        open_keys = [key for key, value in auth.items() if value]
        if open_keys:
            errors.append(f"authority must be closed, open keys: {open_keys}")
    return errors


def require_valid_stage_summary(payload: dict[str, Any], *, require_closed: bool = False) -> None:
    errors = validate_stage_summary(payload, require_closed=require_closed)
    if errors:
        raise StageSummaryError("; ".join(errors))


def make_summary(
    *,
    stage: int,
    stage_name: str,
    passed: bool,
    next_best_step: str,
    metrics: dict[str, Any] | None = None,
    gates: dict[str, bool] | None = None,
    authority: dict[str, bool] | None = None,
    reconstructed: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    auth = closed_authority()
    if authority:
        auth.update({key: bool(authority.get(key, False)) for key in AUTHORITY_KEYS if key in authority})
    payload = {
        "stage": stage,
        "stage_name": stage_name,
        "passed": bool(passed),
        "next_best_step": next_best_step,
        "metrics": metrics or {},
        "gates": gates or {},
        "authority": auth,
        "reconstructed": bool(reconstructed),
    }
    if notes:
        payload["notes"] = notes
    require_valid_stage_summary(payload)
    return payload


def read_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise StageSummaryError(f"summary is not an object: {path}")
    if "stage" not in payload:
        stage = stage_from_name(path.name)
        if stage is not None:
            payload["stage"] = stage
    if "stage_name" not in payload and "name" not in payload:
        payload["stage_name"] = path.stem
    if "authority" not in payload:
        payload["authority"] = normalize_authority(payload)
    return payload


def write_summary(path: Path, payload: dict[str, Any], *, require_closed: bool = False) -> None:
    require_valid_stage_summary(payload, require_closed=require_closed)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
