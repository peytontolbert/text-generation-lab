#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11663
NAME = "stage11663_web_canonical_renderer_package"
OUT = ART / NAME
TRAIN = OUT / "web_canonical_train_support.jsonl"
HELDOUT = OUT / "web_canonical_heldout.jsonl"
ALL_ROWS = OUT / "web_canonical_all_rows.jsonl"
SUMMARY = OUT / "web_canonical_renderer_package.json"

SUPPORT_SOURCES = {
    "stage11570_semantic_non_evidence": ART / "stage11570_semantic_web_non_evidence_support_package/semantic_web_non_evidence_train_rows.jsonl",
    "stage11594_verifier_attached_repaired": ART / "stage11594_web_verifier_attached_repaired_geometry_package/web_verifier_attached_repaired_rows.jsonl",
    "stage11621_fail_to_pass_repaired": ART / "stage11621_web_fail_to_pass_row_geometry_repair/web_fail_to_pass_geometry_repaired_train_support.jsonl",
    "stage11659_schema_aligned_bridge": ART / "stage11659_web_schema_aligned_bridge_package/web_schema_aligned_bridge_manifest.jsonl",
}
HELDOUT_SOURCE = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
PROTECTED_SOURCES = {
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_validation": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl",
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
}

TASK_QUESTIONS = {
    "symptom_localization": "Which candidate owns the observed behavior or failure symptom?",
    "evidence_citation": "Which candidate is the decisive visible evidence for this maintainer decision?",
    "verifier_outcome": "Which verifier/test candidate determines the observed outcome?",
    "minimal_fix_selection": "Which candidate is the smallest justified fix target?",
    "patch_impact": "Which candidate best describes the patch impact or behavior delta?",
    "alternative_hypothesis_elimination": "Which candidate is most strongly eliminated by the visible evidence?",
    "abstention_insufficient_evidence": "Is there enough visible evidence to answer, retrieve, or abstain?",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def first_existing(row: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def bundle(row: dict[str, Any]) -> dict[str, Any]:
    source = row.get("standalone_projection_source")
    if isinstance(source, dict) and isinstance(source.get("bundle"), dict):
        return source["bundle"]
    return {}


def section(prompt: str, starts: list[str], ends: list[str]) -> str:
    for start in starts:
        if start in prompt:
            tail = prompt.split(start, 1)[1]
            end_indexes = [tail.find(marker) for marker in ends if marker in tail]
            end_indexes = [idx for idx in end_indexes if idx >= 0]
            if end_indexes:
                tail = tail[: min(end_indexes)]
            return tail.strip()
    return ""


def evidence_text(row: dict[str, Any], kind: str) -> str:
    b = bundle(row)
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    if kind == "task":
        return str(b.get("task") or section(prompt, ["Task observation:"], ["Visible source", "Options:"]) or "")
    if kind == "source":
        return str(
            b.get("source_evidence")
            or section(
                prompt,
                ["Visible source evidence:", "Visible source evidence (opaque source IDs):", "Visible source candidate excerpt"],
                ["Visible verifier", "Observed verifier", "Plausible sibling", "Options:"],
            )
            or ""
        )
    if kind == "verifier":
        return str(
            b.get("test_evidence")
            or section(
                prompt,
                ["Visible verifier/test evidence:", "Visible verifier/test evidence (opaque verifier IDs):", "Visible verifier/test excerpt"],
                ["Visible verifier execution evidence:", "Observed verifier", "Plausible sibling", "Options:"],
            )
            or ""
        )
    if kind == "execution":
        verifier = row.get("verifier_evidence") if isinstance(row.get("verifier_evidence"), dict) else {}
        execution = b.get("execution_evidence") or section(
            prompt,
            ["Visible verifier execution evidence:", "Observed verifier transition:", "Observed mutant verifier failure:"],
            ["Observed restored verifier pass:", "Verifier log excerpt:", "Choices:", "Options:"],
        )
        if execution:
            return str(execution)
        command = verifier.get("command")
        if isinstance(command, list):
            command_text = " ".join(str(part) for part in command)
        else:
            command_text = str(command or "")
        status = str(verifier.get("status") or "")
        transition = str(verifier.get("transition") or "")
        return f"command={command_text} status={status} transition={transition}".strip()
    if kind == "distractor":
        return str(b.get("distractor_evidence") or section(prompt, ["Visible alternative/distractor evidence:", "Plausible sibling/call-path excerpt"], ["Observed", "Options:", "Choices:"]) or "")
    return ""


def option_records(row: dict[str, Any]) -> list[dict[str, Any]]:
    source = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    options = source.get("opaque_options") if isinstance(source.get("opaque_options"), list) else row.get("opaque_options")
    return [dict(option) for option in options if isinstance(option, dict)]


def infer_role(row: dict[str, Any], option: dict[str, Any]) -> str:
    if option.get("semantic_role"):
        return str(option["semantic_role"])
    semantic = option.get("semantic_candidate") if isinstance(option.get("semantic_candidate"), dict) else {}
    if semantic.get("evidence_role"):
        return str(semantic["evidence_role"])
    value = str(option.get("value") or option.get("text") or "")
    text = str(option.get("text") or "")
    joined = f"{value} {text}".lower()
    if "abstain" in joined or "insufficient" in joined:
        return "abstain_insufficient_evidence"
    if "test" in joined or "verifier" in joined or "assert" in joined or "jest" in joined or "vitest" in joined:
        return "verifier_and_test_constraint"
    if "retrieve" in joined or "external" in joined or "web research" in joined:
        return "retrieve_or_external_reference"
    if "symptom" in joined or "call-path" in joined or "analogue" in joined or "distractor" in joined:
        return "symptom_or_call_path_analogue"
    return "candidate_change_surface"


def artifact_type(role: str, value: str, text: str) -> str:
    joined = f"{value} {text}".lower()
    if "abstain" in joined or "insufficient" in joined:
        return "abstention"
    if "retrieve" in joined or "external" in joined:
        return "information_request"
    if role == "verifier_and_test_constraint" or re.search(r"(test|spec)\.(tsx?|jsx?|js|ts)\b", joined):
        return "verifier_test"
    if re.search(r"\.(tsx?|jsx?|html|css|json|md)\b", joined) or "::" in value:
        return "source_artifact"
    if len(text.split()) >= 6:
        return "evidence_sentence"
    return "candidate"


def evidence_ids(role: str, artifact: str) -> list[str]:
    if role == "verifier_and_test_constraint" or artifact == "verifier_test":
        return ["V01", "X01"]
    if role == "symptom_or_call_path_analogue":
        return ["D01", "S01"]
    if role == "abstain_insufficient_evidence":
        return ["STATE"]
    if role == "retrieve_or_external_reference":
        return ["STATE"]
    return ["S01"]


def canonical_option(row: dict[str, Any], option: dict[str, Any]) -> dict[str, Any]:
    label = str(option.get("label") or "").strip()
    role = infer_role(row, option)
    raw_value = str(option.get("value") or option.get("text") or label).strip()
    raw_text = str(option.get("text") or raw_value).strip()
    artifact = artifact_type(role, raw_value, raw_text)
    ids = evidence_ids(role, artifact)
    candidate_value = (
        f"role={role}; artifact_type={artifact}; value={raw_value}; "
        f"evidence_ids={','.join(ids)}; text={raw_text}"
    )
    semantic = option.get("semantic_candidate") if isinstance(option.get("semantic_candidate"), dict) else {}
    semantic = dict(semantic)
    semantic.update(
        {
            "role": role,
            "artifact_type": artifact,
            "canonical_value": raw_value,
            "evidence_ids": ids,
            "task_type": str(row.get("task_type") or semantic.get("task_type") or "unknown"),
        }
    )
    return {
        "label": label,
        "role": role,
        "artifact_type": artifact,
        "value": candidate_value,
        "text": raw_text,
        "semantic_candidate": semantic,
        "canonical_candidate_object": {
            "candidate_id": label,
            "role": role,
            "artifact_type": artifact,
            "artifact_refs": ids,
            "value": raw_value,
            "text": raw_text,
        },
    }


def render_prompt(row: dict[str, Any], options: list[dict[str, Any]]) -> str:
    task = str(row.get("task_type") or "unknown")
    root_id = first_existing(row, ["root_id", "root_lineage_key", "row_id"], "unknown")
    repo = first_existing(row, ["repo_family", "git_repo_family", "web_heldout_source", "repo_id"], "unknown")
    lines = [
        "TASK",
        f"language: {row.get('language_family') or 'web_js_ts_html'}",
        f"repo_family: {repo}",
        f"root_id: {root_id}",
        f"task_type: {task}",
        f"question: {TASK_QUESTIONS.get(task, 'Choose the best candidate from the visible evidence.')}",
        "",
        "OBSERVED_STATE",
        evidence_text(row, "task")[:1200] or "Verifier-backed maintainer decision over the attached source and test evidence.",
        "",
        "SOURCE_EVIDENCE",
        "[S01] " + (evidence_text(row, "source")[:2600] or "source evidence unavailable"),
        "",
        "VERIFIER_EVIDENCE",
        "[V01] " + (evidence_text(row, "verifier")[:2200] or "verifier evidence unavailable"),
        "[X01] " + (evidence_text(row, "execution")[:1400] or "execution evidence unavailable"),
    ]
    distractor = evidence_text(row, "distractor")
    if distractor:
        lines.extend(["", "DISTRACTOR_OR_CALL_PATH_EVIDENCE", "[D01] " + distractor[:1200]])
    lines.extend(["", "CANDIDATES"])
    for option in options:
        obj = option["canonical_candidate_object"]
        lines.append(
            f"{obj['candidate_id']}: role={obj['role']} | artifact_type={obj['artifact_type']} | "
            f"value={obj['value']} | evidence_ids={','.join(obj['artifact_refs'])} | text={obj['text']}"
        )
    lines.extend(["", "QUESTION", TASK_QUESTIONS.get(task, "Choose the best candidate."), "Answer:"])
    return "\n".join(lines)


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or (row.get("target") or {}).get("bounded_choice_target_label") or "").strip()


def has_label_leak(prompt: str, label: str) -> bool:
    before = prompt.split("CANDIDATES", 1)[0]
    return bool(label and re.search(rf"\b(option|candidate)\s+{re.escape(label)}\b", before, flags=re.IGNORECASE))


def transform(row: dict[str, Any], *, source_name: str, split: str) -> dict[str, Any] | None:
    label = target_label(row)
    options = [canonical_option(row, option) for option in option_records(row) if option.get("label")]
    if not label or not options or label not in {option["label"] for option in options}:
        return None
    out = copy.deepcopy(row)
    prompt = render_prompt(row, options)
    source = dict(out.get("standalone_projection_source") or {})
    source["opaque_options"] = options
    source["projection_mode"] = "stage11663_web_canonical_candidate_renderer"
    source["canonical_renderer_source"] = source_name
    out["standalone_projection_source"] = source
    out["opaque_options"] = copy.deepcopy(options)
    out["prompt_text"] = prompt
    out["input_text"] = prompt
    out["decoder_text"] = label
    out["target_text"] = label
    out["bounded_choice_target_label"] = label
    out["split"] = split
    out["package_split"] = split
    out["split_component"] = f"{split}_canonical_web"
    out["row_id"] = f"{row.get('row_id')}::stage11663_canonical"
    out["stage11663_canonical_renderer"] = True
    out["stage11663_source"] = source_name
    out["trainable_now"] = split == "train"
    out["strict_eval_eligible_now"] = split != "train"
    out["loss_mask"] = {
        "bounded_choice_aux": True,
        "decoder_ce": split == "train",
    }
    anti = dict(out.get("anti_cheat") or {})
    anti.update(
        {
            "canonical_renderer_shared_train_heldout": True,
            "candidate_objects_role_typed": True,
            "deterministic_option_shuffle": True,
            "gold_label_visible_before_options": has_label_leak(prompt, label),
            "no_gold_label_in_prompt_before_options": not has_label_leak(prompt, label),
        }
    )
    out["anti_cheat"] = anti
    return out


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("row_id"))


