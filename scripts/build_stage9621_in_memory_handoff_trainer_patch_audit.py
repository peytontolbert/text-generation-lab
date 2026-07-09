#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9621
NAME = "stage9621_in_memory_handoff_trainer_patch_audit"
TRAINING_LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "in_memory_handoff_trainer_patch_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "IN_MEMORY_HANDOFF_TRAINER_PATCH_AUDIT_STAGE9621.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = TRAINING_LOOP.read_text(encoding="utf-8")
    checks = {
        "denoise_signature_has_model_override": "model_override: torch.nn.Module | None = None" in text[text.index("def run_denoise_repair_probe") : text.index("def run_structured_aux_probe")],
        "denoise_signature_has_tokenizer_override": "tokenizer_override: Any | None = None" in text[text.index("def run_denoise_repair_probe") : text.index("def run_structured_aux_probe")],
        "denoise_uses_tokenizer_override": "tokenizer = tokenizer_override if tokenizer_override is not None else load_tokenizer" in text[text.index("def run_denoise_repair_probe") : text.index("def run_structured_aux_probe")],
        "denoise_uses_model_override": "if model_override is None:" in text[text.index("def run_denoise_repair_probe") : text.index("def run_structured_aux_probe")],
        "denoise_returns_runtime_state": 'result["_runtime_model"] = model' in text[text.index("def run_denoise_repair_probe") : text.index("def run_structured_aux_probe")],
        "two_phase_passes_model_override": "model_override=model" in text[text.index("def run_two_phase_suffix_denoise_reconnect_probe") :],
        "two_phase_passes_tokenizer_override": "tokenizer_override=tokenizer" in text[text.index("def run_two_phase_suffix_denoise_reconnect_probe") :],
    }
    failures = [name for name, passed in checks.items() if not passed]
    audit = {
        "passed": not failures,
        "failures": failures,
        "checks": checks,
        "decision": "Trainer handoff now has the runtime-state plumbing needed for true in-memory denoise reuse. Prior two-phase quality probes should be treated as pre-patch evidence and rerun before using in-memory transfer claims.",
        "invalidated_claims": [
            "Stage9615 and Stage9619 quality measurements remain useful as standalone local objective evidence.",
            "Stage9615 and Stage9619 model_reused_in_memory_between_phases claims require rerun under the patched trainer before being used as evidence.",
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Rerun a contract-only two-phase preflight under the patched trainer, then design Stage9622 tri-phase suffix-choice -> phrase warm-up -> full residual reconnect."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"],
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9621 In-Memory Handoff Trainer Patch Audit",
                "",
                f"Passed: `{audit['passed']}`",
                "",
                "The denoise probe now honors `model_override` / `tokenizer_override` and can return runtime state. This repairs the trainer path needed for true in-memory staged denoise curricula.",
                "",
                "Prior Stage9615/9619 local objective results are still useful, but their in-memory reuse claims must be rerun under the patched trainer before they are used as transfer evidence.",
                "",
                "Authority remains closed: no decoder CE, runtime, Gemma, harness, checkpoint export, or promotion.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
