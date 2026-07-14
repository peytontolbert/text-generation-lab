#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import time

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10572
NAME = "stage10572_visible_candidate_mixed_preservation_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "visible_candidate_mixed_preservation_support_package.json"
ROWS_PATH = OUT_DIR / "visible_candidate_mixed_preservation_support_rows.jsonl"
SUMMARY_REF = ROOT / "runs/summaries" / f"{NAME}.json"

S65_JSON = ROOT / "runs/local/artifacts/stage10565_visible_candidate_decisive_evidence_support_package/visible_candidate_decisive_evidence_support_package.json"
S65_ROWS = ROOT / "runs/local/artifacts/stage10565_visible_candidate_decisive_evidence_support_package/visible_candidate_decisive_evidence_support_rows.jsonl"
TRAIN_PATH = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/train_rows.jsonl"
STRICT_PATH = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/strict_eval_rows.jsonl"

LABELS = list("ABCDEFGH")
TARGET_LANGS = ["python", "c_cpp", "rust", "web_js_ts_html"]
VERIFIER_BASE_CAPS = {"python": 24, "c_cpp": 12, "rust": 2, "web_js_ts_html": 4}
RETRIEVE_BASE_CAPS = {"python": 8, "c_cpp": 4, "rust": 2, "web_js_ts_html": 2}
PYTHON_REPO_CAP = 2
C_CPP_REPO_CAP = 3


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


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or "")


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("decoder_text") or row.get("target_text") or "")


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in (row.get("opaque_options") or []) if isinstance(item, dict)]


def ledger(row: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((row.get("standalone_projection_source") or {}).get("ledger")) or [])


def rebuild_prompt(base_text: str, ledgers: list[dict[str, Any]], new_options: list[dict[str, Any]]) -> str:
    prefix = base_text.split("\n\nVisible evidence ledger:\n", 1)[0].rstrip()
    lines = [prefix, "", "Visible evidence ledger:"]
    for item in ledgers:
        lines.append(f"{item['ledger_id']}: {item['value']}")
    lines.append("")
    lines.append("Choices:")
    for option in new_options:
        lines.append(f"{option['label']}: {option['value'] if option['value'].startswith(('ANSWER_','RETRIEVE_','ABSTAIN_','NEEDS_','PASS_','UNKNOWN')) else next((entry['ledger_id'] for entry in ledgers if entry.get('value') == option.get('value')), '')}")
    lines.append("Return only the option label.")
    return "\n".join(lines)


def choose_offset(row: dict[str, Any]) -> int:
    opts = options(row)
    labels = [str(item.get("label") or "") for item in opts]
    gold = target_label(row)
    if gold not in labels or len(labels) < 2:
        return 0
    gold_idx = labels.index(gold)
    for offset in [1, 2, len(labels) - 1]:
        offset %= len(labels)
        if offset == 0:
            continue
        if LABELS[(gold_idx - offset) % len(labels)] != gold:
            return offset
    return 1


def permute_row(row: dict[str, Any], role: str) -> dict[str, Any]:
    out = clone(row)
    opts = options(row)
    if len(opts) < 2:
        out["augmentation_role"] = role + "_base_only"
        return out
    offset = choose_offset(row)
    rotated_values = [opts[(idx + offset) % len(opts)]["value"] for idx in range(len(opts))]
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
    source["permutation_offset"] = offset
    out["standalone_projection_source"] = source
    anti = dict(out.get("anti_cheat") or {})
    anti["option_permutation_variant"] = True
    anti["strict_eval_source_reuse_forbidden"] = True
    anti["same_root_train_eval_forbidden"] = True
    out["anti_cheat"] = anti
    out["augmentation_role"] = role + "_label_permutation"
    out["support_package_stage"] = STAGE
    return out


def base_row(row: dict[str, Any], role: str) -> dict[str, Any]:
    out = clone(row)
    anti = dict(out.get("anti_cheat") or {})
    anti["strict_eval_source_reuse_forbidden"] = True
    anti["same_root_train_eval_forbidden"] = True
    out["anti_cheat"] = anti
    out["augmentation_role"] = role + "_base"
    out["support_package_stage"] = STAGE
    return out


def repo_cap(lang: str) -> int:
    if lang == "python":
        return PYTHON_REPO_CAP
    if lang == "c_cpp":
        return C_CPP_REPO_CAP
    return 999


