from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_TELEMETRY = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_token_loss.jsonl",
    "eos_length_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def emit_contract_telemetry(output_dir: Path, *, run_id: str, mode: str, measured: bool = False) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    marker = output_dir / ".agentkernel_probe_output"
    if not marker.exists():
        marker.write_text(f"run_id={run_id}\nmode={mode}\ntelemetry_only=true\n", encoding="utf-8")
    jsonl_empty = {
        "loss_by_step.jsonl",
        "eval_loss_by_checkpoint.jsonl",
        "row_field_logits.jsonl",
        "row_field_losses.jsonl",
        "row_token_loss.jsonl",
    }
    for name in REQUIRED_TELEMETRY:
        path = output_dir / name
        if name in jsonl_empty:
            write_jsonl(path, [] if not measured else [{"run_id": run_id, "mode": mode, "measured": False, "contract_only": True}])
        elif name == "cleanup_proof.json":
            write_json(
                path,
                {
                    "run_id": run_id,
                    "mode": mode,
                    "cleanup_executed": False,
                    "cleanup_reason": "telemetry contract only",
                    "contract_only": True,
                },
            )
        else:
            write_json(
                path,
                {
                    "run_id": run_id,
                    "mode": mode,
                    "artifact": name,
                    "contract_only": True,
                    "measured": False,
                    "model_execution_attempted": False,
                },
            )
    return {"output_dir": str(output_dir), "required_artifacts": REQUIRED_TELEMETRY, "artifact_count": len(REQUIRED_TELEMETRY)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit training telemetry contract artifacts without model execution.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    card = emit_contract_telemetry(args.output_dir, run_id=args.run_id, mode=args.mode)
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
