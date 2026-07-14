#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10565
NAME = "stage10565_visible_candidate_decisive_evidence_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "visible_candidate_decisive_evidence_support_package.json"
ROWS_PATH = OUT_DIR / "visible_candidate_decisive_evidence_support_rows.jsonl"
SUMMARY_REF = ROOT / "runs/summaries" / f"{NAME}.json"

TRAIN_PATH = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/train_rows.jsonl"
STRICT_PATH = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/strict_eval_rows.jsonl"
STAGE10563 = ROOT / "runs/local/artifacts/stage10563_visible_candidate_transition_bounded_audit/visible_candidate_transition_bounded_audit.json"

TARGET_LANGS = ["python", "c_cpp", "rust", "web_js_ts_html"]
LABELS = list("ABCDEFGH")
PYTHON_REPO_CAP = 2
C_CPP_REPO_CAP = 3
BASE_ROW_CAPS = {"python": 96, "c_cpp": 24, "rust": 8, "web_js_ts_html": 8}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def clone(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(row))


def repo_key(row: dict[str, Any]) -> str:
    return str(row.get("repo_family") or row.get("repo_id") or "unknown")


def option_count(row: dict[str, Any]) -> int:
    return len(row.get("opaque_options") or [])


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("decoder_text") or row.get("target_text") or "")


def ledger(row: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((row.get("standalone_projection_source") or {}).get("ledger")) or [])


def choose_offset(row: dict[str, Any]) -> int:
    options = row.get("opaque_options") or []
    gold = target_label(row)
    labels = [str(item.get("label") or "") for item in options if isinstance(item, dict)]
    if gold not in labels or len(labels) < 2:
        return 0
    gold_idx = labels.index(gold)
    preferred = [1, 2, 3, len(labels) - 1]
    for offset in preferred:
        offset = offset % len(labels)
        if offset == 0:
            continue
        new_idx = (gold_idx - offset) % len(labels)
        if LABELS[new_idx] != gold:
            return offset
    return 1


def rebuild_prompt(base_text: str, ledgers: list[dict[str, Any]], options: list[dict[str, Any]]) -> str:
    prefix = base_text.split("\n\nVisible evidence ledger:\n", 1)[0].rstrip()
    lines = [prefix, "", "Visible evidence ledger:"]
    for item in ledgers:
        lines.append(f"{item['ledger_id']}: {item['value']}")
    lines.append("")
    lines.append("Choices:")
    for option in options:
        target_ledger = next((item.get("ledger_id") for item in ledgers if item.get("value") == option.get("value")), None)
        if not target_ledger:
            raise RuntimeError(f"missing_ledger_for_option:{option.get('value')}")
        lines.append(f"{option['label']}: {target_ledger}")
    lines.append("Return only the option label.")
    return "\n".join(lines)


def rotate_variant(row: dict[str, Any]) -> dict[str, Any]:
    out = clone(row)
    options = [dict(item) for item in (row.get("opaque_options") or []) if isinstance(item, dict)]
    if len(options) < 2:
        out["augmentation_role"] = "base_only_insufficient_options"
        return out
    labels = [str(item.get("label") or "") for item in options]
    offset = choose_offset(row)
    rotated_values = [options[(idx + offset) % len(options)]["value"] for idx in range(len(options))]
    rotated = [{"label": LABELS[idx], "value": rotated_values[idx]} for idx in range(len(rotated_values))]
    gold_value = str(((row.get("standalone_projection_source") or {}).get("gold_value")) or "")
    new_gold = next((item["label"] for item in rotated if str(item.get("value") or "") == gold_value), None)
    if new_gold is None:
        raise RuntimeError(f"rotated_gold_missing:{row['row_id']}")
    out["row_id"] = str(row["row_id"]) + "::permute_visible_choices"
    out["input_text"] = rebuild_prompt(str(row.get("input_text") or ""), ledger(row), rotated)
    out["prompt_text"] = out["input_text"]
    out["opaque_options"] = rotated
    out["target_text"] = new_gold
    out["decoder_text"] = new_gold
    source = dict(out.get("standalone_projection_source") or {})
    source["opaque_options"] = rotated
    source["gold_value"] = gold_value
    source["permutation_offset"] = offset
    out["standalone_projection_source"] = source
    anti = dict(out.get("anti_cheat") or {})
    anti["option_permutation_variant"] = True
    anti["same_root_train_eval_forbidden"] = True
    anti["strict_eval_source_reuse_forbidden"] = True
    out["anti_cheat"] = anti
    out["augmentation_role"] = "label_permutation"
    out["support_package_stage"] = STAGE
    return out


def base_variant(row: dict[str, Any]) -> dict[str, Any]:
    out = clone(row)
    anti = dict(out.get("anti_cheat") or {})
    anti["same_root_train_eval_forbidden"] = True
    anti["strict_eval_source_reuse_forbidden"] = True
    out["anti_cheat"] = anti
    out["augmentation_role"] = "base_visible_candidate"
    out["support_package_stage"] = STAGE
    return out


