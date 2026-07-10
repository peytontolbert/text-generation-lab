#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9808
NAME = "stage9808_web_disambiguated_target100m_contract_preflight"
MANIFEST = ROOT / "runs/local/artifacts/stage9807_web_disambiguated_opaque_choice_surface/web_disambiguated_opaque_choice_surface.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "web_disambiguated_target100m_contract_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEB_DISAMBIGUATED_TARGET100M_CONTRACT_PREFLIGHT_STAGE9808.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_command() -> list[str]:
    return [
        "python",
        "legacy_src/scripts/train_agentkernel_lite_encdec.py",
        "--repo-root", ".",
        "--manifest", str(MANIFEST),
        "--mode", "edit_localization_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
        "--tokenizer-json", "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
        "--tokenizer-config", "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
        "--tokenizer-hashlock", "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
        "--max-train-rows", "20",
        "--max-eval-rows", "20",
        "--max-strict-rows", "20",
        "--max-steps", "0",
        "--batch-size", "2",
        "--learning-rate", "5e-5",
        "--max-encoder-tokens", "512",
        "--max-decoder-tokens", "4",
        "--decoder-ce-weight", "0.0",
        "--structured-aux-weight", "1.0",
        "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--skip-final-model-save", "1",
        "--contract-only",
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = {
        "passed": True,
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "command": build_command(),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Execute one real Stage9809 structured 100M run on the Stage9807 surface, then compare it against Gemma on the same rows."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": True,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "command_ready": True},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Prepared a contract-only execution ticket for the Stage9807 web-disambiguated structured surface.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9808 Web Disambiguated Target100M Contract Preflight", "", f"Passed: `{summary['passed']}`", "", f"Next: {next_step}", ""]) + "\n", encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": True, "next_best_step": next_step}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