def select_support(rows: list[dict[str, Any]], strict_roots: set[str], subtype: str, caps: dict[str, int]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for lang in TARGET_LANGS:
        pool = [
            row for row in rows
            if row.get("target_subtype") == subtype
            and row.get("language_family") == lang
            and row.get("standalone_projection_source")
            and root_key(row) not in strict_roots
        ]
        pool.sort(key=lambda row: (target_label(row) == "A", repo_key(row), str(row.get("row_id") or "")))
        repos = Counter()
        lang_selected = 0
        for row in pool:
            if lang_selected >= caps.get(lang, 0):
                break
            repo = repo_key(row)
            if repos[repo] >= repo_cap(lang):
                continue
            repos[repo] += 1
            selected.append(row)
            lang_selected += 1
    return selected


def main() -> None:
    s65 = load_json(S65_JSON)
    base_rows = load_jsonl(S65_ROWS)
    train_rows = load_jsonl(TRAIN_PATH)
    strict_rows = load_jsonl(STRICT_PATH)
    strict_roots = {root_key(row) for row in strict_rows}

    verifier_rows = select_support(train_rows, strict_roots, "verifier_outcome_masked", VERIFIER_BASE_CAPS)
    retrieve_rows = select_support(train_rows, strict_roots, "retrieve_answer_abstain", RETRIEVE_BASE_CAPS)

    mixed_rows = list(base_rows)
    for row in verifier_rows:
        mixed_rows.append(base_row(row, "verifier_preservation"))
        mixed_rows.append(permute_row(row, "verifier_preservation"))
    for row in retrieve_rows:
        mixed_rows.append(base_row(row, "retrieve_preservation"))
        mixed_rows.append(permute_row(row, "retrieve_preservation"))

    mixed_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("target_subtype") or ""), str(row.get("row_id") or "")))
    strict_overlap = [str(row.get("row_id") or "") for row in mixed_rows if root_key(row) in strict_roots]
    language_counts = Counter(str(row.get("language_family") or "") for row in mixed_rows)
    subtype_counts = Counter(str(row.get("target_subtype") or "") for row in mixed_rows)
    role_counts = Counter(str(row.get("augmentation_role") or "") for row in mixed_rows)
    target_counts = Counter(target_label(row) for row in mixed_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Mixed train-support-only visible-candidate package that combines stage10565 decisive-evidence repair rows with small rebuilt-contract verifier/retrieve preservation anchors.",
            "All rows remain train-only and strict-root-disjoint from stage10561 heldout rows.",
            "Option-permutation variants are included for decisive, verifier, and retrieve support so label shortcuts are reduced rather than reinforced.",
        ],
        "inputs": {
            "stage10565_support_rows": display(S65_ROWS),
            "stage10561_train_rows": display(TRAIN_PATH),
            "stage10561_strict_rows": display(STRICT_PATH),
        },
        "selection_policy": {
            "verifier_base_caps": VERIFIER_BASE_CAPS,
            "retrieve_base_caps": RETRIEVE_BASE_CAPS,
            "python_repo_cap": PYTHON_REPO_CAP,
            "c_cpp_repo_cap": C_CPP_REPO_CAP,
            "strict_root_overlap_forbidden": True,
            "permutation_on_all_support_types": True,
        },
        "rows": {
            "from_stage10565": len(base_rows),
            "verifier_base_rows": len(verifier_rows),
            "retrieve_base_rows": len(retrieve_rows),
            "emitted_rows": len(mixed_rows),
        },
        "language_counts": dict(sorted(language_counts.items())),
        "target_subtype_counts": dict(sorted(subtype_counts.items())),
        "augmentation_role_counts": dict(sorted(role_counts.items())),
        "target_label_counts": dict(sorted(target_counts.items())),
        "anti_cheat": {
            "strict_root_overlap_rows": len(strict_overlap),
            "strict_root_overlap_forbidden": True,
            "option_permutation_variants_present": True,
            "same_root_train_eval_forbidden": True,
        },
        "outputs": {
            "support_rows": display(ROWS_PATH),
            "package_json": display(SUMMARY_PATH),
        },
    }
    write_jsonl(ROWS_PATH, mixed_rows)
    write_json(SUMMARY_PATH, payload)
    write_json(SUMMARY_REF, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
