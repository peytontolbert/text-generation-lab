#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9272
NAME = "stage9272_target_grounded_denoise_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9271_target_100m_denoise_eos_micro_overfit_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9267_repetition_to_denoise_repair_manifest/repetition_to_denoise_repair_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "target_grounded_denoise_manifest.jsonl"
ANCHOR_CARD = OUT_DIR / "target_grounded_anchor_card.json"
AUDIT = OUT_DIR / "target_grounded_denoise_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TARGET_GROUNDED_DENOISE_MANIFEST_STAGE9272.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

AUTHORITY_FALSE = dict(AUTHORITY_CLOSED)
STOPWORDS = {
    "the", "a", "an", "to", "of", "and", "or", "that", "with", "for", "by", "on", "in", "at", "this", "is", "be", "only", "keep", "return", "emit", "select", "choose", "point", "use", "avoid", "do", "not", "value", "step", "current", "target", "should", "remain",
}
OBJECT_KEYWORDS = [
    ("file path", "file_path"),
    ("path reference", "path_reference"),
    ("project path", "project_path"),
    ("module reference", "module_reference"),
    ("dependency handle", "dependency_handle"),
    ("library entry", "library_entry"),
    ("callable endpoint", "callable_endpoint"),
    ("call target", "call_target"),
    ("invocation target", "invocation_target"),
    ("local name", "local_name"),
    ("identifier", "identifier"),
    ("constant", "constant"),
    ("concrete value", "concrete_value"),
]
CONSTRAINT_KEYWORDS = [
    ("bounded decoder", "bounded_decoder"),
    ("not a full patch", "not_full_patch"),
    ("hidden control", "no_hidden_control"),
    ("runtime claims", "no_runtime_claims"),
    ("source bodies", "no_source_bodies"),
    ("unapproved package", "no_unapproved_package"),
    ("whitelist", "whitelist"),
    ("evidence", "evidence_grounded"),
    ("verifier", "verifier_ready"),
    ("hold-or-retrieve", "hold_or_retrieve"),
    ("smallest edit radius", "smallest_edit_radius"),
    ("single localized transition", "single_localized_transition"),
]
FORBIDDEN_TOP_LEVEL = {"source_text", "body", "raw_body", "patch_body", "hidden_eval", "locked_eval", "runtime_output", "gemma_output"}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text)


def content_words(text: str) -> list[str]:
    out: list[str] = []
    for word in words(text):
        low = word.lower()
        if low in STOPWORDS or len(low) < 4:
            continue
        if low not in out:
            out.append(low)
    return out


def anchor_for_target(text: str) -> dict[str, Any]:
    all_words = words(text)
    action = all_words[0].lower() if all_words else "unknown"
    prefix = " ".join(all_words[:2]) if len(all_words) >= 2 else " ".join(all_words)
    lower = text.lower()
    object_kind = "unknown_object"
    for phrase, label in OBJECT_KEYWORDS:
        if phrase in lower:
            object_kind = label
            break
    constraints = [label for phrase, label in CONSTRAINT_KEYWORDS if phrase in lower][:4]
    keywords = [word for word in content_words(text) if word not in {action, object_kind}][:4]
    return {
        "target_action_verb": action,
        "target_prefix_anchor_2": prefix,
        "target_object_kind": object_kind,
        "target_constraint_bits": constraints,
        "target_anchor_keywords": keywords,
        "target_anchor_word_count": len(words(prefix)) + len(keywords) + len(constraints) + 2,
        "target_text_sha256": sha(text),
    }


def visible_projection(row: dict[str, Any]) -> str:
    payload = {
        "row_id": row.get("row_id"),
        "source_row_id": row.get("source_row_id"),
        "split": row.get("split"),
        "language_family": row.get("language_family"),
        "route": row.get("route"),
        "objective_family": row.get("objective_family"),
        "repair_task_type": row.get("repair_task_type"),
        "corrupted_output": row.get("corrupted_output"),
        "input_state": row.get("input_state"),
        "model_input": row.get("model_input"),
        "loss_mask": row.get("loss_mask"),
    }
    return json.dumps(payload, sort_keys=True)


def build_rows() -> list[dict[str, Any]]:
    rows = []
    for source in load_jsonl(SOURCE_MANIFEST):
        target = str((source.get("target") or {}).get("decoder_text") or source.get("clean_target") or "")
        anchor = anchor_for_target(target)
        row = dict(source)
        row["row_id"] = str(source.get("row_id", "row")).replace("stage9267_", "stage9272_grounded_")
        row["source_stage"] = 9272
        row["source_manifest_stage"] = 9267
        row["source_repair_row_id"] = source.get("row_id")
        row["objective_family"] = "target_grounded_bounded_decoder_output_repair"
        row["repair_task_type"] = f"target_grounded_{source.get('repair_task_type', 'denoise_repair')}"
        state = dict(source.get("input_state") if isinstance(source.get("input_state"), dict) else {})
        state.update(anchor)
        row["input_state"] = state
        row["model_input"] = {
            "target_grounding_mode": "minimal_anchor_v1",
            "anchor_prefix_tokens": anchor["target_prefix_anchor_2"],
            "anchor_object_kind": anchor["target_object_kind"],
            "anchor_constraints": anchor["target_constraint_bits"],
            "anchor_keywords": anchor["target_anchor_keywords"],
        }
        row["anti_cheat"] = {
            "full_target_text_in_model_visible_fields": False,
            "target_text_hash_only_plus_minimal_anchors": True,
            "max_anchor_keywords": 4,
            "max_prefix_anchor_words": 2,
            "decoder_ce_closed": True,
            "runtime_closed": True,
        }
        row["loss_mask"] = {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False}
        row["authority"] = AUTHORITY_FALSE
        rows.append(row)
    return rows


