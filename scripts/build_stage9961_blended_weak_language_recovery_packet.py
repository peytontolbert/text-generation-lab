#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from curriculum_compiler import compile_rows
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from golden_locked_eval_suite import load_locked_source_ids_from_exclusions
except ModuleNotFoundError:
    from scripts.curriculum_compiler import compile_rows  # type: ignore
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.golden_locked_eval_suite import load_locked_source_ids_from_exclusions  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9961
NAME = "stage9961_blended_weak_language_recovery_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "blended_weak_language_recovery_manifest.jsonl"
AUDIT = OUT_DIR / "blended_weak_language_recovery_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BLENDED_WEAK_LANGUAGE_RECOVERY_PACKET_STAGE9961.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
COMPILED_DIR = OUT_DIR / "compiled"

LOCKED_EXCLUSIONS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_source_exclusions.jsonl"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9947_web_targeted_blended_structured_execution_review/review_manifests/edit_localization.jsonl"
ROWS_100M = ROOT / "runs/local/artifacts/stage9950_edit_localization_web_targeted_blended_target100m_probe/edit_localization_probe/row_field_logits.jsonl"
ROWS_GEMMA = ROOT / "runs/local/artifacts/stage9953_blended_edit_localization_gemma_execution/same_prompt_surface_gemma12b_outputs_rows.jsonl"

WEAK_LANGS = {"python", "c_cpp", "web_js_ts_html"}
RUST_ANCHORS = 2


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _base_root(row_id: str) -> str:
    return str(row_id).split("::")[0]


def _normalize_row(row: dict[str, Any], *, reason: str, weight: int, base_root: str) -> dict[str, Any]:
    out = json.loads(json.dumps(row))
    out["row_id"] = f"stage9961_{row.get('row_id')}"
    out["source_row_id"] = row.get("row_id")
    out["expected_enabled_loss"] = "edit_localization_ce"
    out["source_skill_area"] = "edit_localization"
    out["locked_guard_refresh_stage"] = NAME
    out["authority"] = dict(AUTHORITY_CLOSED)
    anti = out.get("anti_cheat") if isinstance(out.get("anti_cheat"), dict) else {}
    anti["stage9961_recovery_reason"] = reason
    anti["stage9961_root_family"] = base_root
    out["anti_cheat"] = anti
    out["curriculum_priority_weight"] = weight
    out["curriculum_refresh_family"] = reason
    out["curriculum_refresh_scope"] = "blended_multilingual_edit_localization_weak_language_recovery"
    return out


def _root_stats() -> tuple[dict[str, dict[str, int]], dict[str, str]]:
    manifest_rows = read_jsonl(SOURCE_MANIFEST)
    rows_100m = read_jsonl(ROWS_100M)
    gemma_rows = {str(row.get("row_id") or ""): row for row in read_jsonl(ROWS_GEMMA)}
    root_lang: dict[str, str] = {
        _base_root(str(row.get("row_id") or "")): str(row.get("language_family") or "")
        for row in manifest_rows
        if str(row.get("split") or "") == "train"
    }
    stats: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows_100m:
        row_id = str(row.get("row_id") or "")
        base_root = _base_root(row_id)
        gemma = gemma_rows.get(row_id, {})
        if bool(row.get("correct")) and not bool(gemma.get("correct")):
            stats[base_root]["hundred_m_advantage"] += 1
        elif not bool(row.get("correct")) and bool(gemma.get("correct")):
            stats[base_root]["gemma_advantage"] += 1
        elif not bool(row.get("correct")):
            stats[base_root]["hundred_m_miss"] += 1
        else:
            stats[base_root]["both_correct"] += 1
    return {root: dict(counter) for root, counter in stats.items()}, root_lang


