#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from loss_mask_card import LOSS_KEYS, normalize_loss_mask, validate_loss_mask_row
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.loss_mask_card import LOSS_KEYS, normalize_loss_mask, validate_loss_mask_row  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9240
NAME = "stage9240_source_backed_multilang_bounded_decoder_tiny_package"
SOURCE_TARGET_STORE = ROOT / "runs/local/artifacts/stage8806_source_backed_decoder_target_materialization_controls/source_backed_decoder_target_store.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "source_backed_multilang_bounded_decoder_tiny_manifest.jsonl"
AUDIT = OUT_DIR / "source_backed_multilang_bounded_decoder_tiny_package_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_BACKED_MULTILANG_BOUNDED_DECODER_TINY_PACKAGE_STAGE9240.md"
CAPS = {"train": 32, "eval": 16, "strict_eval": 16}
LANGUAGE_TARGETS = {
    "train": {"python": 8, "rust": 8, "cpp": 8, "web_js_ts_html": 8},
    "eval": {"python": 4, "rust": 4, "cpp": 4, "web_js_ts_html": 4},
    "strict_eval": {"python": 4, "rust": 4, "cpp": 4, "web_js_ts_html": 4},
}
LANGUAGE_MAP = {"typescript": "web_js_ts_html", "cpp": "cpp", "python": "python", "rust": "rust"}
MAX_DECODER_TOKENS = 768


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def split_name(value: Any) -> str:
    split = str(value or "")
    return "strict_eval" if split == "strict" else split


def language_family(value: Any) -> str:
    return LANGUAGE_MAP.get(str(value or ""), str(value or "unknown"))


def decoder_loss_mask() -> dict[str, bool]:
    return {key: key == "decoder_ce" for key in LOSS_KEYS}


def input_state_for(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "language_family": language_family(row.get("language")),
        "source_language": row.get("language"),
        "context_group": row.get("context_group"),
        "bounded_argument_type": row.get("bounded_argument_type"),
        "source_backed_target_present": True,
        "decoder_budget_ok": True,
        "evidence_state": "direct_present",
    }


def model_visible_text(row: dict[str, Any]) -> str:
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    parts = [f"language={row.get('language_family')}", f"route={row.get('route')}", f"objective={row.get('objective_family')}", f"surface={row.get('surface')}"]
    for key, value in sorted(state.items()):
        parts.append(f"state.{key}={value}")
    return " | ".join(str(part) for part in parts)


def sorted_sources(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (str(row.get("bounded_argument_type")), str(row.get("context_group")), str(row.get("target_ref"))))


