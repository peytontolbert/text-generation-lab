#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9842
NAME = "stage9842_permuted_choice_decoy_coverage_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "permuted_choice_decoy_coverage_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PERMUTED_CHOICE_DECOY_COVERAGE_AUDIT_STAGE9842.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
STAGE9833_AUDIT = ROOT / "runs/local/artifacts/stage9833_permuted_choice_execution_manifest/permuted_choice_execution_manifest_audit.json"
STAGE9833_MANIFEST = ROOT / "runs/local/artifacts/stage9833_permuted_choice_execution_manifest/permuted_choice_execution_manifest.jsonl"
STAGE9839_ROWS = ROOT / "runs/local/artifacts/stage9839_direct_permuted_choice_exec/row_field_logits.jsonl"
STAGE9840_COMPARISON = ROOT / "runs/local/artifacts/stage9840_permuted_choice_per_language_gemma_comparison/permuted_choice_per_language_gemma_comparison.json"
STAGE9835_GEMMA_ROWS = ROOT / "runs/local/artifacts/stage9835_permuted_choice_gemma_comparison/permuted_choice_gemma_rows.jsonl"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


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


def root_row_id(row_id: str) -> str:
    return row_id.split("::", 1)[0]


def expected_counterfactual_role(split: str) -> str | None:
    if split == "eval":
        return "positive_original"
    if split == "strict_eval":
        return "mixed_replay"
    return None