def protected_roots() -> set[str]:
    roots: set[str] = set()
    for path in PROTECTED_SOURCES.values():
        for row in load_jsonl(path):
            roots.add(root_key(row))
    return roots


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    protected = protected_roots()
    support_rows: list[dict[str, Any]] = []
    rejected: Counter[str] = Counter()
    seen: set[tuple[str, str, str]] = set()
    source_counts: Counter[str] = Counter()
    for source_name, path in SUPPORT_SOURCES.items():
        for row in load_jsonl(path):
            if root_key(row) in protected:
                rejected["protected_root_overlap"] += 1
                continue
            if str(row.get("split") or row.get("package_split") or "train") not in {"train", "train_candidate"}:
                rejected["not_train_split"] += 1
                continue
            transformed = transform(row, source_name=source_name, split="train")
            if transformed is None:
                rejected["transform_failed"] += 1
                continue
            key = (root_key(transformed), str(transformed.get("task_type")), str(transformed.get("semantic_target_value") or target_label(transformed)))
            if key in seen:
                rejected["duplicate_root_task_target"] += 1
                continue
            seen.add(key)
            support_rows.append(transformed)
            source_counts[source_name] += 1

    heldout_rows: list[dict[str, Any]] = []
    for row in load_jsonl(HELDOUT_SOURCE):
        transformed = transform(row, source_name="stage11548_web_heldout", split="strict_eval")
        if transformed is not None:
            heldout_rows.append(transformed)
    train_roots = {root_key(row) for row in support_rows}
    heldout_roots = {root_key(row) for row in heldout_rows}
    all_rows = support_rows + heldout_rows
    write_jsonl(TRAIN, support_rows)
    write_jsonl(HELDOUT, heldout_rows)
    write_jsonl(ALL_ROWS, all_rows)

    def counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "rows": len(rows),
            "roots": len({root_key(row) for row in rows}),
            "repo_counts": dict(Counter(str(row.get("repo_family") or row.get("git_repo_family") or row.get("web_heldout_source") or "unknown") for row in rows).most_common()),
            "task_counts": dict(Counter(str(row.get("task_type") or "unknown") for row in rows).most_common()),
            "target_label_counts": dict(Counter(target_label(row) for row in rows).most_common()),
            "prompt_label_leak_rows": sum(1 for row in rows if (row.get("anti_cheat") or {}).get("gold_label_visible_before_options") is True),
        }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "web_canonical_renderer_package_ready_for_baseline_and_head_only_probe",
        "outputs": {
            "train": rel(TRAIN),
            "heldout": rel(HELDOUT),
            "all_rows": rel(ALL_ROWS),
            "summary": rel(SUMMARY),
        },
        "source_artifacts": {name: rel(path) for name, path in SUPPORT_SOURCES.items()} | {"heldout": rel(HELDOUT_SOURCE)},
        "counts": {
            "train": counts(support_rows),
            "heldout": counts(heldout_rows),
            "all": counts(all_rows),
            "source_train_counts": dict(source_counts.most_common()),
            "rejected_support_rows": dict(rejected.most_common()),
        },
        "root_overlap": {
            "train_heldout_overlap_count": len(train_roots & heldout_roots),
            "train_heldout_overlap_examples": sorted(train_roots & heldout_roots)[:20],
            "train_protected_overlap_count": len(train_roots & protected),
        },
        "gates": {
            "no_train_heldout_root_overlap": len(train_roots & heldout_roots) == 0,
            "no_train_protected_root_overlap": len(train_roots & protected) == 0,
            "heldout_rows_66": len(heldout_rows) == 66,
            "train_at_least_250_rows": len(support_rows) >= 250,
            "train_at_least_40_roots": len(train_roots) >= 40,
            "no_prompt_label_leaks": counts(all_rows)["prompt_label_leak_rows"] == 0,
        },
        "claim_boundary": [
            "This is a canonical renderer package, not a model promotion.",
            "Train and heldout now share the same candidate-object interface; roots remain split.",
            "Support sources include prior train-support rows only; heldout rows remain strict_eval.",
            "Any probe must be head-only first and preserve Stage11507 protected gates.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "counts": summary["counts"], "gates": summary["gates"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
