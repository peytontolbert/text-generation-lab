#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HANDOFF = (
    ROOT
    / "runs/local/artifacts/stage10648_reviewed_v28_harness_handoff_bundle/reviewed_v28_harness_handoff_bundle.json"
)
DEFAULT_RUNTIME_ROOT = ROOT / "runs/local/artifacts/stage10138_canonical_harness_local_runtime"
DEFAULT_OUT_DIR = ROOT / "runs/local/artifacts/stage10650_reviewed_v28_harness_writeback_repair"


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


VALIDATE_AND_WRITE = _load_symbol(
    "stage10650_stage10081_adapter",
    ROOT / "scripts" / "run_stage10081_canonical_harness_backend_adapter.py",
    "validate_and_write",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "cell"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repair reviewed v2.8 harness packet dirs and replay adapter writeback into reserved paths."
    )
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--cell-key", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    handoff = load_json(args.handoff)
    handoff_cells = [row for row in (handoff.get("handoff_cells") or []) if isinstance(row, dict)]
    if args.cell_key:
        handoff_cells = [row for row in handoff_cells if str(row.get("cell_key") or "") == args.cell_key]

    created_packet_dirs: list[str] = []
    repaired_runs: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for cell in handoff_cells:
        cell_key = str(cell.get("cell_key") or "")
        artifact_paths = dict(cell.get("artifact_paths") or {})
        packet_dir = ROOT / str(artifact_paths.get("packet_dir") or "")
        adapter_payload = args.runtime_root / slug(cell_key) / "adapter_payload.json"

        if not packet_dir.exists() and not args.dry_run:
            packet_dir.mkdir(parents=True, exist_ok=True)
            created_packet_dirs.append(display(packet_dir))
        elif packet_dir.exists():
            created_packet_dirs.append(display(packet_dir))

        if not adapter_payload.exists():
            failures.append(
                {
                    "cell_key": cell_key,
                    "reason": "missing_adapter_payload",
                    "adapter_payload": display(adapter_payload),
                }
            )
            continue

        try:
            result = VALIDATE_AND_WRITE(
                handoff_path=args.handoff,
                payload_path=adapter_payload,
                cell_key=cell_key,
                dry_run=args.dry_run,
            )
        except Exception as exc:  # noqa: BLE001
            failures.append(
                {
                    "cell_key": cell_key,
                    "reason": "writeback_failed",
                    "adapter_payload": display(adapter_payload),
                    "error": str(exc),
                }
            )
            continue

        repaired_runs.append(
            {
                "cell_key": cell_key,
                "adapter_payload": display(adapter_payload),
                "result": result,
            }
        )

    summary = {
        "stage": 10650,
        "stage_name": "stage10650_reviewed_v28_harness_writeback_repair",
        "passed": not failures,
        "dry_run": args.dry_run,
        "handoff": display(args.handoff),
        "runtime_root": display(args.runtime_root),
        "metrics": {
            "requested_cells": len(handoff_cells),
            "created_or_existing_packet_dirs": len(created_packet_dirs),
            "repaired_runs": len(repaired_runs),
            "failed_runs": len(failures),
        },
        "created_or_existing_packet_dirs": sorted(set(created_packet_dirs)),
        "repaired_runs": repaired_runs,
        "failures": failures,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out_dir / "reviewed_v28_harness_writeback_repair.json", summary)
    print(args.out_dir / "reviewed_v28_harness_writeback_repair.json")


if __name__ == "__main__":
    main()
