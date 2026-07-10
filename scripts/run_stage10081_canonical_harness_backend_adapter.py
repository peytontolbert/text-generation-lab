#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HANDOFF = ROOT / "runs/local/artifacts/stage10081_canonical_harness_backend_handoff_bundle/canonical_harness_backend_handoff_bundle.json"
MACHINE_ARTIFACTS = [
    "harness_run_id",
    "same_task_pack_as_gemma12b",
    "tool_trace_spans",
    "verifier_results",
    "patch_minimality_or_abstain_scores",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and write canonical full-product harness runtime artifacts only to the reserved stage10081 packet paths."
    )
    parser.add_argument("payload", type=Path, help="JSON payload emitted by the external backend adapter.")
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF, help="Canonical handoff bundle to validate against.")
    parser.add_argument("--cell-key", default=None, help="Optional single cell to validate/write.")
    parser.add_argument("--dry-run", action="store_true", help="Validate only; do not write artifacts.")
    return parser.parse_args()


def _cell_index(handoff: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = [row for row in (handoff.get("handoff_cells") or []) if isinstance(row, dict)]
    return {str(row.get("cell_key") or ""): row for row in rows}


def _selected_runs(payload: dict[str, Any], *, cell_key: str | None) -> list[dict[str, Any]]:
    rows = [row for row in (payload.get("runs") or []) if isinstance(row, dict)]
    if cell_key:
        rows = [row for row in rows if str(row.get("cell_key") or "") == cell_key]
    return rows


def _ensure_inside_packet_dir(packet_dir: Path, artifact_path: Path) -> None:
    packet_real = packet_dir.resolve()
    artifact_real = artifact_path.resolve()
    if packet_real not in artifact_real.parents and artifact_real != packet_real:
        raise ValueError(f"artifact path escapes packet dir: {artifact_path}")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def _normalize_run(run: dict[str, Any]) -> dict[str, Any]:
    if not run.get("harness_run_id"):
        raise ValueError(f"missing harness_run_id for {run.get('cell_key')}")
    same_pack = run.get("same_task_pack_as_gemma12b")
    traces = run.get("tool_trace_spans")
    verifier = run.get("verifier_results")
    patch_scores = run.get("patch_minimality_or_abstain_scores")
    if not isinstance(same_pack, dict):
        raise ValueError(f"same_task_pack_as_gemma12b must be an object for {run.get('cell_key')}")
    if not isinstance(traces, list):
        raise ValueError(f"tool_trace_spans must be a list for {run.get('cell_key')}")
    if not isinstance(verifier, dict):
        raise ValueError(f"verifier_results must be an object for {run.get('cell_key')}")
    if not isinstance(patch_scores, dict):
        raise ValueError(f"patch_minimality_or_abstain_scores must be an object for {run.get('cell_key')}")
    return {
        "harness_run_id": str(run["harness_run_id"]),
        "same_task_pack_as_gemma12b": same_pack,
        "tool_trace_spans": traces,
        "verifier_results": verifier,
        "patch_minimality_or_abstain_scores": patch_scores,
    }


def validate_and_write(*, handoff_path: Path, payload_path: Path, cell_key: str | None, dry_run: bool) -> dict[str, Any]:
    handoff = load_json(handoff_path)
    payload = load_json(payload_path)
    cell_index = _cell_index(handoff)
    runs = _selected_runs(payload, cell_key=cell_key)
    if not runs:
        raise ValueError("payload contains no matching runs")

    failures: list[str] = []
    written: list[dict[str, Any]] = []
    for run in runs:
        current_key = str(run.get("cell_key") or "")
        cell = cell_index.get(current_key)
        if cell is None:
            failures.append(f"unknown_cell_key::{current_key}")
            continue
        artifact_paths = dict(cell.get("artifact_paths") or {})
        packet_dir = ROOT / str(artifact_paths.get("packet_dir") or "")
        if not packet_dir.exists():
            failures.append(f"missing_packet_dir::{current_key}")
            continue
        normalized = _normalize_run(run)
        resolved_targets = {}
        for artifact_name in MACHINE_ARTIFACTS:
            rel = artifact_paths.get(artifact_name)
            if not rel:
                failures.append(f"missing_reserved_path::{current_key}::{artifact_name}")
                continue
            target = ROOT / str(rel)
            _ensure_inside_packet_dir(packet_dir, target)
            resolved_targets[artifact_name] = target
        if failures:
            continue
        if not dry_run:
            resolved_targets["harness_run_id"].write_text(normalized["harness_run_id"] + "\n", encoding="utf-8")
            _write_json(resolved_targets["same_task_pack_as_gemma12b"], normalized["same_task_pack_as_gemma12b"])
            _write_jsonl(resolved_targets["tool_trace_spans"], normalized["tool_trace_spans"])
            _write_json(resolved_targets["verifier_results"], normalized["verifier_results"])
            _write_json(resolved_targets["patch_minimality_or_abstain_scores"], normalized["patch_minimality_or_abstain_scores"])
        written.append(
            {
                "cell_key": current_key,
                "packet_dir": display(packet_dir),
                "artifact_paths": {name: display(path) for name, path in resolved_targets.items()},
                "dry_run": dry_run,
            }
        )

    return {
        "handoff": display(handoff_path),
        "payload": display(payload_path),
        "selected_cell_key": cell_key,
        "dry_run": dry_run,
        "validated_runs": len(written),
        "written_runs": len(written) if not dry_run else 0,
        "machine_artifacts_only": MACHINE_ARTIFACTS,
        "failures": failures,
        "writes": written,
    }


def main() -> None:
    args = parse_args()
    result = validate_and_write(
        handoff_path=args.handoff,
        payload_path=args.payload,
        cell_key=args.cell_key,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
