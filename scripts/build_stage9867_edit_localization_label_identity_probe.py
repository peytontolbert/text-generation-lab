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
STAGE = 9867
NAME = "stage9867_edit_localization_label_identity_probe"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9865_edit_localization_collapse_diagnostics.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9865_edit_localization_collapse_diagnostics/edit_localization_position_debiased_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RELABELED_MANIFEST = OUT_DIR / "edit_localization_label_identity_manifest.jsonl"
CARD = OUT_DIR / "edit_localization_label_identity_probe.json"
CANDIDATE = OUT_DIR / "stage9868_edit_localization_label_identity_target_100m_probe_candidate.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EDIT_LOCALIZATION_LABEL_IDENTITY_PROBE_STAGE9867.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LABEL_MAP = {"A": "K", "B": "M", "C": "R", "D": "T", "E": "Z"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def remap_label_text(text: str) -> str:
    stripped = text.strip()
    for src, dst in LABEL_MAP.items():
        if stripped.startswith(f"option {src}:"):
            return stripped.replace(f"option {src}:", f"option {dst}:", 1)
    return text


def remap_row(row: dict[str, Any]) -> dict[str, Any]:
    cloned = json.loads(json.dumps(row))
    for key in ["clean_state", "target"]:
        obj = cloned.get(key)
        if isinstance(obj, dict):
            for field in ["edit_localization", "edit_localization_target", "target_ref", "decoder_text"]:
                if field in obj and str(obj[field]) in LABEL_MAP:
                    obj[field] = LABEL_MAP[str(obj[field])]
    for key in ["edit_localization_target", "edit_localization"]:
        if key in cloned and str(cloned[key]) in LABEL_MAP:
            cloned[key] = LABEL_MAP[str(cloned[key])]
    input_state = cloned.get("input_state") if isinstance(cloned.get("input_state"), dict) else {}
    if "candidate_choices" in input_state and isinstance(input_state["candidate_choices"], list):
        input_state["candidate_choices"] = [remap_label_text(str(choice)) for choice in input_state["candidate_choices"]]
    cloned["input_state"] = input_state
    anti = cloned.get("anti_cheat") if isinstance(cloned.get("anti_cheat"), dict) else {}
    anti["stage9868_label_identity_remap"] = LABEL_MAP
    cloned["anti_cheat"] = anti
    return cloned


def build_command() -> list[str]:
    return [
        "python",
        "legacy_src/scripts/train_agentkernel_lite_encdec.py",
        "--repo-root", str(ROOT),
        "--manifest", str(RELABELED_MANIFEST.relative_to(ROOT)),
        "--mode", "edit_localization_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
        "--tokenizer-json", "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
        "--tokenizer-config", "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
        "--tokenizer-hashlock", "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
        "--max-train-rows", "32",
        "--max-eval-rows", "16",
        "--max-strict-rows", "16",
        "--max-steps", "8",
        "--batch-size", "2",
        "--learning-rate", "5e-5",
        "--max-encoder-tokens", "512",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.0",
        "--structured-aux-weight", "1.0",
        "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save", "1",
        "--output-dir", "runs/local/artifacts/stage9868_edit_localization_label_identity_target_100m_probe/edit_localization_probe",
        "--run-id", "stage9868_edit_localization_label_identity_target_100m_probe",
        "--execution-authorized-for-recovery-probe",
    ]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = read_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9865_not_passed")
    if not rows:
        failures.append("missing_source_rows")
    remapped = [remap_row(row) for row in rows]
    write_jsonl(RELABELED_MANIFEST, remapped)
    target_labels = sorted({str(((row.get("target") or {}).get("edit_localization") or "")) for row in remapped})
    choice_prefixes = sorted({str(choice).split(":",1)[0].strip() for row in remapped for choice in ((row.get("input_state") or {}).get("candidate_choices") or [])})
    if target_labels != sorted(LABEL_MAP.values()):
        failures.append("unexpected_remapped_target_labels")
    if choice_prefixes != [f"option {label}" for label in sorted(LABEL_MAP.values())]:
        failures.append("unexpected_remapped_choice_prefixes")
    candidate = {
        "future_stage": 9868,
        "future_stage_name": "stage9868_edit_localization_label_identity_target_100m_probe",
        "selected_surface": "edit_localization",
        "reason": "Stage9866 ruled out visible option order. Stage9868 keeps the same rows and debiased order but renames the opaque labels themselves to test whether collapse tracks literal label identity or generic class index zero.",
        "command": build_command(),
        "requires_explicit_user_confirmation_before_execution": True,
        "requires_this_stage_passed": True,
        "authority": dict(AUTHORITY_CLOSED),
    }
    CANDIDATE.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "failures": failures,
        "label_map": LABEL_MAP,
        "target_labels": target_labels,
        "choice_prefixes": choice_prefixes,
        "relabeled_manifest": str(RELABELED_MANIFEST.relative_to(ROOT)),
        "next_execution_candidate": str(CANDIDATE.relative_to(ROOT)),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": "Run Stage9868 on the relabeled edit-localization manifest and inspect whether collapse moves from literal label A to the new first vocabulary label K.",
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": True,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {
            "probe_card": str(CARD.relative_to(ROOT)),
            "relabeled_manifest": str(RELABELED_MANIFEST.relative_to(ROOT)),
            "next_execution_candidate": str(CANDIDATE.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "metrics": {
            "label_map": LABEL_MAP,
            "target_labels": target_labels,
            "choice_prefix_count": len(choice_prefixes),
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": card["next_best_step"],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9867 Edit-Localization Label Identity Probe",
            "",
            f"Passed: `{summary['passed']}`",
            f"Label map: `{LABEL_MAP}`",
            "",
            "This stage prepares a label-identity control: the same Stage9866 rows are kept, but the opaque output labels are renamed from A/B/C/D/E to K/M/R/T/Z.",
            "",
            f"Next: {card['next_best_step']}",
            "",
        ]) + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "candidate": str(CANDIDATE.relative_to(ROOT)), "failures": failures}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