def select_rows(rows: list[dict[str, Any]], strict_root_ids: set[str]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("target_subtype") != "decisive_evidence_top1":
            continue
        if row.get("language_family") not in TARGET_LANGS:
            continue
        if not row.get("standalone_projection_source"):
            continue
        if option_count(row) < 4:
            continue
        if str(row.get("root_id") or "") in strict_root_ids:
            continue
        buckets[str(row.get("language_family"))].append(row)

    selected: list[dict[str, Any]] = []
    for lang in TARGET_LANGS:
        lang_rows = buckets.get(lang, [])
        lang_rows.sort(key=lambda row: (target_label(row) == "A", repo_key(row), str(row.get("row_id") or "")))
        repo_cap = PYTHON_REPO_CAP if lang == "python" else C_CPP_REPO_CAP if lang == "c_cpp" else 999
        lang_cap = BASE_ROW_CAPS.get(lang, len(lang_rows))
        repo_counts: Counter[str] = Counter()
        for row in lang_rows:
            if sum(1 for item in selected if str(item.get("language_family") or "") == lang) >= lang_cap:
                break
            repo = repo_key(row)
            if repo_counts[repo] >= repo_cap:
                continue
            repo_counts[repo] += 1
            selected.append(row)
    return selected


def main() -> None:
    train_rows = load_jsonl(TRAIN_PATH)
    strict_rows = load_jsonl(STRICT_PATH)
    strict_root_ids = {str(row.get("root_id") or "") for row in strict_rows}
    selected = select_rows(train_rows, strict_root_ids)
    package_rows: list[dict[str, Any]] = []
    for row in selected:
        package_rows.append(base_variant(row))
        if option_count(row) >= 2:
            package_rows.append(rotate_variant(row))
    package_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("repo_family") or row.get("repo_id") or ""), str(row.get("row_id") or "")))

    by_lang = Counter(str(row.get("language_family") or "") for row in package_rows)
    by_role = Counter(str(row.get("augmentation_role") or "") for row in package_rows)
    by_label = Counter(str(target_label(row)) for row in package_rows)
    roots_by_lang: dict[str, set[str]] = defaultdict(set)
    repos_by_lang: dict[str, set[str]] = defaultdict(set)
    strict_overlap = []
    for row in package_rows:
        lang = str(row.get("language_family") or "")
        roots_by_lang[lang].add(str(row.get("root_id") or ""))
        repos_by_lang[lang].add(repo_key(row))
        if str(row.get("root_id") or "") in strict_root_ids:
            strict_overlap.append(str(row.get("row_id") or ""))

    s63 = load_json(STAGE10563) if STAGE10563.exists() else {}
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Train-support-only multilingual visible-candidate decisive-evidence package built from stage10561 train roots only.",
            "Targets the stage10563 A-attractor failure by adding label-permutation variants on the same visible-ledger contract.",
            "Not promotable eval; strict successor rows remain held out.",
        ],
        "inputs": {
            "stage10561_train_rows": display(TRAIN_PATH),
            "stage10561_strict_rows": display(STRICT_PATH),
            "stage10563_transition_audit": display(STAGE10563),
        },
        "selection_policy": {
            "target_subtype": "decisive_evidence_top1",
            "languages": TARGET_LANGS,
            "base_row_caps": BASE_ROW_CAPS,
            "python_repo_cap": PYTHON_REPO_CAP,
            "c_cpp_repo_cap": C_CPP_REPO_CAP,
            "strict_root_overlap_forbidden": True,
            "min_option_count": 4,
            "sort_bias": "non_A_targets_first_with_repo_caps",
            "augmentation": ["base_visible_candidate", "label_permutation"],
        },
        "rows": {
            "selected_base_rows": len(selected),
            "emitted_rows": len(package_rows),
        },
        "language_counts": dict(sorted(by_lang.items())),
        "augmentation_role_counts": dict(sorted(by_role.items())),
        "target_label_counts": dict(sorted(by_label.items())),
        "root_counts_by_language": {lang: len(vals) for lang, vals in sorted(roots_by_lang.items())},
        "repo_counts_by_language": {lang: len(vals) for lang, vals in sorted(repos_by_lang.items())},
        "anti_cheat": {
            "strict_root_overlap_rows": len(strict_overlap),
            "strict_root_overlap_forbidden": True,
            "option_permutation_variants_present": by_role.get("label_permutation", 0) > 0,
            "same_root_train_eval_forbidden": True,
        },
        "motivation_from_stage10563": {
            "decoder_first_step_overall_accuracy": (((s63.get("summary") or {}).get("decoder_first_step")) or {}).get("accuracy"),
            "decisive_evidence_decoder_accuracy": ((((s63.get("per_target_subtype") or {}).get("decisive_evidence_top1")) or {}).get("decoder_first_step") or {}).get("accuracy"),
        },
        "supply_gaps": [
            "Rust decisive-evidence support remains extremely thin: only 2 base roots were available in stage10561 train supply.",
            "Web decisive-evidence support remains extremely thin: only 3 base roots from 1 repo family were available in stage10561 train supply.",
            "Further multilingual progress will require fresh disjoint root compilation, not only more training on this support package.",
        ],
        "outputs": {
            "support_rows": display(ROWS_PATH),
            "package_json": display(SUMMARY_PATH),
        },
    }
    write_jsonl(ROWS_PATH, package_rows)
    write_json(SUMMARY_PATH, payload)
    write_json(SUMMARY_REF, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
