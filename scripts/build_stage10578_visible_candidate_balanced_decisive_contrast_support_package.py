#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10578
NAME = "stage10578_visible_candidate_balanced_decisive_contrast_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "visible_candidate_balanced_decisive_contrast_support_package.json"
ROWS_PATH = OUT_DIR / "visible_candidate_balanced_decisive_contrast_support_rows.jsonl"
SUMMARY_REF = ROOT / "runs/summaries" / f"{NAME}.json"

TRAIN_PATH = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/train_rows.jsonl"
STRICT_PATH = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/strict_eval_rows.jsonl"
PRIOR_PACKAGE = ROOT / "runs/local/artifacts/stage10572_visible_candidate_mixed_preservation_support_package/visible_candidate_mixed_preservation_support_package.json"

LABELS = list("ABCDEFGH")
TARGET_LANGS = ["python", "c_cpp", "rust", "web_js_ts_html"]
DECISIVE_CAPS = {
    "python": {"verification_target": 48, "changed_file": 8, "key_symbol": 2},
    "c_cpp": {"verification_target": 30, "changed_file": 8, "key_symbol": 0},
    "rust": {"verification_target": 2, "changed_file": 1, "key_symbol": 0},
    "web_js_ts_html": {"verification_target": 4, "changed_file": 0, "key_symbol": 0},
}
VERIFIER_BASE_CAPS = {"python": 12, "c_cpp": 8, "rust": 2, "web_js_ts_html": 2}
RETRIEVE_BASE_CAPS = {"python": 6, "c_cpp": 4, "rust": 2, "web_js_ts_html": 2}
VARIANT_LIMITS = {"python": 2, "c_cpp": 3, "rust": 5, "web_js_ts_html": 5}
PYTHON_REPO_CAP = 2
C_CPP_REPO_CAP = 3


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def gold_value(row: dict[str, Any]) -> str:
    return str(((row.get("standalone_projection_source") or {}).get("gold_value")) or "")


def value_prefix(value: str) -> str:
    return value.split("::", 1)[0] if "::" in value else value


def option_prefixes(row: dict[str, Any]) -> set[str]:
    return {value_prefix(str(item.get("value") or "")) for item in options(row)}


def rebuild_prompt(base_text: str, ledgers: list[dict[str, Any]], new_options: list[dict[str, Any]]) -> str:
    prefix = base_text.split("\n\nVisible evidence ledger:\n", 1)[0].rstrip()
    lines = [prefix, "", "Visible evidence ledger:"]
    for item in ledgers:
        lines.append(f"{item['ledger_id']}: {item['value']}")
    lines.append("")
    lines.append("Choices:")
    for option in new_options:
        value = str(option.get("value") or "")
        ledger_id = next((entry["ledger_id"] for entry in ledgers if entry.get("value") == value), value)
        lines.append(f"{option['label']}: {ledger_id}")
    lines.append("Return only the option label.")
    return "\n".join(lines)


def choose_offsets(row: dict[str, Any], max_variants: int) -> list[int]:
    opts = options(row)
    labels = [str(item.get("label") or "") for item in opts]
    gold = target_label(row)
    if gold not in labels or len(labels) < 2:
        return []
    gold_idx = labels.index(gold)
    out: list[int] = []
    for offset in range(1, len(labels)):
        new_idx = (gold_idx - offset) % len(labels)
        if LABELS[new_idx] == gold:
            continue
        out.append(offset)
        if len(out) >= max_variants:
            break
    return out


def permute_row(row: dict[str, Any], offset: int, role: str) -> dict[str, Any]:
    out = clone(row)
    opts = options(row)
    rotated_values = [opts[(idx + offset) % len(opts)]["value"] for idx in range(len(opts))]
    rotated = [{"label": LABELS[idx], "value": rotated_values[idx]} for idx in range(len(rotated_values))]
    gold = gold_value(row)
    new_gold = next((item["label"] for item in rotated if str(item.get("value") or "") == gold), None)
    if new_gold is None:
        raise RuntimeError(f"rotated_gold_missing:{row['row_id']}")
    out["row_id"] = f"{row['row_id']}::permute_visible_choices_{offset}"
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
    out["augmentation_role"] = f"{role}_label_permutation"
    out["support_package_stage"] = STAGE
    return out


def base_row(row: dict[str, Any], role: str) -> dict[str, Any]:
    out = clone(row)
    anti = dict(out.get("anti_cheat") or {})
    anti["strict_eval_source_reuse_forbidden"] = True
    anti["same_root_train_eval_forbidden"] = True
    out["anti_cheat"] = anti
    out["augmentation_role"] = f"{role}_base"
    out["support_package_stage"] = STAGE
    return out


def repo_cap(lang: str) -> int:
    if lang == "python":
        return PYTHON_REPO_CAP
    if lang == "c_cpp":
        return C_CPP_REPO_CAP
    return 999


