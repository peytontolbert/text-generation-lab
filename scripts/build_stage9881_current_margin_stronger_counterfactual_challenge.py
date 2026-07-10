#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

try:
    from counterfactual_obligation_audit import audit_rows as audit_counterfactual_rows
except ModuleNotFoundError:
    from scripts.counterfactual_obligation_audit import audit_rows as audit_counterfactual_rows  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9881
NAME = "stage9881_current_margin_stronger_counterfactual_challenge"
SOURCE = ROOT / "runs/local/artifacts/stage9867_edit_localization_label_identity_probe/edit_localization_label_identity_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "current_margin_stronger_counterfactual_challenge.jsonl"
AUDIT = OUT_DIR / "current_margin_stronger_counterfactual_challenge_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MARGIN_STRONGER_COUNTERFACTUAL_CHALLENGE_STAGE9881.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
PACKETS = ROOT / "runs/local/artifacts/stage9879_current_margin_multilingual_winner_review_packets/current_margin_multilingual_winner_review_packet_manifest.json"
REQUIRED = {
    "POSITIVE_ORIGINAL",
    "EVIDENCE_REMOVED",
    "CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN",
    "MIXED_REPLAY",
}
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
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


def _clone(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(row))


def _root_id_from_row(row_id: str) -> str:
    parts = row_id.split("::")
    if len(parts) >= 2:
        return parts[0]
    return row_id


def _visible_text_safe(row: dict[str, Any]) -> bool:
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    fields = [
        str(state.get("task_observation") or ""),
        str(state.get("visible_locality_evidence") or ""),
        " ".join(str(x) for x in (state.get("candidate_choices") or [])),
    ]
    return all("TARGET_" not in text for text in fields)


def _source_rows() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = load_jsonl(SOURCE)
    packets = load_json(PACKETS)
    packet_langs = {str(row.get("language_family") or "") for row in ((packets.get("rows") if isinstance(packets.get("rows"), list) else []))}
    train_rows = {
        _root_id_from_row(str(row.get("row_id") or "")): row
        for row in rows
        if str(row.get("split") or "") == "train"
        and str(row.get("obligation_type") or "") == "POSITIVE_ORIGINAL"
        and str(row.get("language_family") or "") in packet_langs
    }
    strict_rows = {
        _root_id_from_row(str(row.get("row_id") or "")): row
        for row in rows
        if str(row.get("split") or "") == "strict_eval"
        and str(row.get("obligation_type") or "") == "MIXED_REPLAY"
        and str(row.get("language_family") or "") in packet_langs
    }
    common_roots = sorted(set(train_rows) & set(strict_rows))
    selected_train = [train_rows[root] for root in common_roots]
    return selected_train, train_rows, strict_rows


def _group_id(row: dict[str, Any]) -> str:
    root_id = _root_id_from_row(str(row.get("row_id") or ""))
    return f"cf_current::{row['language_family']}::{root_id}"


