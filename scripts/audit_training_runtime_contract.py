from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from stage_summary_schema import AUTHORITY_KEYS, normalize_authority
from training_runtime_contract import REQUIRED_TELEMETRY


def audit_contract(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    gates: dict[str, bool] = {}

    components = payload.get("components") if isinstance(payload.get("components"), dict) else {}
    status = payload.get("execution_implementation_status") if isinstance(payload.get("execution_implementation_status"), dict) else {}
    telemetry = payload.get("required_telemetry") if isinstance(payload.get("required_telemetry"), list) else []

    required_components = [
        "tokenizer",
        "manifest_dataset",
        "loss_mask_enforcer",
        "bounded_decoder_batcher",
        "model_forward",
        "optimizer_step",
        "telemetry_writer",
        "checkpoint_policy",
    ]
    missing_components = [key for key in required_components if key not in components]
    missing_telemetry = [key for key in REQUIRED_TELEMETRY if key not in telemetry]
    open_auth = [key for key, value in normalize_authority(payload).items() if value]

    gates["required_components_present"] = not missing_components
    gates["required_telemetry_present"] = not missing_telemetry
    gates["authority_closed"] = not open_auth
    gates["checkpoint_export_forbidden"] = status.get("checkpoint_export") == "forbidden"
    gates["model_forward_not_falsely_restored"] = status.get("model_forward") in {"not_restored", "not_reimplemented"}
    gates["optimizer_step_not_falsely_restored"] = status.get("optimizer_step") in {"not_restored", "not_reimplemented"}

    if missing_components:
        errors.append(f"missing components: {missing_components}")
    if missing_telemetry:
        errors.append(f"missing telemetry: {missing_telemetry}")
    if open_auth:
        errors.append(f"authority open: {open_auth}")
    if not gates["checkpoint_export_forbidden"]:
        errors.append("checkpoint export is not forbidden")
    if not gates["model_forward_not_falsely_restored"]:
        errors.append("model_forward is marked restored without implementation audit")
    if not gates["optimizer_step_not_falsely_restored"]:
        errors.append("optimizer_step is marked restored without implementation audit")

    return {
        "passed": not errors,
        "contract": str(path),
        "gates": gates,
        "errors": errors,
        "missing_components": missing_components,
        "missing_telemetry": missing_telemetry,
        "authority": {key: False for key in AUTHORITY_KEYS},
        "next_best_step": "restore telemetry writer, then tiny model forward/backward implementation behind explicit authorization",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit non-executing training runtime contract.")
    parser.add_argument("contract", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    card = audit_contract(args.contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
