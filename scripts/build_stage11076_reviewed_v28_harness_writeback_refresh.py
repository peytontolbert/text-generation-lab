#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_stage10081_canonical_harness_backend_adapter import validate_and_write


ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11076
NAME = "stage11076_reviewed_v28_harness_writeback_refresh"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "reviewed_v28_harness_writeback_refresh.json"

HANDOFF = ARTIFACTS / "stage10648_reviewed_v28_harness_handoff_bundle" / "reviewed_v28_harness_handoff_bundle.json"
RUNTIME_ROOT = ARTIFACTS / "stage10138_canonical_harness_local_runtime"
CELL_DIR_NAMES = [
    "reviewed_full_product_harness_c_cpp_maintainer_choice",
    "reviewed_full_product_harness_python_maintainer_choice",
    "reviewed_full_product_harness_rust_maintainer_choice",
    "reviewed_full_product_harness_web_js_ts_html_maintainer_choice",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    handoff = load_json(HANDOFF)
    cell_index = {
        str(row.get("cell_key") or ""): row
        for row in (handoff.get("handoff_cells") or [])
        if isinstance(row, dict)
    }

    results: list[dict[str, Any]] = []
    failures: list[str] = []

    for dir_name in CELL_DIR_NAMES:
        runtime_dir = RUNTIME_ROOT / dir_name
        adapter_payload = runtime_dir / "adapter_payload.json"
        if not adapter_payload.exists():
            failures.append(f"missing_adapter_payload::{dir_name}")
            continue
        payload = load_json(adapter_payload)
        runs = [row for row in (payload.get("runs") or []) if isinstance(row, dict)]
        if len(runs) != 1:
            failures.append(f"unexpected_run_count::{dir_name}::{len(runs)}")
            continue
        run = runs[0]
        cell_key = str(run.get("cell_key") or "")
        packet = cell_index.get(cell_key)
        if packet is None:
            failures.append(f"unknown_cell_key::{cell_key}")
            continue

        writeback = validate_and_write(
            handoff_path=HANDOFF,
            payload_path=adapter_payload,
            cell_key=cell_key,
            dry_run=False,
        )
        writeback_path = runtime_dir / "writeback_result.json"
        write_json(writeback_path, writeback)

        artifact_paths = dict(packet.get("artifact_paths") or {})
        packet_status = {}
        for artifact_name in (
            "harness_run_id",
            "same_task_pack_as_gemma12b",
            "tool_trace_spans",
            "verifier_results",
            "patch_minimality_or_abstain_scores",
        ):
            target = ROOT / str(artifact_paths.get(artifact_name) or "")
            packet_status[artifact_name] = {
                "path": rel(target),
                "exists": target.exists(),
                "size_bytes": target.stat().st_size if target.exists() else 0,
            }

        row = {
            "cell_key": cell_key,
            "runtime_dir": rel(runtime_dir),
            "adapter_payload": rel(adapter_payload),
            "writeback_result": writeback,
            "packet_status": packet_status,
        }
        if writeback.get("failures"):
            failures.extend(f"{cell_key}::{reason}" for reason in writeback.get("failures") or [])
        results.append(row)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not failures,
        "claim_scope": [
            "Replay canonical adapter writeback for the reviewed-v28 full-product harness runtime artifacts.",
            "Verify that the multilingual reviewed-v28 review packets now hold real machine artifacts at the reserved packet paths.",
        ],
        "source_artifacts": {
            "handoff": rel(HANDOFF),
            "runtime_root": rel(RUNTIME_ROOT),
        },
        "metrics": {
            "cells_attempted": len(CELL_DIR_NAMES),
            "cells_completed": sum(1 for row in results if not (row.get("writeback_result") or {}).get("failures")),
            "cells_failed": len(failures),
        },
        "results": results,
        "failures": failures,
        "next_best_step": "If this passes, the reviewed-v28 harness path has real machine artifact writeback and the remaining gap is human/evaluator review rather than runtime capture.",
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
