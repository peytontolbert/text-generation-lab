#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9854
NAME = "stage9854_multisurface_abstention_honesty_manifests"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PATCH_SOURCE = ROOT / "runs/local/artifacts/stage9735_multilingual_patch_operator_label_aligned_package/multilingual_patch_operator_label_aligned.jsonl"
VERIFIER_SOURCE = ROOT / "runs/local/artifacts/stage9738_multilingual_verifier_repair_label_aligned_package/multilingual_verifier_repair_label_aligned.jsonl"
PATCH_AUDIT = ROOT / "runs/local/artifacts/stage9776_patch_operator_evidence_sufficiency_audit/patch_operator_evidence_sufficiency_audit.json"
VERIFIER_AUDIT = ROOT / "runs/local/artifacts/stage9777_verifier_repair_evidence_sufficiency_audit/verifier_repair_evidence_sufficiency_audit.json"
PATCH_MANIFEST = OUT_DIR / "multilingual_patch_operator_abstention_honesty.jsonl"
VERIFIER_MANIFEST = OUT_DIR / "multilingual_verifier_repair_abstention_honesty.jsonl"
AUDIT = OUT_DIR / "multisurface_abstention_honesty_manifests.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MULTISURFACE_ABSTENTION_HONESTY_MANIFESTS_STAGE9854.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
ABSTAIN_LABEL = "ABSTAIN_INSUFFICIENT_EVIDENCE"
PATCH_FIELD = "patch_operator"
VERIFIER_FIELD = "verifier_repair_action"
PATCH_PLAN = "abstain because visible patch-operator evidence is insufficient to distinguish a concrete action honestly"
VERIFIER_PLAN = "abstain because visible verifier evidence is insufficient to distinguish a concrete repair action honestly"


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


def _assert_collapsed(audit: dict[str, Any], name: str) -> list[str]:
    failures: list[str] = []
    if audit.get("passed") is not True:
        failures.append(f"{name}_audit_not_passed")
    if int(audit.get("collapsed_safe_bucket_count") or 0) != int(audit.get("bucket_count") or -1):
        failures.append(f"{name}_safe_buckets_not_fully_collapsed")
    if int(audit.get("separable_only_with_leaky_fields_bucket_count") or 0) != int(audit.get("bucket_count") or -1):
        failures.append(f"{name}_labels_not_leaky_only")
    return failures


def _rewrite_patch_row(row: dict[str, Any]) -> dict[str, Any]:
    cloned = json.loads(json.dumps(row))
    clean = cloned.get("clean_state") if isinstance(cloned.get("clean_state"), dict) else {}
    clean[PATCH_FIELD] = ABSTAIN_LABEL
    clean["action_sequence"] = [ABSTAIN_LABEL]
    clean["file_plan"] = PATCH_PLAN
    cloned["clean_state"] = clean
    cloned["abstention_honesty_stage"] = STAGE
    cloned["abstention_honesty_surface"] = "patch_operator"
    cloned["abstention_honesty_reason"] = "safe evidence signature collapses while labels remain separable only through label-shaped fields"
    return cloned


def _rewrite_verifier_row(row: dict[str, Any]) -> dict[str, Any]:
    cloned = json.loads(json.dumps(row))
    clean = cloned.get("clean_state") if isinstance(cloned.get("clean_state"), dict) else {}
    clean[VERIFIER_FIELD] = ABSTAIN_LABEL
    clean["action_sequence"] = [ABSTAIN_LABEL]
    clean["file_plan"] = VERIFIER_PLAN
    cloned["clean_state"] = clean
    cloned["abstention_honesty_stage"] = STAGE
    cloned["abstention_honesty_surface"] = "verifier_repair"
    cloned["abstention_honesty_reason"] = "safe evidence signature collapses while labels remain separable only through label-shaped fields"
    return cloned


