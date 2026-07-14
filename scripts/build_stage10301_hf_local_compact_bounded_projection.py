#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10301
NAME = "stage10301_hf_local_compact_bounded_projection"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_PATH = OUT_DIR / "hf_local_compact_bounded_projection.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
SOURCE = ROOT / (
    "runs/local/artifacts/"
    "stage10300_hf_local_python_replenishment_bundle/"
    "hf_local_python_replenishment_admitted_manifest.json"
)


def _load_module(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


PROJECTION = _load_module(
    "stage10301_stage10143_projection",
    ROOT / "scripts" / "build_stage10143_compact_bounded_bundle_projection.py",
)


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = PROJECTION.build_payload(SOURCE)
    payload["stage"] = STAGE
    payload["stage_name"] = NAME
    payload["source"] = display(SOURCE)
    payload["decision"] = (
        "Projected the refreshed admitted manifest that includes the repaired hf_local Python replenishment bundle into compact bounded rows. "
        "Use this projection as the row source for the next bounded support-package splice rather than reusing the older thin successor packet."
    )
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "stage_name": NAME,
                "passed": payload["passed"],
                "payload": display(OUT_PATH),
                "metrics": payload["metrics"],
                "next_best_step": "Splice the new hf_local-derived compact bounded rows into a narrow support package and keep unsupported agentkernel roots excluded.",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": payload["passed"],
                "payload": display(OUT_PATH),
                "metrics": payload["metrics"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
