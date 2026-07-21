#!/usr/bin/env python3
"""Build a repo-wide atlas of failed-stage lessons for takeover handoff."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUM = ROOT / "runs" / "summaries"
ART = ROOT / "runs" / "local" / "artifacts" / "stage12120_failed_stage_lessons_atlas"
STAGE = 12120
NAME = "stage12120_failed_stage_lessons_atlas"

FAIL_NAME_MARKERS = (
    "failure",
    "failed",
    "blocker",
    "reject",
    "rejected",
    "regression",
    "gap",
    "shortcut",
    "leak",
    "quarantine",
    "collapse",
    "mismatch",
    "drift",
    "overfit",
    "not_quality",
)

REJECT_DECISION_MARKERS = (
    "reject",
    "rejected",
    "do_not",
    "blocked",
    "blocker",
    "quarantine",
    "keep_stage",
    "not_quality",
    "failure",
    "failed",
    "regression",
    "overfit",
)

LESSON_KEYS = {
    "lesson",
    "failure_lesson",
    "lessons",
    "failure_lessons",
    "failure_mode",
    "failure_modes",
    "failure_pattern",
    "failure_patterns",
    "finding",
    "findings",
    "key_findings",
    "root_cause",
    "root_causes",
    "regression",
    "regressions",
    "blocker",
    "blockers",
    "failure",
    "failures",
}

CATEGORY_RULES = [
    (
        "shared_training_interference",
        ("shared", "interfere", "interference", "regress", "overcorrect", "preservation", "protected"),
    ),
    (
        "schema_renderer_option_geometry",
        ("schema", "renderer", "option", "geometry", "label", "canonical", "permutation"),
    ),
    (
        "leakage_and_lineage",
        ("leak", "lineage", "same-root", "same root", "overlap", "heldout", "train overlap", "shortcut"),
    ),
    (
        "evidence_verifier_mislabeled",
        ("verifier", "selected-test", "selected test", "build-only", "build only", "static", "not exercised"),
    ),
    (
        "decoder_generation_mismatch",
        ("bounded decoder", "decoder ce", "answer letter", "answer-letter", "generation", "repetition", "eos"),
    ),
    (
        "web_transfer_gap",
        ("web", "openhands", "llama", "html", "typescript", "javascript"),
    ),
    (
        "data_scale_quality_gap",
        ("more rows", "row count", "same roots", "same-family", "support only", "train support", "coverage", "scale"),
    ),
    (
        "runtime_training_artifact_gap",
        ("runtime", "saved", "checkpoint", "train loss", "eval drops", "bundle", "harness"),
    ),
]


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text())
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def stage_num(path: Path, obj: dict[str, Any]) -> int | None:
    raw = obj.get("stage")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    match = re.search(r"stage(\d+)", path.name)
    return int(match.group(1)) if match else None


def compact_text(value: Any, limit: int = 420) -> str | None:
    if value is None or value is False:
        return None
    if isinstance(value, str):
        text = " ".join(value.split())
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    elif isinstance(value, list):
        parts = [compact_text(item, 180) for item in value[:8]]
        text = "; ".join(part for part in parts if part)
    elif isinstance(value, dict):
        parts = []
        for key, item in list(value.items())[:10]:
            item_text = compact_text(item, 160)
            if item_text:
                parts.append(f"{key}: {item_text}")
        text = "; ".join(parts)
    else:
        return None
    if not text:
        return None
    return text[: limit - 3] + "..." if len(text) > limit else text


def informative_text(text: str | None, field_path: str = "") -> bool:
    if not text:
        return False
    stripped = text.strip()
    if stripped.lower() in {"true", "false", "none", "null"}:
        return False
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", stripped):
        return False
    if len(stripped) < 12 and "lesson" not in field_path.lower():
        return False
    return True


def walk_lesson_fields(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            key_l = str(key).lower()
            if key_l in LESSON_KEYS or any(marker in key_l for marker in ("lesson", "failure", "regression", "blocker")):
                text = compact_text(item)
                if informative_text(text, path):
                    found.append((path, text))
            if isinstance(item, (dict, list)):
                found.extend(walk_lesson_fields(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value[:80]):
            if isinstance(item, (dict, list)):
                found.extend(walk_lesson_fields(item, f"{prefix}[{index}]"))
    return found


def text_blob(obj: dict[str, Any]) -> str:
    pieces = []
    for key in ("stage_name", "decision", "lesson", "failure_lesson", "next_best_step"):
        val = compact_text(obj.get(key), 800)
        if val:
            pieces.append(val)
    for key in ("findings", "key_findings", "failures", "regressions", "blockers"):
        val = compact_text(obj.get(key), 800)
        if val:
            pieces.append(val)
    return " ".join(pieces).lower()


def classify(obj: dict[str, Any], path: Path) -> tuple[bool, list[str], list[str]]:
    name = str(obj.get("stage_name") or path.stem).lower()
    decision = str(obj.get("decision") or "").lower()
    blob = text_blob(obj)
    reasons: list[str] = []
    categories: list[str] = []

    if obj.get("passed") is False:
        reasons.append("passed_false")
    if any(marker in name for marker in FAIL_NAME_MARKERS):
        reasons.append("failure_marker_in_stage_name")
    if any(marker in decision for marker in REJECT_DECISION_MARKERS):
        reasons.append("reject_or_block_decision")
    if "score" in blob and any(marker in blob for marker in ("below", "drops", "drop", "regress", "behind")):
        reasons.append("score_drop_or_below_baseline")
    if walk_lesson_fields(obj):
        reasons.append("explicit_lesson_or_failure_field")

    for category, terms in CATEGORY_RULES:
        if any(term in blob for term in terms):
            categories.append(category)
    if not categories and reasons:
        categories.append("uncategorized_failure_or_blocker")

    return bool(reasons), sorted(set(reasons)), sorted(set(categories))


def strongest_lesson(obj: dict[str, Any], path: Path) -> str:
    fields = walk_lesson_fields(obj)
    for wanted in ("lesson", "failure_lesson"):
        for field_path, text in fields:
            if field_path == wanted:
                return text
    if fields:
        for _, text in fields:
            if informative_text(text):
                return text
    decision = compact_text(obj.get("decision"), 260)
    next_step = compact_text(obj.get("next_best_step"), 220)
    if decision and next_step:
        return f"{decision}. Next: {next_step}"
    if decision:
        return decision
    return str(obj.get("stage_name") or path.stem)


def lesson_instruction(category: str) -> str:
    return {
        "shared_training_interference": "Use routed or task-specific heads first; never promote a run that fixes one transition task while damaging protected or sibling task metrics.",
        "schema_renderer_option_geometry": "Freeze the renderer and semantic option contract before training; require option-permutation stability before headline claims.",
        "leakage_and_lineage": "Treat root lineage and same-family overlap as hard admission gates; same-root wins are support only, not heldout progress.",
        "evidence_verifier_mislabeled": "Separate selected-test, build/static, not-exercised, and insufficient-evidence scopes in row labels and audits.",
        "decoder_generation_mismatch": "Do not infer maintainer ability from decoder CE or answer-letter loss; evaluate the bounded scorer path actually used by the product.",
        "web_transfer_gap": "For web rows, verify schema/renderer parity and OpenHands/Llama-style heldout behavior before adding more support rows.",
        "data_scale_quality_gap": "Scale roots and verifier-backed evidence, not template variants; rows without new roots or new failure mechanisms are weak support.",
        "runtime_training_artifact_gap": "Promotion requires saved runtime bundles, same-manifest eval, protected gates, and retained artifacts; train loss is diagnostic only.",
        "uncategorized_failure_or_blocker": "Read the cited stage before acting; it was classified as a failure/blocker but needs human interpretation.",
    }[category]


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    total = 0
    for path in sorted(SUM.glob("stage*.json")):
        obj = read_json(path)
        if not obj:
            continue
        num = stage_num(path, obj)
        if num == STAGE:
            continue
        total += 1
        is_failure, reasons, categories = classify(obj, path)
        if not is_failure:
            continue
        fields = walk_lesson_fields(obj)
        records.append(
            {
                "stage": num,
                "stage_name": obj.get("stage_name") or path.stem,
                "summary_path": str(path.relative_to(ROOT)),
                "decision": obj.get("decision"),
                "passed": obj.get("passed"),
                "failure_reasons": reasons,
                "lesson_categories": categories,
                "primary_lesson": strongest_lesson(obj, path),
                "explicit_lesson_fields": [
                    {"field": field, "text": text} for field, text in fields[:12]
                ],
            }
        )
    records.sort(key=lambda row: ((row["stage"] is None), row["stage"] or -1, row["stage_name"]))

    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        for category in record["lesson_categories"]:
            by_category[category].append(record)

    category_cards = []
    for category in sorted(by_category):
        rows = by_category[category]
        examples = sorted(rows, key=lambda row: row["stage"] or -1)[-8:]
        category_cards.append(
            {
                "category": category,
                "stage_count": len(rows),
                "instruction": lesson_instruction(category),
                "recent_examples": [
                    {
                        "stage": row["stage"],
                        "stage_name": row["stage_name"],
                        "lesson": row["primary_lesson"],
                        "summary_path": row["summary_path"],
                    }
                    for row in examples
                ],
            }
        )

    reason_counts = Counter(reason for row in records for reason in row["failure_reasons"])
    category_counts = Counter(category for row in records for category in row["lesson_categories"])
    explicit_count = sum(1 for row in records if row["explicit_lesson_fields"])

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "decision": "failed_stage_lessons_atlas_ready",
        "created_at_utc": "2026-07-15T04:20:00Z",
        "scanned_summary_files": total,
        "failure_or_blocker_stage_records": len(records),
        "records_with_explicit_lesson_fields": explicit_count,
        "records_inferred_from_name_or_decision": len(records) - explicit_count,
        "failure_reason_counts": dict(sorted(reason_counts.items())),
        "lesson_category_counts": dict(sorted(category_counts.items())),
        "artifacts": {
            "atlas_json": str((ART / "failed_stage_lessons_atlas.json").relative_to(ROOT)),
            "atlas_jsonl": str((ART / "failed_stage_lessons_records.jsonl").relative_to(ROOT)),
            "brief_md": str((ART / "enhanced_failed_stage_lessons_for_subagents.md").relative_to(ROOT)),
            "summary_mirror": f"runs/summaries/{NAME}.json",
        },
        "claim_boundary": [
            "This is a failure-lesson extraction and classification artifact, not model progress.",
            "Records without explicit lesson fields are inferred from stage names, decisions, and failure markers.",
            "Use cited summary paths before making irreversible training/eval decisions.",
        ],
        "category_cards": category_cards,
    }

    (ART / "failed_stage_lessons_records.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in records) + "\n"
    )
    (ART / "failed_stage_lessons_atlas.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (ROOT / "runs" / "summaries" / f"{NAME}.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Enhanced Lessons From Failed Stages",
        "",
        f"Scanned `{total}` stage summaries and classified `{len(records)}` failure, blocker, regression, leakage, shortcut, gap, or rejection records.",
        f"`{explicit_count}` records had explicit lesson/failure fields; `{len(records) - explicit_count}` were inferred from names, decisions, and failure markers.",
        "",
        "Use this as the subagent babysitting checklist. It upgrades the short Stage12119 lesson section from eight bullets into cited failure classes.",
        "",
        "## Non-Negotiable Lessons",
    ]
    for card in category_cards:
        lines.extend(
            [
                "",
                f"### {card['category']}",
                "",
                f"- Count: `{card['stage_count']}` classified records.",
                f"- Instruction: {card['instruction']}",
                "- Recent cited examples:",
            ]
        )
        for example in card["recent_examples"][-5:]:
            lines.append(
                f"  - `stage{example['stage']}` `{example['stage_name']}`: {example['lesson']} ({example['summary_path']})"
            )
    lines.extend(
        [
            "",
            "## Immediate Subagent Guardrails",
            "",
            "- Before assigning work, name which failure category the work is meant to fix.",
            "- Stop any line that adds rows without adding root-disjoint verifier-backed evidence.",
            "- Stop any line that reports train loss without same-manifest heldout and protected-gate results.",
            "- Treat selected-test evidence, build/static evidence, not-exercised evidence, and insufficient evidence as separate labels.",
            "- Require option-permutation stability for any bounded candidate/scorer comparison.",
            "- Preserve Stage11507 compact gates and Stage11924 transition baseline unless an explicitly routed product claim is being made.",
            "- Do not let subagents self-admit rows; they produce candidate JSONL plus logs, and the deterministic audit admits or rejects.",
        ]
    )
    (ART / "enhanced_failed_stage_lessons_for_subagents.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"summary": summary["artifacts"]["summary_mirror"], "records": len(records)}, indent=2))


if __name__ == "__main__":
    main()
