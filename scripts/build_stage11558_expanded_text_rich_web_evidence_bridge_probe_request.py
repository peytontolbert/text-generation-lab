#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11558
NAME = "stage11558_expanded_text_rich_web_evidence_bridge_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "text_rich_web_evidence_judgment_bridge_probe_request.json"
MANIFEST = OUT / "text_rich_web_evidence_judgment_bridge_probe_manifest.jsonl"
BRIDGE_ROWS = OUT / "text_rich_web_evidence_judgment_bridge_rows.jsonl"
QUARANTINE = OUT / "text_rich_web_evidence_judgment_quarantine.jsonl"
COMMAND = OUT / "text_rich_web_evidence_judgment_bridge_probe_command.json"
PROBE = ART / "stage11558_expanded_text_rich_web_evidence_bridge_probe/bounded_decoder_probe"
RUNTIME_OUT = ART / "stage11558_expanded_text_rich_web_evidence_bridge_probe/runtime_model"

INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
BASE_MANIFEST = ART / "stage11550_web_root_support_from_stage11507_probe_request/web_root_support_from_stage11507_probe_manifest.jsonl"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
WEB_HELDOUT = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"

ROLE_TO_JUDGMENT = {
    "candidate_change_surface": "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "candidate_change_surface_only": "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "verifier_and_test_constraint": "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "test_assertions_and_predicate_conditions": "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "transition_validation_assertions": "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "stdio_transport_lifecycle_assertions": "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "symptom_or_call_path_analogue": "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "nearby_definition_or_usage_context": "DISTRACTOR_BACKGROUND_CONTEXT",
    "external_analogue_reference": "DISTRACTOR_BACKGROUND_CONTEXT",
    "algorithmic_background_reference": "DISTRACTOR_BACKGROUND_CONTEXT",
    "dependency_or_test_environment_surface": "DISTRACTOR_BACKGROUND_CONTEXT",
    "background_type_shape_only": "DISTRACTOR_BACKGROUND_CONTEXT",
    "config_presence_only": "DISTRACTOR_BACKGROUND_CONTEXT",
    "repo_manager_surface": "DISTRACTOR_BACKGROUND_CONTEXT",
    "repo_metadata_or_config": "DISTRACTOR_BACKGROUND_CONTEXT",
    "repo_metadata_or_runtime_setup": "DISTRACTOR_BACKGROUND_CONTEXT",
    "supporting_secondary_surface": "DISTRACTOR_BACKGROUND_CONTEXT",
    "supporting_public_projection_surface": "DISTRACTOR_BACKGROUND_CONTEXT",
    "abstain_insufficient_evidence": "DISTRACTOR_BACKGROUND_CONTEXT",
    "ABSTAIN_INSUFFICIENT_EVIDENCE": "DISTRACTOR_BACKGROUND_CONTEXT",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def role_key(value: str) -> str:
    raw = str(value).strip()
    if "|" in raw:
        raw = raw.split("|", 1)[0].strip()
    return raw


def normalize_row(row: dict[str, Any], split: str | None = None) -> dict[str, Any]:
    out = dict(row)
    if split is not None:
        out["split"] = split
    out.setdefault("prompt_text", out.get("input_text") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    if not isinstance(out.get("loss_mask"), dict):
        out["loss_mask"] = {"decoder_ce": True}
    out.setdefault("expected_enabled_loss", "decoder_ce")
    standalone = dict(out.get("standalone_projection_source") or {})
    standalone.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = standalone
    if "target" not in out or not isinstance(out.get("target"), dict):
        out["target"] = {
            "decoder_text": out.get("decoder_text"),
            "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text"),
        }
    return out


def bridge_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source = normalize_row(row, "train")
    if str(source.get("task_type") or "") != "evidence_citation":
        return None, {"row_id": source.get("row_id"), "reason": "not_evidence_citation"}
    options = list(((source.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    if len(options) < 2:
        return None, {"row_id": source.get("row_id"), "reason": "too_few_options"}
    if not all(str(option.get("text") or "").strip() for option in options):
        return None, {"row_id": source.get("row_id"), "reason": "not_text_rich"}
    mapped = []
    for option in options:
        key = role_key(str(option.get("value") or ""))
        judgment = ROLE_TO_JUDGMENT.get(key)
        if judgment is None:
            return None, {"row_id": source.get("row_id"), "reason": "unsupported_option_value", "value": key}
        item = dict(option)
        item["value"] = judgment
        mapped.append(item)
    out = dict(source)
    out["row_id"] = f"{source.get('row_id')}::stage11558_judgment_bridge"
    out["task_type"] = "evidence_candidate_judgment"
    out["bounded_choice_target_label"] = str(source.get("bounded_choice_target_label") or source.get("target_text") or "")
    out["target_text"] = out["bounded_choice_target_label"]
    out["decoder_text"] = out["bounded_choice_target_label"]
    out["loss_mask"] = {"decoder_ce": True}
    out["expected_enabled_loss"] = "decoder_ce"
    standalone = dict(out.get("standalone_projection_source") or {})
    standalone["opaque_options"] = mapped
    standalone["stage11558_bridge_source_row_id"] = source.get("row_id")
    standalone["stage11558_bridge_gate"] = "all_supported_text_rich_evidence_roles"
    out["standalone_projection_source"] = standalone
    out["opaque_options"] = mapped
    out["target"] = {
        "decoder_text": out["decoder_text"],
        "bounded_choice_target_label": out["bounded_choice_target_label"],
    }
    text = str(out.get("input_text") or out.get("prompt_text") or "")
    if "Perspective: evidence_citation" in text:
        text = text.replace("Perspective: evidence_citation", "Perspective: evidence_candidate_judgment")
    out["input_text"] = text
    out["prompt_text"] = text
    anti = dict(out.get("anti_cheat") or {})
    anti.update(
        {
            "stage11558_judgment_bridge": True,
            "all_options_text_rich": True,
            "all_option_values_supported_judgment_buckets": True,
            "train_support_only": True,
        }
    )
    out["anti_cheat"] = anti
    return out, None


def root_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("root_id") or row.get("source_bundle_id") or row.get("row_id", "").split("::")[0]) for row in rows}


def main() -> None:
    base_rows = [normalize_row(row) for row in load_jsonl(BASE_MANIFEST)]
    base_train = [row for row in base_rows if row.get("split") == "train"]
    validation = [normalize_row(row, "eval") for row in load_jsonl(FILTERED_VALIDATION)]
    strict = [normalize_row(row, "strict_eval") for row in load_jsonl(FILTERED_STRICT)]
    heldout = load_jsonl(WEB_HELDOUT)
    bridge_rows: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    for row in base_train:
        bridged, blocked = bridge_row(row)
        if bridged is not None:
            bridge_rows.append(bridged)
        elif blocked is not None and blocked.get("reason") != "not_evidence_citation":
            quarantine.append(blocked)
    bridge_roots = root_ids(bridge_rows)
    manifest_rows = bridge_rows + validation + strict
    overlaps = {
        "bridge_vs_validation": sorted(bridge_roots & root_ids(validation)),
        "bridge_vs_strict": sorted(bridge_roots & root_ids(strict)),
        "bridge_vs_web_heldout": sorted(bridge_roots & root_ids(heldout)),
    }
    command = [
        "env",
        "CUDA_VISIBLE_DEVICES=2",
        "NVIDIA_VISIBLE_DEVICES=2",
        "AGENTKERNEL_EVAL_DEVICE=cuda:0",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
        "TMPDIR=/data/tmp",
        "TEMP=/data/tmp",
        "TMP=/data/tmp",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST),
        "--mode",
        "bounded_decoder_ce_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(len(bridge_rows)),
        "--max-eval-rows",
        str(len(validation)),
        "--max-strict-rows",
        str(len(strict)),
        "--max-steps",
        "96",
        "--batch-size",
        "4",
        "--learning-rate",
        "1.2e-6",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.05",
        "--bounded-choice-aux-weight",
        "3.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_evidence_judgment_head",
        "--bounded-decoder-train-sampler",
        "cyclic",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "4.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "8",
        "--max-generation-tokens",
        "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_OUT),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--bounded-choice-contrast-weight",
        "0.0",
        "--bounded-choice-contrast-margin",
        "0.05",
        "--preservation-kl-weight",
        "2.0",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(PROBE),
    ]
    gates = {
        "bridge_rows_present": len(bridge_rows) >= 8,
        "bridge_roots_present": len(bridge_roots) >= 4,
        "no_bridge_eval_strict_or_heldout_root_overlap": all(not values for values in overlaps.values()),
        "all_bridge_rows_judgment_task": all(row.get("task_type") == "evidence_candidate_judgment" for row in bridge_rows),
        "quarantine_only_expected_non_bridge_reasons": all(row.get("reason") in {"not_text_rich", "unsupported_option_value", "too_few_options"} for row in quarantine),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(BRIDGE_ROWS, bridge_rows)
    write_jsonl(QUARANTINE, quarantine)
    write_jsonl(MANIFEST, manifest_rows)
    write_json(COMMAND, {"command": command})
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "text_rich_web_evidence_judgment_bridge_probe_ready" if all(gates.values()) else "text_rich_web_evidence_judgment_bridge_probe_blocked",
        "metrics": {
            "base_train_rows": len(base_train),
            "bridge_rows": len(bridge_rows),
            "bridge_roots": len(bridge_roots),
            "bridge_repo_counts": dict(Counter(str(row.get("repo_family") or "unknown") for row in bridge_rows)),
            "quarantine_reasons": dict(Counter(str(row.get("reason")) for row in quarantine)),
            "validation_rows": len(validation),
            "strict_rows": len(strict),
            "root_overlaps": overlaps,
        },
        "gates": gates,
        "command": command,
        "claim_boundary": [
            "Diagnostic bridge training for text-rich evidence judgment rows only.",
            "This trains the head used by the Stage11554 safe gated policy, not raw evidence_citation rows.",
            "Promotion requires postrun gated audit against old/filtered canaries, residual bank, and Web heldout.",
        ],
        "source_artifacts": {
            "init_runtime": rel(INIT_RUNTIME),
            "base_manifest": rel(BASE_MANIFEST),
            "web_heldout": rel(WEB_HELDOUT),
            "filtered_validation": rel(FILTERED_VALIDATION),
            "filtered_strict": rel(FILTERED_STRICT),
        },
        "outputs": {
            "bridge_rows": rel(BRIDGE_ROWS),
            "quarantine": rel(QUARANTINE),
            "manifest": rel(MANIFEST),
            "command": rel(COMMAND),
            "probe_dir": rel(PROBE),
            "runtime_model": rel(RUNTIME_OUT),
            "summary": rel(SUMMARY),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "passed": summary["passed"], "metrics": summary["metrics"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
