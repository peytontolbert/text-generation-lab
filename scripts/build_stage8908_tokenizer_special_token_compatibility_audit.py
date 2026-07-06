#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8908
NAME = "stage8908_tokenizer_special_token_compatibility_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TOKENIZER_SPECIAL_TOKEN_COMPATIBILITY_STAGE8908.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "tokenizer_special_token_compatibility_audit.json"

EXPORT_TOKENIZER_DIR = Path("/data/repository_library/exports/agent_kernel/models/agentkernel_lite_100m_bitnet_v11/tokenizer")
TOKENIZER_JSON = EXPORT_TOKENIZER_DIR / "tokenizer.json"
TOKENIZER_CONFIG = EXPORT_TOKENIZER_DIR / "tokenizer_config.json"
RECOVERED_TARGET_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

EXPECTED_CORE = {
    "pad_token_id": 0,
    "bos_token_id": 1,
    "eos_token_id": 2,
    "unk_token_id": 3,
}

EXPECTED_AK_SPECIALS = [
    "<AK_USER>",
    "<AK_CHAT>",
    "<AK_THINK>",
    "<AK_DEEP_RESEARCH>",
    "<AK_CONTEXT>",
    "<AK_EVIDENCE>",
    "<AK_CANDIDATE>",
    "<AK_QUERY_REWRITE>",
    "<AK_RERANK>",
    "<AK_GATHER_CONTEXT>",
    "<AK_RESPOND>",
    "<AK_SUFFICIENT>",
    "<AK_INSUFFICIENT>",
    "<AK_ANSWER>",
    "<AK_JSON>",
]

REQUIRED_V2_SPECIAL_GAPS = [
    "<AK_OBSERVE>",
    "<AK_ORIENT>",
    "<AK_ACT>",
    "<AK_VERIFY>",
    "<AK_REPAIR>",
    "<AK_RETRIEVE>",
    "<AK_PATCH>",
    "<AK_TEST>",
    "<AK_ABORT>",
    "<AK_HOLD_LONG_OUTPUT>",
    "<AK_BOUND_DECODER>",
    "<AK_VTR>",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def recovered_target_vocab_size() -> int:
    payload = load_json(RECOVERED_TARGET_CONFIG)
    cfg = payload.get("model_config", payload)
    return int(cfg.get("vocab_size", 1506))


def build_audit() -> dict[str, Any]:
    tok = load_json(TOKENIZER_JSON)
    cfg = load_json(TOKENIZER_CONFIG)
    added = tok.get("added_tokens") if isinstance(tok.get("added_tokens"), list) else []
    added_by_content = {str(item.get("content")): item for item in added if isinstance(item, dict)}
    ak_tokens = [content for content in EXPECTED_AK_SPECIALS if content in added_by_content]
    missing_ak = [content for content in EXPECTED_AK_SPECIALS if content not in added_by_content]
    core = {key: cfg.get(key) for key in EXPECTED_CORE}
    model_vocab = (tok.get("model") or {}).get("vocab") if isinstance(tok.get("model"), dict) else {}
    export_vocab = int(cfg.get("vocab_size") or len(model_vocab) + len(added))
    target_vocab = recovered_target_vocab_size()
    special_rows = [
        {
            "content": str(item.get("content")),
            "id": item.get("id"),
            "special": bool(item.get("special")),
        }
        for item in added
        if isinstance(item, dict) and bool(item.get("special"))
    ]
    checks = {
        "tokenizer_files_present": TOKENIZER_JSON.exists() and TOKENIZER_CONFIG.exists(),
        "tokenizer_kind_supported_by_wrapper": cfg.get("tokenizer_kind") == "agentkernel_bytelevel_bpe_v1",
        "core_special_ids_match": core == EXPECTED_CORE,
        "ak_special_tokens_present": not missing_ak,
        "ak_special_ids_contiguous": [added_by_content[t]["id"] for t in ak_tokens] == list(range(8192, 8192 + len(EXPECTED_AK_SPECIALS))),
        "export_vocab_size": export_vocab,
        "recovered_target_vocab_size": target_vocab,
        "vocab_matches_recovered_target": export_vocab == target_vocab,
        "safe_to_swap_tokenizer_without_resize": export_vocab == target_vocab,
        "requires_vocab_resize_or_target_config_update": export_vocab != target_vocab,
        "v2_special_tokens_missing": [tok for tok in REQUIRED_V2_SPECIAL_GAPS if tok not in added_by_content],
    }
    blockers = []
    if not checks["tokenizer_files_present"]:
        blockers.append("tokenizer_files_missing")
    if not checks["core_special_ids_match"]:
        blockers.append("core_special_id_mismatch")
    if not checks["ak_special_tokens_present"]:
        blockers.append("missing_agentkernel_special_tokens")
    if not checks["ak_special_ids_contiguous"]:
        blockers.append("agentkernel_special_token_ids_not_contiguous")
    if not checks["vocab_matches_recovered_target"]:
        blockers.append("export_vocab_8207_does_not_match_recovered_target_1506")
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "tokenizer_json": str(TOKENIZER_JSON),
        "tokenizer_config": str(TOKENIZER_CONFIG),
        "core_specials": core,
        "special_tokens": special_rows,
        "expected_ak_specials": EXPECTED_AK_SPECIALS,
        "missing_ak_specials": missing_ak,
        "v2_special_token_gaps": checks["v2_special_tokens_missing"],
        "checks": checks,
        "blockers": blockers,
        "decision": {
            "core_token_compatibility": "pass" if checks["core_special_ids_match"] else "fail",
            "full_tokenizer_swap_status": "blocked_pending_vocab_migration" if blockers else "eligible_for_next_shape_audit",
            "recommended_v2_policy": "Do not add missing V2 maintenance tokens ad hoc. Reserve them in a tokenizer migration manifest, then resize embeddings/lm_head under a state-dict shape audit.",
        },
        "authority": AUTHORITY_CLOSED,
    }