def select_decisive(rows: list[dict[str, Any]], strict_roots: set[str]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for lang in TARGET_LANGS:
        pool = [
            row for row in rows
            if row.get("target_subtype") == "decisive_evidence_top1"
            and row.get("language_family") == lang
            and row.get("standalone_projection_source")
            and root_key(row) not in strict_roots
            and len(options(row)) >= 4
            and "verification_target" in option_prefixes(row)
            and "changed_file" in option_prefixes(row)
        ]
        pool.sort(
            key=lambda row: (
                value_prefix(gold_value(row)) != "verification_target",
                "key_symbol" not in option_prefixes(row),
                target_label(row) == "A",
                repo_key(row),
                str(row.get("row_id") or ""),
            )
        )
        repo_counts: Counter[str] = Counter()
        type_counts: Counter[str] = Counter()
        caps = DECISIVE_CAPS.get(lang, {})
        for row in pool:
            gprefix = value_prefix(gold_value(row))
            if gprefix not in caps or type_counts[gprefix] >= caps[gprefix]:
                continue
            repo = repo_key(row)
            if repo_counts[repo] >= repo_cap(lang):
                continue
            repo_counts[repo] += 1
            type_counts[gprefix] += 1
            selected.append(row)
    return selected


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
        repo_counts: Counter[str] = Counter()
        lang_count = 0
        for row in pool:
            if lang_count >= caps.get(lang, 0):
                break
            repo = repo_key(row)
            if repo_counts[repo] >= repo_cap(lang):
                continue
            repo_counts[repo] += 1
            lang_count += 1
            selected.append(row)
    return selected


def main() -> None:
    train_rows = load_jsonl(TRAIN_PATH)
    strict_rows = load_jsonl(STRICT_PATH)
    strict_roots = {root_key(row) for row in strict_rows}

    decisive_rows = select_decisive(train_rows, strict_roots)
    verifier_rows = select_support(train_rows, strict_roots, "verifier_outcome_masked", VERIFIER_BASE_CAPS)
    retrieve_rows = select_support(train_rows, strict_roots, "retrieve_answer_abstain", RETRIEVE_BASE_CAPS)

    out_rows: list[dict[str, Any]] = []
    for row in decisive_rows:
        lang = str(row.get("language_family") or "")
        out_rows.append(base_row(row, "decisive_contrast"))
        for offset in choose_offsets(row, VARIANT_LIMITS.get(lang, 2)):
            out_rows.append(permute_row(row, offset, "decisive_contrast"))
    for row in verifier_rows:
        out_rows.append(base_row(row, "verifier_preservation"))
        for offset in choose_offsets(row, 1):
            out_rows.append(permute_row(row, offset, "verifier_preservation"))
    for row in retrieve_rows:
        out_rows.append(base_row(row, "retrieve_preservation"))
        for offset in choose_offsets(row, 1):
            out_rows.append(permute_row(row, offset, "retrieve_preservation"))

    out_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("target_subtype") or ""), str(row.get("row_id") or "")))
    language_counts = Counter(str(row.get("language_family") or "") for row in out_rows)
    subtype_counts = Counter(str(row.get("target_subtype") or "") for row in out_rows)
    role_counts = Counter(str(row.get("augmentation_role") or "") for row in out_rows)
    target_counts = Counter(target_label(row) for row in out_rows)
    strict_overlap = [str(row.get("row_id") or "") for row in out_rows if root_key(row) in strict_roots]

    decisive_base_by_lang = Counter(str(row.get("language_family") or "") for row in decisive_rows)
    decisive_gold_by_lang: dict[str, Counter[str]] = defaultdict(Counter)
    for row in decisive_rows:
        decisive_gold_by_lang[str(row.get("language_family") or "")][value_prefix(gold_value(row))] += 1

    prior = load_json(PRIOR_PACKAGE)
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Train-support-only rebuilt-contract package that rebalances decisive-evidence supervision toward verification_target versus changed_file contrasts while preserving verifier and retrieve anchors.",
            "All rows remain train-only and root-disjoint from stage10561 strict rows.",
            "Scarce languages receive more option-permutation variants so the current rebuilt strict slice is not dominated by Python support.",
        ],
        "inputs": {
            "stage10561_train_rows": display(TRAIN_PATH),
            "stage10561_strict_rows": display(STRICT_PATH),
            "prior_support_package": display(PRIOR_PACKAGE),
        },
        "selection_policy": {
            "decisive_caps": DECISIVE_CAPS,
            "verifier_base_caps": VERIFIER_BASE_CAPS,
            "retrieve_base_caps": RETRIEVE_BASE_CAPS,
            "variant_limits": VARIANT_LIMITS,
            "required_option_prefixes_for_decisive": ["verification_target", "changed_file"],
            "strict_root_overlap_forbidden": True,
            "same_root_train_eval_forbidden": True,
        },
        "rows": {
            "decisive_base_rows": len(decisive_rows),
            "verifier_base_rows": len(verifier_rows),
            "retrieve_base_rows": len(retrieve_rows),
            "emitted_rows": len(out_rows),
        },
        "decisive_base_by_language": dict(sorted(decisive_base_by_lang.items())),
        "decisive_gold_prefix_by_language": {
            lang: dict(sorted(counter.items())) for lang, counter in sorted(decisive_gold_by_lang.items())
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
            "prompt_target_leak_expected_false": True,
        },
        "comparison_to_stage10572": {
            "prior_emitted_rows": ((prior.get("rows") or {}).get("emitted_rows")),
            "prior_language_counts": prior.get("language_counts"),
            "prior_target_subtype_counts": prior.get("target_subtype_counts"),
        },
        "outputs": {
            "support_rows": display(ROWS_PATH),
            "package_json": display(SUMMARY_PATH),
        },
    }
    write_jsonl(ROWS_PATH, out_rows)
    write_json(SUMMARY_PATH, payload)
    write_json(SUMMARY_REF, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