def build_rows() -> list[dict[str, Any]]:
    selected_train, train_rows, strict_rows = _source_rows()
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected_train:
        by_lang[str(row.get("language_family") or "")].append(row)
    for lang in by_lang:
        by_lang[lang].sort(key=lambda row: str(row.get("row_id") or ""))

    output: list[dict[str, Any]] = []
    for lang in LANGS:
        lang_rows = by_lang.get(lang, [])
        for idx, row in enumerate(lang_rows):
            donor = lang_rows[(idx + 1) % len(lang_rows)]
            root_id = _root_id_from_row(str(row.get("row_id") or ""))
            donor_root_id = _root_id_from_row(str(donor.get("row_id") or ""))
            mixed_source = strict_rows[root_id]
            donor_mixed = strict_rows[donor_root_id]
            gid = _group_id(row)
            base_meta = {
                "counterfactual_group_id": gid,
                "objective_family": "current_margin_edit_localization_counterfactual_guard",
                "counterfactual_root_row_id": root_id,
                "counterfactual_language_family": lang,
                "counterfactual_source_stage": 9867,
                "counterfactual_challenge_stage": STAGE,
                "counterfactual_required_obligations": sorted(REQUIRED),
                "counterfactual_frontier_stage": 9878,
                "counterfactual_review_stage": 9879,
            }

            original = _clone(row)
            original.update(base_meta)
            original["row_id"] = f"{root_id}::positive_original"
            original["split"] = "strict_eval"
            original["obligation_type"] = "POSITIVE_ORIGINAL"
            original["counterfactual_role"] = "positive_original"
            original["counterfactual_expected_behavior"] = "prediction_should_match_original_target"
            output.append(original)

            removed = _clone(row)
            removed.update(base_meta)
            removed["row_id"] = f"{root_id}::evidence_removed"
            removed["split"] = "strict_eval"
            removed["obligation_type"] = "EVIDENCE_REMOVED"
            removed["counterfactual_role"] = "evidence_removed"
            removed["counterfactual_expected_behavior"] = "performance_should_drop_or_model_should_request_more_evidence"
            removed_state = removed.get("input_state") if isinstance(removed.get("input_state"), dict) else {}
            removed_state["visible_locality_evidence"] = ""
            removed_state["context_config_visible"] = False
            removed_state["context_entrypoint_visible"] = False
            removed_state["context_symbol_names_visible"] = False
            removed_state["context_tests_visible"] = False
            removed_state["task_observation"] = str(removed_state.get("task_observation") or "") + " Counterfactual note: supporting locality details are unavailable."
            removed["input_state"] = removed_state
            output.append(removed)

            contradictory = _clone(row)
            contradictory.update(base_meta)
            contradictory["row_id"] = f"{root_id}::contradictory_evidence"
            contradictory["split"] = "strict_eval"
            contradictory["obligation_type"] = "CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN"
            contradictory["counterfactual_role"] = "contradictory_evidence"
            contradictory["counterfactual_expected_behavior"] = "prediction_should_follow_substituted_causal_evidence"
            contradictory["counterfactual_donor_row_id"] = donor_root_id
            contradictory_state = contradictory.get("input_state") if isinstance(contradictory.get("input_state"), dict) else {}
            donor_state = donor.get("input_state") if isinstance(donor.get("input_state"), dict) else {}
            contradictory_state["visible_locality_evidence"] = donor_state.get("visible_locality_evidence")
            contradictory_state["task_observation"] = donor_state.get("task_observation")
            contradictory_state["context_config_visible"] = donor_state.get("context_config_visible")
            contradictory_state["context_entrypoint_visible"] = donor_state.get("context_entrypoint_visible")
            contradictory_state["context_symbol_names_visible"] = donor_state.get("context_symbol_names_visible")
            contradictory_state["context_tests_visible"] = donor_state.get("context_tests_visible")
            contradictory["input_state"] = contradictory_state
            contradictory_target = contradictory.get("target") if isinstance(contradictory.get("target"), dict) else {}
            donor_target = donor.get("target") if isinstance(donor.get("target"), dict) else {}
            contradictory_target["decoder_text"] = donor_target.get("decoder_text")
            contradictory_target["edit_localization"] = donor_target.get("edit_localization")
            contradictory_target["target_ref"] = donor_target.get("target_ref")
            contradictory["target"] = contradictory_target
            contradictory_clean = contradictory.get("clean_state") if isinstance(contradictory.get("clean_state"), dict) else {}
            donor_clean = donor.get("clean_state") if isinstance(donor.get("clean_state"), dict) else {}
            contradictory_clean["edit_localization"] = donor_clean.get("edit_localization")
            contradictory_clean["edit_localization_target"] = donor_clean.get("edit_localization_target")
            contradictory_clean["edit_localization_target_hidden"] = donor_clean.get("edit_localization_target_hidden")
            contradictory["clean_state"] = contradictory_clean
            output.append(contradictory)

            mixed = _clone(mixed_source)
            mixed.update(base_meta)
            mixed["row_id"] = f"{root_id}::mixed_replay"
            mixed["split"] = "strict_eval"
            mixed["obligation_type"] = "MIXED_REPLAY"
            mixed["counterfactual_role"] = "mixed_replay"
            mixed["counterfactual_expected_behavior"] = "prediction_should_ignore_decoy_and_resist_label_proxy_shortcuts"
            donor_target = donor_mixed.get("target") if isinstance(donor_mixed.get("target"), dict) else {}
            mixed["counterfactual_wrong_label"] = donor_target.get("decoder_text")
            output.append(mixed)
    return output


def build_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cf = audit_counterfactual_rows(rows, required=REQUIRED)
    obligation_counts = Counter(str(row.get("obligation_type") or "") for row in rows)
    lang_counts = Counter(str(row.get("language_family") or "") for row in rows)
    visible_target_literal_rows = [str(row.get("row_id") or "") for row in rows if not _visible_text_safe(row)]
    failures: list[str] = []
    if len(rows) != 64:
        failures.append(f"rows_not_64:{len(rows)}")
    if len({str(row.get('counterfactual_group_id') or '') for row in rows}) != 16:
        failures.append("groups_not_16")
    for obligation in sorted(REQUIRED):
        if obligation_counts.get(obligation) != 16:
            failures.append(f"obligation_count_mismatch:{obligation}:{obligation_counts.get(obligation, 0)}")
    for lang in LANGS:
        if lang_counts.get(lang) != 16:
            failures.append(f"language_count_mismatch:{lang}:{lang_counts.get(lang, 0)}")
    if visible_target_literal_rows:
        failures.append("visible_target_literals_present")
    if not cf.get("counterfactual_obligations_complete"):
        failures.append("counterfactual_obligations_incomplete")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "groups": len({str(row.get('counterfactual_group_id') or '') for row in rows}),
        "obligation_counts": dict(sorted(obligation_counts.items())),
        "language_counts": dict(sorted(lang_counts.items())),
        "visible_target_literal_rows": visible_target_literal_rows,
        "counterfactual_obligation_card": cf,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    write_jsonl(MANIFEST, rows)
    audit = build_audit(rows)
    write_json(AUDIT, audit)
    next_step = "Convert the Stage9881 stronger challenge bank into a current-frontier execution manifest so the 100M model can be rerun on mixed-replay strict rows while evidence-removed and contradictory siblings stay in the frozen anti-cheat bank."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "rows": audit["rows"], "groups": audit["groups"], "obligation_counts": audit["obligation_counts"], "language_counts": audit["language_counts"], "failures": audit["failures"]},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a stronger same-packet counterfactual challenge bank for the current Stage9878 multilingual frontier using the exact Stage9867 winning rows, with complete sibling obligations across original, evidence-removed, contradictory-evidence, and mixed-replay variants.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9881 Current Margin Stronger Counterfactual Challenge",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Groups: `{audit['groups']}`",
                f"Obligation counts: `{audit['obligation_counts']}`",
                f"Language counts: `{audit['language_counts']}`",
                "",
                "This stage upgrades the current Stage9878 frontier from inherited counterfactuals to a real rerun-ready current-packet challenge bank with explicit clustered siblings.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit['passed'], "rows": audit['rows'], "groups": audit['groups'], "failures": audit['failures']}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
