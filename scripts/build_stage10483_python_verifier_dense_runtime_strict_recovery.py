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

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

STAGE = 10483
NAME = "stage10483_python_verifier_dense_runtime_strict_recovery"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RECOVERY_JSON = OUT_DIR / "python_verifier_dense_runtime_strict_recovery.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10481_python_verifier_dense_probe/runtime_model/runtime_model_bundle.json"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"
PROBE_DIR = ROOT / "runs/local/artifacts/stage10481_python_verifier_dense_probe/bounded_decoder_probe"
STRICT_AUDIT = PROBE_DIR / "bounded_choice_eval_audit_strict_eval.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    model_config = load_json(Path(str(metadata["model_config"])))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer, init_card


def load_rows() -> list[dict[str, Any]]:
    return load_jsonl(STRICT_ROWS)


def main() -> None:
    model, tokenizer, init_card = build_runtime()
    rows = load_rows()
    card = _write_bounded_choice_eval_audit(
        PROBE_DIR,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="strict_eval",
        bounded_choice_aux_source="encoder_option_retrieval",
    )
    recovery = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "recovered_missing_strict_eval_audit_from_saved_runtime",
        "claim_scope": [
            "Recover the missing strict-eval bounded-choice audit for stage10481 from the saved runtime bundle.",
            "Use the same repaired strict overlay and encoder_option_retrieval scorer as the original dense verifier probe request.",
        ],
        "source_artifacts": {
            "runtime_bundle": display(RUNTIME_BUNDLE),
            "strict_rows": display(STRICT_ROWS),
        },
        "runtime_initialization": init_card,
        "strict_rows": len(rows),
        "strict_accuracy": card.get("constrained_choice_top1_accuracy"),
        "strict_audit": display(STRICT_AUDIT),
    }
    write_json(RECOVERY_JSON, recovery)
    write_json(SUMMARY, recovery)
    print(json.dumps(recovery, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