def _surface_metrics(rows: list[dict[str, Any]], clean_key: str) -> dict[str, Any]:
    labels = Counter(str(((row.get("clean_state") or {}).get(clean_key) or "")) for row in rows)
    splits = Counter(str(row.get("split") or "") for row in rows)
    langs = Counter(str(row.get("language_family") or "") for row in rows)
    return {
        "rows": len(rows),
        "label_counts": dict(sorted(labels.items())),
        "split_counts": dict(sorted(splits.items())),
        "language_counts": dict(sorted(langs.items())),
    }


def build_manifests() -> dict[str, Any]:
    patch_rows = load_jsonl(PATCH_SOURCE)
    verifier_rows = load_jsonl(VERIFIER_SOURCE)
    patch_audit = load_json(PATCH_AUDIT)
    verifier_audit = load_json(VERIFIER_AUDIT)

    failures = [
        *_assert_collapsed(patch_audit, "patch_operator"),
        *_assert_collapsed(verifier_audit, "verifier_repair"),
    ]

    rewritten_patch = [_rewrite_patch_row(row) for row in patch_rows]
    rewritten_verifier = [_rewrite_verifier_row(row) for row in verifier_rows]
    write_jsonl(PATCH_MANIFEST, rewritten_patch)
    write_jsonl(VERIFIER_MANIFEST, rewritten_verifier)

    patch_metrics = _surface_metrics(rewritten_patch, PATCH_FIELD)
    verifier_metrics = _surface_metrics(rewritten_verifier, VERIFIER_FIELD)
    if list(patch_metrics["label_counts"].keys()) != [ABSTAIN_LABEL]:
        failures.append("patch_operator_not_fully_rewritten_to_abstain")
    if list(verifier_metrics["label_counts"].keys()) != [ABSTAIN_LABEL]:
        failures.append("verifier_repair_not_fully_rewritten_to_abstain")

    return {
        "passed": not failures,
        "failures": failures,
        "patch_operator": {
            "source_manifest": str(PATCH_SOURCE.relative_to(ROOT)),
            "source_audit": str(PATCH_AUDIT.relative_to(ROOT)),
            "rewritten_manifest": str(PATCH_MANIFEST.relative_to(ROOT)),
            "metrics": patch_metrics,
        },
        "verifier_repair": {
            "source_manifest": str(VERIFIER_SOURCE.relative_to(ROOT)),
            "source_audit": str(VERIFIER_AUDIT.relative_to(ROOT)),
            "rewritten_manifest": str(VERIFIER_MANIFEST.relative_to(ROOT)),
            "metrics": verifier_metrics,
        },
        "claim": (
            "The current multilingual patch-operator and verifier-repair packages should not be trained as forced action selection. "
            "Given the present observable evidence, the honest target is abstention."
        ),
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_manifests()
    write_json(AUDIT, built)
    next_step = (
        "Use these honesty manifests as the upstream replacement for additional patch-operator and verifier-repair sweeps, then run targeted 100M probes to measure whether explicit abstention preserves multilingual advantage without forcing guessed actions."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "failures": built["failures"],
            "patch_rows": built["patch_operator"]["metrics"]["rows"],
            "verifier_rows": built["verifier_repair"]["metrics"]["rows"],
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "patch_manifest": str(PATCH_MANIFEST.relative_to(ROOT)),
            "verifier_manifest": str(VERIFIER_MANIFEST.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Rewrote the structurally collapsed multilingual patch-operator and verifier-repair training packets into abstention-only honesty manifests so the next hard-surface training cycle can stop rewarding forced guesses on underspecified rows.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9854 Multisurface Abstention Honesty Manifests",
                "",
                f"Passed: `{built['passed']}`",
                f"Patch rows rewritten: `{built['patch_operator']['metrics']['rows']}`",
                f"Verifier rows rewritten: `{built['verifier_repair']['metrics']['rows']}`",
                "",
                "This stage turns the evidence-sufficiency audits into an executable training artifact: the current patch-operator and verifier-repair surfaces are relabeled to abstain because their visible evidence does not honestly distinguish concrete actions.",
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
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "patch_rows": built["patch_operator"]["metrics"]["rows"],
                "verifier_rows": built["verifier_repair"]["metrics"]["rows"],
                "failures": built["failures"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
