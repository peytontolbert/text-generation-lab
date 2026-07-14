#!/usr/bin/env python3
"""Render Stage11880 support rows into the same compact bounded-choice interface."""

from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11884
NAME = "stage11884_rendered_source_heldout_support_probe_package"
OUT = ART / NAME
SUMMARY = OUT / "rendered_source_heldout_support_probe_package.json"
MANIFEST = OUT / "rendered_source_heldout_support_probe_manifest.jsonl"
ADDED_ROWS = OUT / "rendered_source_heldout_support_added_train_rows.jsonl"

BASE_SUMMARY = ART / "stage11880_source_heldout_support_guarded_probe_package/source_heldout_support_guarded_probe_package.json"
BASE_MANIFEST = ART / "stage11880_source_heldout_support_guarded_probe_package/source_heldout_support_guarded_probe_manifest.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def row_split(row: dict[str, Any]) -> str:
    return str(row.get("split") or row.get("package_split") or "")


def row_root(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def compact_text(value: Any, limit: int = 520) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def render_evidence(row: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    ledger = row.get("evidence_ledger") if isinstance(row.get("evidence_ledger"), list) else []
    for item in ledger:
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("id") or "E??")
        kind = str(item.get("kind") or "evidence")
        summary = compact_text(item.get("summary") or item.get("text") or "", 360)
        if summary:
            lines.append(f"{evidence_id}: kind={kind}; summary={summary}")
        else:
            lines.append(f"{evidence_id}: kind={kind}")
    verifier = row.get("verifier_evidence") if isinstance(row.get("verifier_evidence"), dict) else {}
    if verifier:
        verifier_id = str(verifier.get("id") or "V01")
        kind = str(verifier.get("kind") or "verifier")
        result = str(verifier.get("result") or row.get("verifier_transition") or "")
        summary = compact_text(verifier.get("summary") or "", 360)
        rendered = f"{verifier_id}: kind={kind}"
        if result:
            rendered += f"; result={result}"
        if summary:
            rendered += f"; summary={summary}"
        lines.append(rendered)
    return lines


def render_options(row: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for opt in row.get("opaque_options") or []:
        if not isinstance(opt, dict):
            continue
        label = str(opt.get("label") or "").strip()
        if not label:
            continue
        role = str(opt.get("role") or opt.get("semantic_role") or "candidate")
        value = compact_text(opt.get("value") or label, 260)
        evidence_ids = opt.get("evidence_ids") if isinstance(opt.get("evidence_ids"), list) else []
        evidence = ",".join(str(item) for item in evidence_ids[:8])
        suffix = f"; evidence_ids={evidence}" if evidence else ""
        lines.append(f"{label}: role={role}; value={value}{suffix}")
    return lines


def render_prompt(row: dict[str, Any]) -> str:
    task = str(row.get("task_type") or "bounded_choice")
    language = str(row.get("language_family") or "unknown")
    repo = str(row.get("repo_family") or row.get("repo_id") or "unknown_repo")
    verifier_transition = str(row.get("verifier_transition") or "")
    parts = [
        "TASK",
        f"language: {language}",
        f"repo_family: {repo}",
        f"perspective: {task}",
        "instruction: choose the best candidate from the opaque options using only the observed evidence.",
    ]
    if verifier_transition:
        parts.append(f"observed_verifier_transition: {verifier_transition}")
    parts.append("")
    parts.append("OBSERVED_STATE")
    if row.get("selected_test_anchor"):
        parts.append("selected_test_anchor_present: true")
    if row.get("verifier_anchor"):
        parts.append("verifier_anchor_present: true")
    parts.append("")
    parts.append("SOURCE_AND_VERIFIER_EVIDENCE")
    evidence_lines = render_evidence(row)
    parts.extend(evidence_lines or ["E00: no additional evidence"])
    parts.append("")
    parts.append("CANDIDATES")
    parts.extend(render_options(row))
    parts.append("")
    parts.append("QUESTION")
    parts.append("Return only the option label.")
    prompt = "\n".join(parts)
    semantic = str(row.get("semantic_target_value") or row.get("target_value") or "")
    if semantic and semantic != "ABSTAIN_INSUFFICIENT_EVIDENCE" and "\nCANDIDATES\n" in prompt:
        before, after = prompt.split("\nCANDIDATES\n", 1)
        before = before.replace(semantic, "[candidate_value_redacted]")
        prompt = before + "\nCANDIDATES\n" + after
    return prompt


def normalize_support_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    prompt = render_prompt(out)
    out["prompt_text"] = prompt
    out["input_text"] = prompt
    label = str(out.get("bounded_choice_target_label") or out.get("target_label") or out.get("target_text") or "")
    out["bounded_choice_target_label"] = label
    out["target_label"] = label
    out["target_text"] = label
    out["decoder_text"] = label
    out["target"] = {
        "decoder_text": label,
        "bounded_choice_target_label": label,
        "semantic_value": out.get("semantic_target_value") or out.get("target_value"),
    }
    source = dict(out.get("standalone_projection_source") or {})
    source["opaque_options"] = out.get("opaque_options") or []
    source["rendering"] = "stage11884_canonical_support_renderer_v1"
    out["standalone_projection_source"] = source
    out["stage11884_rendered_support"] = True
    return out


def main() -> None:
    base_summary = read_json(BASE_SUMMARY)
    rows = read_jsonl(BASE_MANIFEST)
    rendered: list[dict[str, Any]] = []
    added: list[dict[str, Any]] = []
    for row in rows:
        if row.get("stage11880_support_source"):
            out = normalize_support_row(row)
            added.append(out)
            rendered.append(out)
        else:
            rendered.append(row)

    split_counts = Counter(row_split(row) for row in rendered)
    support_roots = {row_root(row) for row in added}
    empty_support_prompts = sum(1 for row in added if not str(row.get("prompt_text") or "").strip())
    prompt_lengths = [len(str(row.get("prompt_text") or "")) for row in added]
    option_counts = Counter(len(row.get("opaque_options") or []) for row in added)
    pre_options_leaks = []
    for row in added:
        prompt = str(row.get("prompt_text") or "")
        before_options = prompt.split("\nCANDIDATES\n", 1)[0]
        semantic = str(row.get("semantic_target_value") or row.get("target_value") or "")
        if semantic and semantic != "ABSTAIN_INSUFFICIENT_EVIDENCE" and semantic in before_options:
            pre_options_leaks.append(row.get("row_id"))

    write_jsonl(MANIFEST, rendered)
    write_jsonl(ADDED_ROWS, added)

    passed = (
        len(added) == 160
        and not empty_support_prompts
        and not pre_options_leaks
        and split_counts.get("eval", 0) == 23
        and split_counts.get("strict_eval", 0) == 23
    )
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": passed,
        "decision": "rendered_support_probe_package_ready" if passed else "rendered_support_probe_package_blocked",
        "base_package": rel(BASE_SUMMARY),
        "base_decision": base_summary.get("decision"),
        "row_counts": {
            "manifest_rows": len(rendered),
            "rendered_support_rows": len(added),
            "split_counts": dict(split_counts),
            "unique_support_roots": len(support_roots),
        },
        "renderer_audit": {
            "empty_support_prompts": empty_support_prompts,
            "option_count_distribution": dict(option_counts),
            "support_prompt_min_chars": min(prompt_lengths) if prompt_lengths else 0,
            "support_prompt_max_chars": max(prompt_lengths) if prompt_lengths else 0,
            "support_prompt_avg_chars": (sum(prompt_lengths) / len(prompt_lengths)) if prompt_lengths else 0,
            "pre_options_target_value_leak_rows": pre_options_leaks[:20],
            "pre_options_target_value_leak_count": len(pre_options_leaks),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "manifest": rel(MANIFEST),
            "added_rows": rel(ADDED_ROWS),
        },
        "claim_boundary": [
            "This repairs the Stage11880 support rendering interface; it does not change protected eval/strict rows.",
            "Stage11882 remains rejected and reproducible.",
            "Rendered support rows remain train-support-only, not source-heldout strict evidence.",
        ],
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "row_counts": artifact["row_counts"], "renderer_audit": artifact["renderer_audit"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