def _select_roots(stats: dict[str, dict[str, int]], root_lang: dict[str, str]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    rust_candidates: list[tuple[str, int]] = []
    for root, counter in stats.items():
        lang = root_lang.get(root, "unknown")
        gemma_adv = int(counter.get("gemma_advantage", 0))
        miss = int(counter.get("hundred_m_miss", 0))
        hm_adv = int(counter.get("hundred_m_advantage", 0))
        if lang in WEAK_LANGS and (gemma_adv > 0 or miss > 0):
            reason = "gemma_advantage_recovery" if gemma_adv > 0 else "hundred_m_miss_recovery"
            weight = 4 if gemma_adv > 0 else 3
            selected[root] = {"language_family": lang, "reason": reason, "weight": weight}
        elif lang == "rust" and hm_adv > 0 and miss == 0 and gemma_adv == 0:
            rust_candidates.append((root, hm_adv))
    rust_candidates.sort(key=lambda item: (-item[1], item[0]))
    for root, _ in rust_candidates[:RUST_ANCHORS]:
        selected[root] = {"language_family": "rust", "reason": "rust_anchor_preserve_winning_pattern", "weight": 1}
    return selected


def build_rows() -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    manifest_rows = read_jsonl(SOURCE_MANIFEST)
    stats, root_lang = _root_stats()
    selected_roots = _select_roots(stats, root_lang)
    failures: list[str] = []
    selected_rows: list[dict[str, Any]] = []
    root_counts = Counter()
    row_counts = Counter()
    split_counts = Counter()
    reason_counts = Counter()
    language_counts = Counter()
    weight_sum = 0

    for row in manifest_rows:
        base_root = _base_root(str(row.get("row_id") or ""))
        meta = selected_roots.get(base_root)
        if not meta:
            continue
        normalized = _normalize_row(
            row,
            reason=str(meta["reason"]),
            weight=int(meta["weight"]),
            base_root=base_root,
        )
        selected_rows.append(normalized)
        row_counts[str(meta["language_family"])] += 1
        split_counts[str(row.get("split") or "")] += 1
        reason_counts[str(meta["reason"])] += 1
        language_counts[str(meta["language_family"])] += 1
        weight_sum += int(meta["weight"])

    for root, meta in selected_roots.items():
        root_counts[str(meta["language_family"])] += 1

    if root_counts.get("python", 0) != 3:
        failures.append("python_root_count_not_3")
    if root_counts.get("c_cpp", 0) != 5:
        failures.append("c_cpp_root_count_not_5")
    if root_counts.get("web_js_ts_html", 0) != 6:
        failures.append("web_root_count_not_6")
    if root_counts.get("rust", 0) != 2:
        failures.append("rust_anchor_root_count_not_2")
    if split_counts.get("train", 0) != 16 or split_counts.get("eval", 0) != 16 or split_counts.get("strict_eval", 0) != 16:
        failures.append("split_counts_not_16_each")

    audit = {
        "rows": len(selected_rows),
        "language_root_counts": dict(sorted(root_counts.items())),
        "language_row_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "weight_sum": weight_sum,
    }
    return selected_rows, audit, failures


def compile_packet(rows: list[dict[str, Any]]) -> dict[str, Any]:
    locked_source_ids = load_locked_source_ids_from_exclusions(LOCKED_EXCLUSIONS)
    buckets, card = compile_rows(
        rows,
        allow_decoder=False,
        allow_denoise=False,
        allow_runtime=False,
        require_recovered_gates=True,
        locked_source_ids=locked_source_ids,
    )
    COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    for objective, bucket_rows in buckets.items():
        write_jsonl(COMPILED_DIR / f"{objective}.jsonl", bucket_rows)
    (COMPILED_DIR / "compile_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return card


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows, audit_metrics, failures = build_rows()
    write_jsonl(MANIFEST, rows)
    compile_card = compile_packet(rows)
    audit = {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            **audit_metrics,
            "compiler_gate_rejected_rows": compile_card.get("gate_rejected_rows"),
            "compiler_locked_source_exclusion_rows": compile_card.get("locked_source_exclusion_rows"),
            "compiler_loss_counts": compile_card.get("loss_counts"),
        },
        "training_recommendation": {
            "mix_strategy": "blend this packet into the next 100M edit-localization cycle so weak-language root families are replayed with higher priority while rust winning patterns stay anchored.",
            "focus_languages": ["python", "c_cpp", "web_js_ts_html"],
            "anchor_language": "rust",
            "why": "the current blended same-manifest run still loses on python and c_cpp overall and only partially recovers web_js_ts_html.",
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    if compile_card.get("gate_rejected_rows") != 0:
        audit["failures"].append("compiler_gate_rejected_rows_nonzero")
    if compile_card.get("locked_source_exclusion_rows") != 0:
        audit["failures"].append("compiler_locked_source_exclusion_rows_nonzero")
    audit["passed"] = not audit["failures"]
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = (
        "Blend this weak-language recovery packet into the next valid 100M edit-localization cycle, then rerun the same-manifest blended comparison to see whether python and c_cpp recover without giving back the web gains."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {
            "manifest": display(MANIFEST),
            "compiled_dir": display(COMPILED_DIR),
            "compile_card": display(COMPILED_DIR / "compile_card.json"),
            "audit": display(AUDIT),
            "doc": display(DOC),
        },
        "decision": "Built a blended weak-language recovery packet from the real stage9950/stage9953 same-manifest misses, targeting python, c_cpp, and web_js_ts_html root families while preserving two rust anchor families that already beat Gemma.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9961 Blended Weak-Language Recovery Packet",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{audit['metrics']['rows']}`",
        f"Language root counts: `{audit['metrics']['language_root_counts']}`",
        f"Split counts: `{audit['metrics']['split_counts']}`",
        f"Reason counts: `{audit['metrics']['reason_counts']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": audit["metrics"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