def audit_rows(rows: list[dict[str, Any]], source_summary: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("source_stage9271_not_passed")
    if not rows:
        failures.append("manifest_empty")
    split_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    full_target_visible_rows = 0
    excessive_anchor_rows = 0
    authority_rows = 0
    unsafe_loss_rows = 0
    empty_targets = 0
    forbidden_key_rows = 0
    anchor_cards = []
    for row in rows:
        split_counts[str(row.get("split"))] = split_counts.get(str(row.get("split")), 0) + 1
        language_counts[str(row.get("language_family"))] = language_counts.get(str(row.get("language_family")), 0) + 1
        route_counts[str(row.get("route"))] = route_counts.get(str(row.get("route")), 0) + 1
        target = str((row.get("target") or {}).get("decoder_text", ""))
        if not target.strip():
            empty_targets += 1
        visible = visible_projection(row)
        if target and target in visible:
            full_target_visible_rows += 1
        state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        prefix_words = words(str(state.get("target_prefix_anchor_2", "")))
        keywords = state.get("target_anchor_keywords") if isinstance(state.get("target_anchor_keywords"), list) else []
        constraints = state.get("target_constraint_bits") if isinstance(state.get("target_constraint_bits"), list) else []
        if len(prefix_words) > 2 or len(keywords) > 4 or len(constraints) > 4 or int(state.get("target_anchor_word_count", 999)) > 12:
            excessive_anchor_rows += 1
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        if mask.get("denoise_ce") is not True or mask.get("decoder_ce") is not False or mask.get("runtime_reward") is not False:
            unsafe_loss_rows += 1
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else row
        if any(bool(auth.get(key, False)) for key in AUTHORITY_CLOSED):
            authority_rows += 1
        if set(row).intersection(FORBIDDEN_TOP_LEVEL):
            forbidden_key_rows += 1
        anchor_cards.append({
            "row_id": row.get("row_id"),
            "source_repair_row_id": row.get("source_repair_row_id"),
            "split": row.get("split"),
            "language_family": row.get("language_family"),
            "target_action_verb": state.get("target_action_verb"),
            "target_object_kind": state.get("target_object_kind"),
            "target_prefix_anchor_2": state.get("target_prefix_anchor_2"),
            "target_anchor_keywords": state.get("target_anchor_keywords"),
            "target_constraint_bits": state.get("target_constraint_bits"),
            "target_anchor_word_count": state.get("target_anchor_word_count"),
        })
    if full_target_visible_rows:
        failures.append("full_target_visible_rows_nonzero")
    if excessive_anchor_rows:
        failures.append("excessive_anchor_rows_nonzero")
    if authority_rows:
        failures.append("authority_rows_nonzero")
    if unsafe_loss_rows:
        failures.append("unsafe_loss_rows_nonzero")
    if empty_targets:
        failures.append("empty_targets_nonzero")
    if forbidden_key_rows:
        failures.append("forbidden_key_rows_nonzero")
    serialized_visible = "\n".join(visible_projection(row).lower() for row in rows)
    for token in ["/arxiv", "hidden_eval", "locked_eval", "runtime_authorized\": true", "gemma_execution_authorized_next\": true"]:
        if token in serialized_visible:
            failures.append(f"forbidden_visible_token:{token}")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": split_counts,
        "language_counts": language_counts,
        "route_counts": route_counts,
        "full_target_visible_rows": full_target_visible_rows,
        "excessive_anchor_rows": excessive_anchor_rows,
        "authority_rows": authority_rows,
        "unsafe_loss_rows": unsafe_loss_rows,
        "empty_targets": empty_targets,
        "forbidden_key_rows": forbidden_key_rows,
        "anchor_cards": anchor_cards,
        "authority": AUTHORITY_FALSE,
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": AUTHORITY_FALSE, "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = build_rows()
    audit = audit_rows(rows, source)
    MANIFEST.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    ANCHOR_CARD.write_text(json.dumps(audit["anchor_cards"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit_public = {key: value for key, value in audit.items() if key != "anchor_cards"}
    AUDIT.write_text(json.dumps(audit_public, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": AUTHORITY_FALSE,
        "metrics": {**AUTHORITY_FALSE, **audit_public},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "anchor_card": str(ANCHOR_CARD.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built target-grounded denoise rows with minimal anchor fields so the repair decoder can recover semantic targets without seeing full target text in model-visible inputs.",
        "next_best_step": "Run a contract-only preflight, then a tiny target-100M denoise probe with EOS weighting over Stage9272 and audit prefix recovery before any wider denoise data.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9272 Target-Grounded Denoise Manifest",
            "",
            "Stage9272 adds minimal target anchors to denoise repair rows without copying the full target into model-visible fields.",
            "",
            f"Rows: {audit['rows']}",
            f"Splits: {audit['split_counts']}",
            f"Full target visible rows: {audit['full_target_visible_rows']}",
            f"Excessive anchor rows: {audit['excessive_anchor_rows']}",
            f"Authority rows: {audit['authority_rows']}",
            f"Unsafe loss rows: {audit['unsafe_loss_rows']}",
            "",
            "Decoder CE, runtime, Gemma, harness, scoring, source/body emission, and promotion remain closed.",
        ]) + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
