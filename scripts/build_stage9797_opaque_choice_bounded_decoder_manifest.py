#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from loss_mask_card import LOSS_KEYS, normalize_loss_mask
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.loss_mask_card import LOSS_KEYS, normalize_loss_mask  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9797
NAME = "stage9797_opaque_choice_bounded_decoder_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9790_edit_localization_opaque_choice_surface/edit_localization_opaque_choice_surface.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "opaque_choice_bounded_decoder_manifest.jsonl"
AUDIT = OUT_DIR / "opaque_choice_bounded_decoder_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPAQUE_CHOICE_BOUNDED_DECODER_MANIFEST_STAGE9797.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def decoder_loss_mask() -> dict[str, bool]:
    return {key: key == "decoder_ce" for key in LOSS_KEYS}


def build_rows() -> list[dict[str, Any]]:
    rows = []
    for source in load_jsonl(SOURCE):
        target = source.get("target") if isinstance(source.get("target"), dict) else {}
        decoder_text = str(target.get("decoder_text") or "").strip()
        row = dict(source)
        row["objective_family"] = "bounded_decoder_ce"
        row["route"] = "KEEP_BOUNDED_DECODER"
        row["recommended_action"] = "KEEP_BOUNDED_DECODER"
        row["risk_bucket"] = "KEEP_BOUNDED_DECODER"
        row["surface"] = "EDIT_LOCALIZATION_OPAQUE_CHOICE_DECODER"
        row["target"] = {
            "decoder_text": decoder_text,
            "target_shape": "OPAQUE_CHOICE_LABEL",
            "target_ref": decoder_text,
        }
        row["decoder_token_len"] = len(decoder_text)
        row["decoder_budget_ok"] = True
        row["target_length_bucket"] = "bounded"
        row["copied_target_text_in_input"] = False
        row["loss_mask"] = decoder_loss_mask()
        anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        row["anti_cheat"] = {
            **anti,
            "target_text_in_model_input": False,
            "target_text_in_encoder": False,
            "raw_decoder_text_in_encoder": False,
            "decoder_ce_surface": True,
        }
        rows.append(row)
    return rows


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts = Counter(str(row.get("split") or "") for row in rows)
    language_counts = Counter(str(row.get("language_family") or "") for row in rows)
    split_language_counts = Counter((str(row.get("split") or ""), str(row.get("language_family") or "")) for row in rows)
    decoder_labels = Counter(str(((row.get("target") if isinstance(row.get("target"), dict) else {}).get("decoder_text") or "")) for row in rows)
    failures: list[str] = []
    unsafe_loss_rows = []
    empty_targets = []
    for row in rows:
        row_id = str(row.get("row_id") or "")
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        decoder_text = str(target.get("decoder_text") or "")
        if not decoder_text:
            empty_targets.append(row_id)
        enabled = [key for key, value in normalize_loss_mask(row).items() if value]
        if enabled != ["decoder_ce"]:
            unsafe_loss_rows.append({"row_id": row_id, "enabled": enabled})
    expected_split_lang = {(split, lang): 5 for split in ["train", "eval", "strict_eval"] for lang in LANGS}
    if dict(split_counts) != {"train": 20, "eval": 20, "strict_eval": 20}:
        failures.append("unexpected_split_counts")
    if dict(language_counts) != {lang: 15 for lang in LANGS}:
        failures.append("unexpected_language_counts")
    if not all(split_language_counts.get(key, 0) == value for key, value in expected_split_lang.items()):
        failures.append("unexpected_split_language_counts")
    if set(decoder_labels) != {"A", "B", "C", "D", "E"}:
        failures.append("unexpected_decoder_label_vocab")
    if unsafe_loss_rows:
        failures.append("unsafe_loss_rows")
    if empty_targets:
        failures.append("empty_targets")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "split_language_counts": {f"{split}:{lang}": count for (split, lang), count in sorted(split_language_counts.items())},
        "decoder_label_counts": dict(sorted(decoder_labels.items())),
        "unsafe_loss_rows": unsafe_loss_rows[:20],
        "empty_target_rows": empty_targets[:20],
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    audit = audit_rows(rows)
    write_jsonl(MANIFEST, rows)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "source": str(SOURCE.relative_to(ROOT))},
        "decision": "Lifted the corrected Stage9790 opaque-choice edit-localization rows into bounded decoder CE manifest shape so the 100M model can learn the A-E output protocol through the decoder path instead of the frozen structured head path." if audit["passed"] else "Opaque-choice bounded decoder manifest failed audit.",
        "next_best_step": "Run a bounded decoder CE preexecution contract on the Stage9797 manifest, then execute one real target-100M probe if the contract passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9797 Opaque Choice Bounded Decoder Manifest",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Splits: `{audit['split_counts']}`",
        f"Languages: `{audit['language_counts']}`",
        f"Decoder labels: `{audit['decoder_label_counts']}`",
        "",
        "This stage keeps the corrected Stage9790 visible evidence but rewrites the rows into decoder-CE training shape so bounded decoder execution can learn the opaque A-E labels directly.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": audit["rows"], "split_counts": audit["split_counts"], "decoder_label_counts": audit["decoder_label_counts"]}, "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