def index_manifest(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        split = str(row.get("split") or "")
        lang = str(row.get("language_family") or "")
        root = root_row_id(str(row.get("row_id") or ""))
        out[(lang, split, root)] = row
    return out


def index_100m_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        if str(row.get("field") or "") != "edit_localization":
            continue
        cell_key = str(row.get("cell_key") or "")
        lang = cell_key.split("::", 1)[0]
        split = str(row.get("split") or "")
        root = root_row_id(str(row.get("row_id") or ""))
        out[(lang, split, root)] = row
    return out


def index_gemma_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        lang = str(row.get("language_family") or "")
        split = str(row.get("split") or "")
        root = root_row_id(str(row.get("row_id") or ""))
        out[(lang, split, root)] = row
    return out


def exact_score(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    return sum(1 for row in rows if bool(row.get("correct"))) / len(rows)


def build_language_record(
    lang: str,
    *,
    manifest_index: dict[tuple[str, str, str], dict[str, Any]],
    hundred_index: dict[tuple[str, str, str], dict[str, Any]],
    gemma_index: dict[tuple[str, str, str], dict[str, Any]],
    bucket_cards: dict[str, Any],
    comparison_9840: dict[str, Any],
) -> dict[str, Any]:
    roots = sorted({root for (_lang, split, root) in manifest_index if _lang == lang and split == "eval"})
    pairs: list[dict[str, Any]] = []
    failures: list[str] = []

    for root in roots:
        manifest_eval = manifest_index.get((lang, "eval", root))
        manifest_strict = manifest_index.get((lang, "strict_eval", root))
        hundred_eval = hundred_index.get((lang, "eval", root))
        hundred_strict = hundred_index.get((lang, "strict_eval", root))
        gemma_eval = gemma_index.get((lang, "eval", root))
        gemma_strict = gemma_index.get((lang, "strict_eval", root))
        if not all([manifest_eval, manifest_strict, hundred_eval, hundred_strict, gemma_eval, gemma_strict]):
            failures.append(f"missing_pair:{lang}:{root}")
            continue

        strict_wrong_label = str(manifest_strict.get("counterfactual_wrong_label") or "")
        pairs.append(
            {
                "root_row_id": root,
                "expected_label": hundred_eval.get("target"),
                "strict_wrong_label": strict_wrong_label,
                "counterfactual_roles": {
                    "eval": str(manifest_eval.get("counterfactual_role") or ""),
                    "strict_eval": str(manifest_strict.get("counterfactual_role") or ""),
                },
                "hundred_m": {
                    "eval_pred": hundred_eval.get("pred"),
                    "eval_correct": bool(hundred_eval.get("correct")),
                    "strict_pred": hundred_strict.get("pred"),
                    "strict_correct": bool(hundred_strict.get("correct")),
                    "prediction_changed": hundred_eval.get("pred") != hundred_strict.get("pred"),
                    "followed_wrong_label_on_strict": strict_wrong_label != "" and hundred_strict.get("pred") == strict_wrong_label,
                },
                "gemma": {
                    "eval_pred": gemma_eval.get("predicted_label"),
                    "eval_correct": bool(gemma_eval.get("correct")),
                    "strict_pred": gemma_strict.get("predicted_label"),
                    "strict_correct": bool(gemma_strict.get("correct")),
                    "prediction_changed": gemma_eval.get("predicted_label") != gemma_strict.get("predicted_label"),
                    "followed_wrong_label_on_strict": strict_wrong_label != "" and gemma_strict.get("predicted_label") == strict_wrong_label,
                },
            }
        )

    hundred_eval_rows = [pair["hundred_m"] for pair in pairs]
    gemma_eval_rows = [pair["gemma"] for pair in pairs]
    hundred_eval_exact = exact_score([{"correct": row["eval_correct"]} for row in hundred_eval_rows])
    hundred_strict_exact = exact_score([{"correct": row["strict_correct"]} for row in hundred_eval_rows])
    gemma_eval_exact = exact_score([{"correct": row["eval_correct"]} for row in gemma_eval_rows])
    gemma_strict_exact = exact_score([{"correct": row["strict_correct"]} for row in gemma_eval_rows])

    def _rate(rows: list[dict[str, Any]], key: str) -> float | None:
        if not rows:
            return None
        return sum(1 for row in rows if bool(row[key])) / len(rows)

    return {
        "language_family": lang,
        "paired_root_count": len(pairs),
        "pair_failures": failures,
        "packet_structure": {
            "eval_counterfactual_role": expected_counterfactual_role("eval"),
            "strict_eval_counterfactual_role": expected_counterfactual_role("strict_eval"),
            "built_in_decoy_slice_present": True,
            "built_in_ablation_slice_present": False,
            "built_in_causal_flip_slice_present": False,
            "stage9833_bucket_cards": {
                "eval": bucket_cards.get(f"{lang}:eval"),
                "strict_eval": bucket_cards.get(f"{lang}:strict_eval"),
            },
        },
        "hundred_m": {
            "eval_exact": hundred_eval_exact,
            "strict_eval_exact": hundred_strict_exact,
            "decoy_exact_delta": None if hundred_eval_exact is None or hundred_strict_exact is None else hundred_strict_exact - hundred_eval_exact,
            "prediction_changed_rate": _rate(hundred_eval_rows, "prediction_changed"),
            "wrong_label_follow_rate_on_strict": _rate(hundred_eval_rows, "followed_wrong_label_on_strict"),
            "paired_both_correct_rate": _rate(
                [{"paired_both_correct": row["eval_correct"] and row["strict_correct"]} for row in hundred_eval_rows],
                "paired_both_correct",
            ),
        },
        "gemma": {
            "eval_exact": gemma_eval_exact,
            "strict_eval_exact": gemma_strict_exact,
            "decoy_exact_delta": None if gemma_eval_exact is None or gemma_strict_exact is None else gemma_strict_exact - gemma_eval_exact,
            "prediction_changed_rate": _rate(gemma_eval_rows, "prediction_changed"),
            "wrong_label_follow_rate_on_strict": _rate(gemma_eval_rows, "followed_wrong_label_on_strict"),
            "paired_both_correct_rate": _rate(
                [{"paired_both_correct": row["eval_correct"] and row["strict_correct"]} for row in gemma_eval_rows],
                "paired_both_correct",
            ),
        },
        "pair_rows": pairs,
        "comparison_stage9840": {
            "eval_verdict": comparison_9840.get("comparisons", {}).get(f"{lang}:eval", {}).get("verdict"),
            "strict_eval_verdict": comparison_9840.get("comparisons", {}).get(f"{lang}:strict_eval", {}).get("verdict"),
        },
        "coverage_gaps": [
            "critical_evidence_ablation_not_executed_on_stage9839_packet",
            "causal_flip_not_executed_on_stage9839_packet",
        ],
    }


def build_audit() -> dict[str, Any]:
    manifest_rows = load_jsonl(STAGE9833_MANIFEST)
    hundred_rows = load_jsonl(STAGE9839_ROWS)
    gemma_rows = load_jsonl(STAGE9835_GEMMA_ROWS)
    stage9833_audit = load_json(STAGE9833_AUDIT)
    comparison_9840 = load_json(STAGE9840_COMPARISON)

    manifest_index = index_manifest(manifest_rows)
    hundred_index = index_100m_rows(hundred_rows)
    gemma_index = index_gemma_rows(gemma_rows)
    bucket_cards = stage9833_audit.get("bucket_cards") if isinstance(stage9833_audit.get("bucket_cards"), dict) else {}

    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for lang in LANGS:
        record = build_language_record(
            lang,
            manifest_index=manifest_index,
            hundred_index=hundred_index,
            gemma_index=gemma_index,
            bucket_cards=bucket_cards,
            comparison_9840=comparison_9840,
        )
        if record["paired_root_count"] != 5:
            failures.append(f"unexpected_paired_root_count:{lang}:{record['paired_root_count']}")
        if record["pair_failures"]:
            failures.extend(record["pair_failures"])
        records.append(record)

    metrics = {
        "validated_languages": len(records),
        "paired_roots": sum(int(record["paired_root_count"]) for record in records),
        "built_in_decoy_languages": sum(1 for record in records if record["packet_structure"]["built_in_decoy_slice_present"] is True),
        "missing_ablation_languages": sum(1 for record in records if record["packet_structure"]["built_in_ablation_slice_present"] is False),
        "missing_causal_flip_languages": sum(1 for record in records if record["packet_structure"]["built_in_causal_flip_slice_present"] is False),
        "hundred_m_avg_decoy_exact_delta": sum(float(record["hundred_m"]["decoy_exact_delta"] or 0.0) for record in records) / len(records) if records else None,
        "gemma_avg_decoy_exact_delta": sum(float(record["gemma"]["decoy_exact_delta"] or 0.0) for record in records) / len(records) if records else None,
        "hundred_m_avg_wrong_label_follow_rate": sum(float(record["hundred_m"]["wrong_label_follow_rate_on_strict"] or 0.0) for record in records) / len(records) if records else None,
        "gemma_avg_wrong_label_follow_rate": sum(float(record["gemma"]["wrong_label_follow_rate_on_strict"] or 0.0) for record in records) / len(records) if records else None,
    }

    return {
        "passed": not failures,
        "failures": failures,
        "records": records,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use this direct decoy audit to update the stage9841 anti-cheat cards, then run fresh ablation and causal-flip executions on the same packet before making a stronger no-shortcuts claim."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Measured the stronger packet's built-in decoy slice directly from the real Stage9839 100M rows and Stage9835 Gemma rows, while explicitly marking ablation and causal-flip as missing coverage on this packet.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9842 Permuted-Choice Decoy Coverage Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Validated languages: `{audit['metrics']['validated_languages']}`",
                f"Paired roots: `{audit['metrics']['paired_roots']}`",
                f"Built-in decoy languages: `{audit['metrics']['built_in_decoy_languages']}`",
                f"Missing ablation languages: `{audit['metrics']['missing_ablation_languages']}`",
                f"Missing causal-flip languages: `{audit['metrics']['missing_causal_flip_languages']}`",
                "",
                "This stage scores the stronger packet's built-in decoy slice directly from the real 100M and Gemma outputs instead of pretending ablation and causal-flip evidence already exist.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": audit["metrics"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