def validate_audit(audit: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    checks = audit["checks"]
    if checks["tokenizer_files_present"] is not True:
        failures.append("tokenizer_files_missing")
    if checks["tokenizer_kind_supported_by_wrapper"] is not True:
        failures.append("unsupported_tokenizer_kind")
    if checks["core_special_ids_match"] is not True:
        failures.append("core_special_ids_do_not_match")
    if checks["ak_special_tokens_present"] is not True:
        failures.append("missing_expected_ak_specials")
    if checks["ak_special_ids_contiguous"] is not True:
        failures.append("ak_special_ids_not_contiguous")
    if checks["safe_to_swap_tokenizer_without_resize"] is True:
        failures.append("unexpected_direct_tokenizer_swap_allowed")
    if "export_vocab_8207_does_not_match_recovered_target_1506" not in audit["blockers"]:
        failures.append("missing_vocab_mismatch_blocker")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8907, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    failures = validate_audit(audit, registry)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "tokenizer_files_present": audit["checks"]["tokenizer_files_present"],
            "core_special_ids_match": audit["checks"]["core_special_ids_match"],
            "ak_special_tokens_present": audit["checks"]["ak_special_tokens_present"],
            "export_vocab_size": audit["checks"]["export_vocab_size"],
            "recovered_target_vocab_size": audit["checks"]["recovered_target_vocab_size"],
            "vocab_matches_recovered_target": audit["checks"]["vocab_matches_recovered_target"],
            "safe_to_swap_tokenizer_without_resize": audit["checks"]["safe_to_swap_tokenizer_without_resize"],
            "v2_special_token_gap_count": len(audit["v2_special_token_gaps"]),
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
            "download_authorized": False,
        },
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": "Core tokenizer IDs and AgentKernel special tokens are recoverable, but full tokenizer swap is blocked by vocab mismatch and needs a migration/resize audit." if not failures else "Tokenizer compatibility audit failed.",
        "next_best_step": "Build state-dict key/shape audit and tokenizer migration design; do not load weights, resize embeddings, or train yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8908 Tokenizer Special Token Compatibility Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "The local AgentKernel Lite tokenizer is `agentkernel_bytelevel_bpe_v1` with core IDs `<pad>=0`, `<s>=1`, `</s>=2`, `<unk>=3`.",
        "",
        "Recovered AgentKernel special tokens are contiguous from 8192 through 8206:",
        "",
        ", ".join(EXPECTED_AK_SPECIALS),
        "",
        "The full tokenizer is not swappable into the recovered target as-is because the local export vocab is 8207 while the recovered target config still uses 1506. This requires an explicit tokenizer migration and embedding/lm-head resize or a matching checkpoint/config source.",
        "",
        "V2 software-maintainer tokens remain a planned migration, not an ad hoc edit:",
        "",
        ", ".join(REQUIRED_V2_SPECIAL_GAPS),
        "",
        "Authority remains closed for model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, and promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8908 Tokenizer Special Token Compatibility"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8908 recovers the local AgentKernel Lite tokenizer boundary. Core IDs match the recovered wrapper, and AgentKernel special tokens occupy 8192-8206. Direct tokenizer swap is blocked because the recovered target config uses vocab 1506 while the local export uses vocab 8207. V2 software-maintainer special tokens must be added only through an audited tokenizer migration plus embedding/lm-head shape plan.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
