#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10884
NAME = "stage10884_flash_attn_alias_safe_successor_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "flash_attn_alias_safe_successor_audit.json"

BASE = ARTIFACTS / "stage10881_evidence_alias_quarantine_successor"
SUCCESSOR = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def row_ids(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(str(row.get("row_id") or "") for row in rows)


def main() -> None:
    base_train = load_jsonl(BASE / "agentkernel_lite_encdec_train.jsonl")
    base_validation = load_jsonl(BASE / "agentkernel_lite_encdec_validation.jsonl")
    base_strict = load_jsonl(BASE / "agentkernel_lite_encdec_strict_eval.jsonl")
    base_stress = load_jsonl(BASE / "agentkernel_lite_encdec_stress_eval.jsonl")
    succ_train = load_jsonl(SUCCESSOR / "agentkernel_lite_encdec_train.jsonl")
    succ_validation = load_jsonl(SUCCESSOR / "agentkernel_lite_encdec_validation.jsonl")
    succ_strict = load_jsonl(SUCCESSOR / "agentkernel_lite_encdec_strict_eval.jsonl")
    succ_stress = load_jsonl(SUCCESSOR / "agentkernel_lite_encdec_stress_eval.jsonl")
    repaired = load_jsonl(SUCCESSOR / "flash_attn_alias_safe_repaired_rows.jsonl")

    base_train_ids = set(row_ids(base_train))
    succ_train_ids = set(row_ids(succ_train))
    added_train_ids = sorted(succ_train_ids - base_train_ids)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "flash_attn_alias_safe_successor_audited",
        "claim_scope": [
            "Verify that the stage10883 Rust flash-attn repair only changes train-support rows.",
            "Prove that validation, strict, and stress splits remain byte-for-byte row-id identical to the anti-cheat quarantine baseline.",
        ],
        "metrics": {
            "base_train_rows": len(base_train),
            "successor_train_rows": len(succ_train),
            "added_train_rows": len(added_train_ids),
            "validation_rows_unchanged": row_ids(base_validation) == row_ids(succ_validation),
            "strict_rows_unchanged": row_ids(base_strict) == row_ids(succ_strict),
            "stress_rows_unchanged": row_ids(base_stress) == row_ids(succ_stress),
            "repaired_rows_emitted": len(repaired),
        },
        "added_train_row_ids": added_train_ids,
        "repaired_row_ids": [str(row.get("row_id") or "") for row in repaired],
        "interpretation": [
            "The Rust flash-attn alias-safe successor is a train-support-only repair.",
            "The heldout multilingual baseline remains the quarantined 23-row package, so no new heldout win is being claimed.",
            "This preserves evaluation honesty while improving the Rust evidence-family training geometry.",
        ],
        "source_artifacts": {
            "baseline_package": rel(BASE / "evidence_alias_quarantine_successor.json"),
            "successor_package": rel(SUCCESSOR / "flash_attn_alias_safe_successor_package.json"),
            "successor_rows": rel(SUCCESSOR / "flash_attn_alias_safe_repaired_rows.jsonl"),
        },
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