def build_rows(target_store: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_cell: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in target_store:
        split = split_name(row.get("split"))
        family = language_family(row.get("language"))
        text = str(row.get("decoder_text") or "").strip()
        token_len = int(row.get("decoder_token_len") or len(text.encode("utf-8")))
        if split in CAPS and family in LANGUAGE_TARGETS[split] and row.get("quality", {}).get("decoder_budget_ok") is True and text and token_len <= MAX_DECODER_TOKENS:
            by_cell[(split, family)].append(row)
    by_cell = {cell: sorted_sources(rows) for cell, rows in by_cell.items()}

    selected: list[dict[str, Any]] = []
    used_hashes: set[str] = set()
    selected_counts: dict[str, dict[str, int]] = {split: {language: 0 for language in LANGUAGE_TARGETS[split]} for split in LANGUAGE_TARGETS}
    for split, language_caps in LANGUAGE_TARGETS.items():
        for family, cap in language_caps.items():
            for source in by_cell.get((split, family), []):
                text = str(source.get("decoder_text") or "").strip()
                target_hash = str(source.get("decoder_text_sha256") or stable_hash(text))
                if target_hash in used_hashes:
                    continue
                used_hashes.add(target_hash)
                source_ref = str(source.get("target_ref"))
                idx = selected_counts[split][family]
                row = {
                    "row_id": f"stage9240_source_backed_{split}_{family}_{idx:03d}_{stable_hash(source_ref)[:12]}",
                    "split": split,
                    "objective_family": "bounded_decoder_ce",
                    "route": "KEEP_BOUNDED_DECODER",
                    "recommended_action": "KEEP_BOUNDED_DECODER",
                    "risk_bucket": "KEEP_BOUNDED_DECODER",
                    "language_family": family,
                    "source_language": source.get("language"),
                    "surface": "BOUNDED_DECODER_ARGUMENT_TEXT",
                    "input_state": input_state_for(source),
                    "target": {
                        "decoder_text": text,
                        "target_shape": "BOUNDED_DECODER_ARGUMENT_TEXT",
                        "target_ref": source_ref,
                        "target_text_sha256": target_hash,
                    },
                    "decoder_token_len": int(source.get("decoder_token_len") or len(text.encode("utf-8"))),
                    "decoder_budget_ok": True,
                    "target_length_bucket": "bounded",
                    "source_stage": 8806,
                    "source_target_ref": source_ref,
                    "source_target_hash": target_hash,
                    "copied_target_text_in_input": False,
                    "loss_mask": decoder_loss_mask(),
                    "authority": dict(AUTHORITY_CLOSED),
                    "anti_cheat": {
                        "raw_source_included": False,
                        "raw_decoder_text_in_encoder": False,
                        "raw_patch_body_included": False,
                        "target_text_in_model_input": False,
                        "target_text_in_encoder": False,
                        "source_target_ref_in_model_input": False,
                        "split_disjoint_target_hash_required": True,
                        "language_balance_required": True,
                        "no_execution_in_this_stage": True,
                    },
                }
                selected.append(row)
                selected_counts[split][family] += 1
                if selected_counts[split][family] >= cap:
                    break
    source_counts = {f"{split}:{family}": len(rows) for (split, family), rows in sorted(by_cell.items())}
    return selected, {"source_cell_counts": source_counts, "selected_counts": selected_counts}


def audit_rows(rows: list[dict[str, Any]], selection_card: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    split_counts = Counter(row.get("split") for row in rows)
    language_counts = Counter(row.get("language_family") for row in rows)
    split_language_counts = Counter((row.get("split"), row.get("language_family")) for row in rows)
    arg_counts = Counter((row.get("split"), row.get("language_family"), (row.get("input_state") or {}).get("bounded_argument_type")) for row in rows)
    hash_splits: dict[str, set[str]] = defaultdict(set)
    authority_rows = 0
    unsafe_loss_rows = []
    over_cap_rows = []
    target_ref_rows = []
    copied_text_rows = []
    empty_rows = []
    repetition_rows = []
    terminal_rows = 0
    for row in rows:
        row_id = str(row.get("row_id"))
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        text = str(target.get("decoder_text") or "")
        target_hash = str(target.get("target_text_sha256") or stable_hash(text))
        hash_splits[target_hash].add(str(row.get("split")))
        if any((row.get("authority") or {}).values()):
            authority_rows += 1
        enabled = [key for key, value in normalize_loss_mask(row).items() if value]
        mask_errors = validate_loss_mask_row(row, allow_decoder_ce=True, allow_denoise=False, allow_runtime=False)
        if enabled != ["decoder_ce"] or mask_errors:
            unsafe_loss_rows.append({"row_id": row_id, "enabled": enabled, "errors": mask_errors})
        if int(row.get("decoder_token_len") or 0) > MAX_DECODER_TOKENS:
            over_cap_rows.append(row_id)
        if text.startswith("target_ref::") or str(target.get("target_ref") or "").startswith("target_ref::reconstructed"):
            target_ref_rows.append(row_id)
        if not text.strip():
            empty_rows.append(row_id)
        if "_refamily_refamily" in text or text.count("refamily") >= 2:
            repetition_rows.append(row_id)
        visible = model_visible_text(row)
        if text and (text in json.dumps(row.get("input_state") or {}, sort_keys=True) or text in visible):
            copied_text_rows.append(row_id)
        terminal_rows += int(bool(text.strip()) and text[-1] in ".!?")
    cross_split_duplicate_hashes = {h: sorted(splits) for h, splits in hash_splits.items() if len(splits) > 1}
    expected_split_language = {(split, language): count for split, language_counts_target in LANGUAGE_TARGETS.items() for language, count in language_counts_target.items()}
    checks = {
        "rows_match_caps": dict(split_counts) == CAPS,
        "split_language_counts_match_targets": all(split_language_counts.get(cell, 0) == count for cell, count in expected_split_language.items()),
        "all_required_languages_present": set(language_counts) == {"python", "rust", "cpp", "web_js_ts_html"},
        "authority_rows_zero": authority_rows == 0,
        "unsafe_loss_rows_zero": len(unsafe_loss_rows) == 0,
        "over_cap_rows_zero": len(over_cap_rows) == 0,
        "target_ref_placeholder_rows_zero": len(target_ref_rows) == 0,
        "empty_target_rows_zero": len(empty_rows) == 0,
        "repetition_target_rows_zero": len(repetition_rows) == 0,
        "target_text_copied_to_input_rows_zero": len(copied_text_rows) == 0,
        "cross_split_duplicate_target_hashes_zero": len(cross_split_duplicate_hashes) == 0,
        "all_targets_sentence_terminal": terminal_rows == len(rows),
    }
    failures.extend([key for key, value in checks.items() if value is not True])
    return {
        "passed": not failures,
        "failures": failures,
        "checks": checks,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "split_language_counts": {f"{split}:{lang}": count for (split, lang), count in sorted(split_language_counts.items())},
        "arg_cell_counts": {f"{split}:{lang}:{arg}": count for (split, lang, arg), count in sorted(arg_counts.items())},
        "source_cell_counts": selection_card["source_cell_counts"],
        "selected_counts": selection_card["selected_counts"],
        "authority_rows": authority_rows,
        "unsafe_loss_rows": len(unsafe_loss_rows),
        "unsafe_loss_examples": unsafe_loss_rows[:20],
        "over_cap_rows": len(over_cap_rows),
        "target_ref_placeholder_rows": len(target_ref_rows),
        "empty_target_rows": len(empty_rows),
        "repetition_target_rows": len(repetition_rows),
        "target_text_copied_to_input_rows": len(copied_text_rows),
        "target_hash_unique_rows": len(hash_splits),
        "cross_split_duplicate_target_hashes": len(cross_split_duplicate_hashes),
        "loss_counts": dict(Counter(key for row in rows for key, value in normalize_loss_mask(row).items() if value)),
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_rows = read_jsonl(SOURCE_TARGET_STORE)
    rows, selection_card = build_rows(source_rows)
    audit = audit_rows(rows, selection_card)
    write_jsonl(MANIFEST, rows)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "supersedes": ["stage9237_source_backed_bounded_decoder_tiny_package", "stage9238_source_backed_target_100m_contract_only_preflight", "stage9239_source_backed_bounded_decoder_execution_review"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "source_target_store": str(SOURCE_TARGET_STORE.relative_to(ROOT))},
        "decision": "Built a language-balanced source-backed tiny bounded decoder CE manifest for Python, Rust, C/C++, and web/TS; no execution authorized." if audit["passed"] else "Language-balanced source-backed tiny bounded decoder package failed audit.",
        "next_best_step": "Run target-100M contract-only preflight on the Stage9240 balanced manifest, then create a fresh inactive execution review if it passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9240 Source-Backed Multi-Language Bounded Decoder Tiny Package",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Rows: `{audit['rows']}`",
        f"Splits: `{audit['split_counts']}`",
        f"Languages: `{audit['language_counts']}`",
        f"Split-language counts: `{audit['split_language_counts']}`",
        f"Target hash unique rows: `{audit['target_hash_unique_rows']}`",
        f"Cross-split duplicate target hashes: `{audit['cross_split_duplicate_target_hashes']}`",
        f"Authority rows: `{audit['authority_rows']}`",
        f"Unsafe loss rows: `{audit['unsafe_loss_rows']}`",
        f"Target-ref placeholder rows: `{audit['target_ref_placeholder_rows']}`",
        f"Target text copied to input rows: `{audit['target_text_copied_to_input_rows']}`",
        "",
        "This stage supersedes the Stage9237 package because Stage9237 was safety-clean but language-imbalanced. Stage9240 enforces Python/Rust/C++/web-TS coverage before any target-100M execution.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if audit["passed"] else 1)


if __name__ == "__main__":
    main()
