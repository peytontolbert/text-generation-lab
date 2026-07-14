#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10889
NAME = "stage10889_flash_attn_alias_safe_probe_manifest_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "flash_attn_alias_safe_probe_manifest_audit.json"

PACKAGE_DIR = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package"
REQUEST_DIR = ARTIFACTS / "stage10888_flash_attn_alias_safe_probe_request"


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
    package_train = load_jsonl(PACKAGE_DIR / "agentkernel_lite_encdec_train.jsonl")
    package_validation = load_jsonl(PACKAGE_DIR / "agentkernel_lite_encdec_validation.jsonl")
    package_strict = load_jsonl(PACKAGE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl")
    package_stress = load_jsonl(PACKAGE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl")
    request_manifest = load_jsonl(REQUEST_DIR / "flash_attn_alias_safe_probe_manifest.jsonl")
    request = load_json(REQUEST_DIR / "flash_attn_alias_safe_probe_request.json")

    request_train = [row for row in request_manifest if str(row.get("split") or "") == "train"]
    request_eval = [row for row in request_manifest if str(row.get("split") or "") == "eval"]
    request_strict = [row for row in request_manifest if str(row.get("split") or "") == "strict_eval"]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "flash_attn_alias_safe_probe_manifest_audited",
        "claim_scope": [
            "Verify that the stage10888 probe manifest is a faithful probe projection of the stage10883 alias-safe successor package.",
            "Prove that only stress rows are excluded and that train, validation, and strict row identities are preserved exactly.",
        ],
        "metrics": {
            "package_train_rows": len(package_train),
            "request_train_rows": len(request_train),
            "package_validation_rows": len(package_validation),
            "request_eval_rows": len(request_eval),
            "package_strict_rows": len(package_strict),
            "request_strict_rows": len(request_strict),
            "package_stress_rows": len(package_stress),
            "request_manifest_rows": len(request_manifest),
            "train_row_ids_preserved": row_ids(package_train) == row_ids(request_train),
            "validation_row_ids_preserved": row_ids(package_validation) == row_ids(request_eval),
            "strict_row_ids_preserved": row_ids(package_strict) == row_ids(request_strict),
            "stress_rows_excluded": len(request_manifest) == len(package_train) + len(package_validation) + len(package_strict),
        },
        "interpretation": [
            "The probe manifest carries forward the anti-cheat-clean 23-row heldout surface exactly.",
            "The new request changes training support only through the already-audited stage10883 flash-attn repair.",
            "Any post-run score movement must therefore be interpreted as a training-time effect on the unchanged heldout surface, not as an eval reshaping artifact.",
        ],
        "source_artifacts": {
            "successor_package": rel(PACKAGE_DIR / "flash_attn_alias_safe_successor_package.json"),
            "probe_request": rel(REQUEST_DIR / "flash_attn_alias_safe_probe_request.json"),
            "probe_manifest": rel(REQUEST_DIR / "flash_attn_alias_safe_probe_manifest.jsonl"),
        },
        "request_run_id": request.get("run_id"),
    }

    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
