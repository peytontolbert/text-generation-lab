#!/usr/bin/env python3
"""Audit subagent-produced Maintainer-400 pilot acquisition candidates."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
STAGE = 12117
NAME = "stage12117_maintainer_400_pilot_candidate_intake_audit"
IN_DIR = ART / "stage12117_maintainer_400_pilot_candidate_intake"
OUT = ART / NAME
SUMMARY = OUT / "maintainer_400_pilot_candidate_intake_audit.json"
MIRROR = SUM / f"{NAME}.json"
ADMITTED = OUT / "admitted_pilot_acquisition_targets.jsonl"
REJECTED = OUT / "rejected_pilot_acquisition_targets.jsonl"
MERGED = OUT / "merged_pilot_candidate_intake.jsonl"

VALID_LANGS = {"python", "rust", "c_cpp", "web_js_ts_html"}
VALID_VERIFIER_TYPES = {"selected_test_anchor", "build_config_anchor", "static_compile_anchor", "dependency_resolution_anchor"}
VALID_SPLITS = {"needs_acquisition", "sealed_candidate", "dev_only"}

AVOID = {
    "python": [
        "mirrormind", "codeassist", "repositorylibrary", "agentlab", "einops", "smolagents",
        "pythonsdk", "openaiagentspython", "pydanticai", "dspy", "llmmemorymodulesatscale",
    ],
    "rust": ["tokenizers", "candle", "perftree", "libgitrs"],
    "c_cpp": [
        "parametergolf", "agentkernel", "cccl", "onnxruntime", "sentencepiece", "bitsandbytes",
        "mamba", "statespace101", "modelstack", "pytorch", "mentalsai",
    ],
    "web_js_ts_html": ["openhands", "llamastack", "codeassist", "openclaw", "modelcontextprotocol", "sepautomation"],
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            rows.append(value if isinstance(value, dict) else {"_parse_error": "json line is not object", "_raw": line[:300]})
        except json.JSONDecodeError as exc:
            rows.append({"_parse_error": str(exc), "_raw": line[:300]})
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def canonical(value: Any) -> str:
    text = str(value or "").lower().replace("\\", "/")
    text = text.removeprefix("https://github.com/")
    text = text.removeprefix("http://github.com/")
    if "::" in text:
        text = text.split("::", 1)[0]
    return re.sub(r"[^a-z0-9]+", "", text)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    input_files = sorted(IN_DIR.glob("*_candidates.jsonl"))
    rows = []
    for path in input_files:
        for row in read_jsonl(path):
            row["_stage12117_input_file"] = rel(path)
            rows.append(row)

    admitted = []
    rejected = []
    seen = set()
    rejection_counts = Counter()
    admitted_by_language = Counter()
    admitted_by_verifier_type = Counter()
    per_repo = Counter()
    per_language_repo = defaultdict(Counter)

    for row in rows:
        reasons = []
        language = str(row.get("language") or "")
        verifier_type = str(row.get("verifier_type") or "")
        split_status = str(row.get("split_status") or "")
        target = row.get("source_path_or_acquisition_target") or row.get("source_path")
        repo_key = canonical(row.get("repo_family") or target)
        dedupe_key = f"{language}::{repo_key}::{canonical(target)}"

        if row.get("_parse_error"):
            reasons.append("json_parse_error")
        if language not in VALID_LANGS:
            reasons.append("invalid_language")
        if verifier_type not in VALID_VERIFIER_TYPES:
            reasons.append("invalid_verifier_type")
        if split_status not in VALID_SPLITS:
            reasons.append("invalid_split_status")
        if split_status != "needs_acquisition":
            reasons.append("pilot_accepts_needs_acquisition_only")
        if bool(row.get("exists_locally")):
            reasons.append("pilot_accepts_remote_acquisition_only")
        if not str(target or "").startswith("https://github.com/"):
            reasons.append("missing_github_url_target")
        if row.get("reserved_family_conflict") is True:
            reasons.append("reserved_family_conflict_true")
        if not row.get("available_evidence"):
            reasons.append("missing_available_evidence")
        if not row.get("missing_evidence"):
            reasons.append("missing_missing_evidence")
        if not row.get("suggested_commands"):
            reasons.append("missing_suggested_commands")
        if not row.get("why_valid"):
            reasons.append("missing_why_valid")
        if not row.get("risk_notes"):
            reasons.append("missing_risk_notes")
        if dedupe_key in seen:
            reasons.append("duplicate_candidate")
        for banned in AVOID.get(language, []):
            if banned and banned in repo_key:
                reasons.append("language_overfit_family_excluded")
                break
        if per_repo[repo_key] >= 1:
            reasons.append("duplicate_repo_family_in_pilot_intake")

        audited = {
            **row,
            "stage12117_repo_key": repo_key,
            "stage12117_dedupe_key": dedupe_key,
            "stage12117_reasons": reasons,
        }
        if reasons:
            rejected.append(audited)
            for reason in reasons:
                rejection_counts[reason] += 1
            continue
        seen.add(dedupe_key)
        per_repo[repo_key] += 1
        per_language_repo[language][repo_key] += 1
        audited["stage12117_admitted"] = True
        audited["do_not_train"] = True
        audited["claim_boundary"] = "Acquisition target only; not a task row until checkout, verifier logs, anti-cheat, and lineage admission pass."
        admitted.append(audited)
        admitted_by_language[language] += 1
        admitted_by_verifier_type[verifier_type] += 1

    target_by_language = {language: 50 for language in VALID_LANGS}
    pilot_readiness = {
        language: {
            "admitted": admitted_by_language.get(language, 0),
            "target": target,
            "ready": admitted_by_language.get(language, 0) >= target,
        }
        for language, target in sorted(target_by_language.items())
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "maintainer_400_pilot_candidate_intake_audited",
        "do_not_train": True,
        "input_dir": rel(IN_DIR),
        "input_files": [rel(path) for path in input_files],
        "input_candidates": len(rows),
        "admitted_candidates": len(admitted),
        "rejected_candidates": len(rejected),
        "admitted_by_language": dict(sorted(admitted_by_language.items())),
        "admitted_by_verifier_type": dict(sorted(admitted_by_verifier_type.items())),
        "rejection_counts": dict(rejection_counts.most_common()),
        "pilot_readiness_by_language": pilot_readiness,
        "next_stage_recommendation": {
            "stage": "stage12118_maintainer_400_checkout_probe_request",
            "action": "Only admitted acquisition targets may proceed to network checkout/probe. Still no train/eval rows.",
            "network_required": True,
            "gpu_required": False,
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
            "merged_intake": rel(MERGED),
            "admitted": rel(ADMITTED),
            "rejected": rel(REJECTED),
        },
    }
    write_jsonl(MERGED, rows)
    write_jsonl(ADMITTED, admitted)
    write_jsonl(REJECTED, rejected)
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "input_candidates": len(rows),
        "admitted_candidates": len(admitted),
        "admitted_by_language": summary["admitted_by_language"],
        "rejection_counts": summary["rejection_counts"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
