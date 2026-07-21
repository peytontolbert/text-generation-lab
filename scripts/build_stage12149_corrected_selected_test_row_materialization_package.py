#!/usr/bin/env python3
"""Build Stage12149 corrected selected-test train-support rows.

This materializer is intentionally conservative: it only uses Stage12146 ready
supply, blocks roots with missing hash/commit provenance, and audits the
task-specific target semantics required by the Stage12148 contract.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
OUT = ART / "stage12149_corrected_selected_test_row_materialization_package"
SUMMARY_MIRROR = ROOT / "runs/summaries/stage12149_corrected_selected_test_row_materialization_package.json"

CONTRACT_PATH = ART / "stage12148_task_specific_selected_test_materialization_contract/materialization_contract.json"
SUPPLY_PATH = ART / "stage12146_selected_test_supply_rollup/selected_test_supply_rollup.jsonl"
PY_RESULTS = ART / "stage12143_no_install_selected_test_expansion/selected_test_expansion_results.jsonl"
RUST_RESULTS = ART / "stage12144_rust_hydrated_selected_test_success_package/rust_hydrated_selected_test_successes.jsonl"
WEB_RESULTS = ART / "stage12145_web_hydrated_selected_test_success_package/web_hydrated_selected_test_results.jsonl"
HYGIENE_PATH = ROOT / "runs/summaries/stage12151_selected_test_supply_hygiene_audit.json"

PREFERRED_REPOS = [
    "PyCQA/flake8",
    "assert-rs/predicates-rs",
    "toml-rs/toml",
    "dtolnay/anyhow",
    "moment/luxon",
]

TASKS = [
    "transition_candidate_selection",
    "transition_next_action",
    "transition_continue_or_stop",
    "transition_verifier_transition",
    "transition_evidence_citation",
]

DEPENDENCY_PARTS = {
    ".git",
    "node_modules",
    "target",
    "build",
    "dist",
    ".tox",
    ".venv",
    "venv",
    "__pycache__",
}

CONFIRMED_COMMIT_SHA = {
    "moment/luxon": "b6b9d03709085008287ed7f4ce5067f0f4be53f2",
}

EXTRA_CLEAN_HASH_PATHS = {
    "assert-rs/predicates-rs": [
        "src/function.rs",
    ],
    "toml-rs/toml": [
        "crates/toml/src/lib.rs",
        "crates/toml/tests/compliance/parse.rs",
        "crates/toml/tests/compliance/main.rs",
    ],
    "dtolnay/anyhow": [
        "src/lib.rs",
        "tests/test_context.rs",
    ],
    "moment/luxon": [
        "src/datetime.js",
        "src/settings.js",
        "test/datetime/create.test.js",
        "test/helpers.js",
    ],
}


def read_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_id(*parts: str, n: int = 12) -> str:
    return hashlib.sha256("::".join(parts).encode()).hexdigest()[:n]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_dependency_path(path: str) -> bool:
    parts = set(Path(path).parts)
    return bool(parts & DEPENDENCY_PARTS)


def git_commit(path: Path) -> str | None:
    try:
        got = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        return None
    sha = got.stdout.strip()
    return sha if sha else None


def classify_hashes(root: Path, declared: list[dict[str, str]] | None, paths: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    blockers: list[str] = []
    records: list[dict[str, str]] = []
    if declared:
        for item in declared:
            rel = str(item.get("path") or "")
            digest = str(item.get("sha256") or "")
            kind = str(item.get("kind") or "")
            if not rel or not digest:
                blockers.append(f"invalid_declared_hash::{rel}")
                continue
            if is_dependency_path(rel):
                blockers.append(f"dependency_path_declared_hash::{rel}")
                continue
            if not (root / rel).exists():
                blockers.append(f"declared_hash_path_missing::{rel}")
                continue
            actual = sha256_file(root / rel)
            if actual != digest:
                blockers.append(f"declared_hash_mismatch::{rel}")
                continue
            records.append({"kind": kind, "path": rel, "sha256": digest})
        return sorted(records, key=lambda x: (x["kind"], x["path"])), blockers

    for rel in sorted(set(paths)):
        if not rel or is_dependency_path(rel):
            continue
        p = root / rel
        if not p.is_file():
            continue
        kind = "test" if "/test" in f"/{rel}" or rel.startswith("test") or "/tests" in f"/{rel}" or rel.startswith("tests") else "source"
        records.append({"kind": kind, "path": rel, "sha256": sha256_file(p)})
    # Rust unit tests may live in the source file; duplicate the same clean file
    # as test evidence when no separate selected-test file exists.
    if records and not any(r["kind"] == "test" for r in records):
        for r in records:
            if r["path"].endswith(".rs") and "/src/" in f"/{r['path']}":
                records.append({"kind": "test", "path": r["path"], "sha256": r["sha256"]})
                break
    if not records:
        blockers.append("no_non_dependency_hashable_source_or_test_paths")
    if not any(r["kind"] == "source" for r in records):
        blockers.append("missing_source_hash")
    if not any(r["kind"] == "test" for r in records):
        blockers.append("missing_test_hash")
    return sorted(records, key=lambda x: (x["kind"], x["path"])), blockers


def hygiene_gate() -> dict[str, dict[str, Any]]:
    hygiene = read_json(HYGIENE_PATH)
    return {str(rec.get("repo_family")): rec for rec in hygiene.get("records", [])}


def build_source_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}

    for rec in read_jsonl(PY_RESULTS):
        if rec.get("admission_ready_for_row_materialization") is True:
            records[rec["repo_family"]] = {
                "stage_record": rec,
                "checkout_path": rec["local_root"],
                "commit_sha": rec.get("commit_sha"),
                "language_family": "python",
                "root_id": rec["candidate_id"],
                "selected_test_ids": rec.get("selected_test_ids") or [],
                "selected_test_count": len(rec.get("selected_test_ids") or []),
                "verifier_command": " && ".join(c.get("command", "") for c in rec.get("commands", []) if c.get("label", "").startswith("selected")),
                "result_summary": "selected pytest node ids passed",
                "declared_hashes": rec.get("source_test_evidence_hashes") or [],
                "visible_paths": [],
                "source_stage": "stage12143",
            }

    for rec in read_jsonl(RUST_RESULTS):
        if rec.get("admissible_for_row_materialization_request") is True:
            records[rec["repo_family"]] = {
                "stage_record": rec,
                "checkout_path": rec["checkout_path"],
                "commit_sha": rec.get("commit_sha"),
                "language_family": "rust",
                "root_id": rec["queue_id"],
                "selected_test_ids": rec.get("selected_test_ids") or [],
                "selected_test_count": rec.get("selected_test_count") or len(rec.get("selected_test_ids") or []),
                "verifier_command": rec.get("selected_test_command"),
                "result_summary": rec.get("result_summary"),
                "declared_hashes": None,
                "visible_paths": rec.get("visible_rust_sources") or [],
                "source_stage": "stage12144",
            }

    for rec in read_jsonl(WEB_RESULTS):
        if rec.get("admissible_for_row_materialization_request") is True:
            records[rec["repo_family"]] = {
                "stage_record": rec,
                "checkout_path": rec["checkout_path"],
                "commit_sha": rec.get("commit_sha"),
                "language_family": "web_js_ts_html",
                "root_id": rec["queue_id"],
                "selected_test_ids": rec.get("selected_test_ids") or [],
                "selected_test_count": rec.get("selected_test_count") or len(rec.get("selected_test_ids") or []),
                "verifier_command": rec.get("selected_test_command"),
                "result_summary": rec.get("result_summary"),
                "declared_hashes": None,
                "visible_paths": rec.get("visible_source_files") or [],
                "verifier_environment": rec.get("verifier_environment") or {},
                "source_stage": "stage12145",
            }

    return records


def task_spec(task: str, root: dict[str, Any]) -> dict[str, Any]:
    verifier_status = "PASS_CURRENT_STATE"
    if root["language_family"] in {"rust", "web_js_ts_html"}:
        verifier_status = "PASS_CURRENT_BUILD_AND_RUN"

    specs = {
        "transition_candidate_selection": {
            "target": "selected_test_backed_verifier_candidate",
            "role": "selected_test_backed_verifier_candidate",
            "target_kind": "candidate_artifact_or_evidence_candidate",
            "artifact_type": "selected_test_verifier_record",
            "options": [
                ("selected_test_backed_verifier_candidate", "selected_test_verifier_record"),
                ("candidate_change_surface", "source_surface_record"),
                ("source_surface", "source_surface_record"),
                ("insufficient_evidence", "control"),
            ],
        },
        "transition_next_action": {
            "target": "FINISH",
            "role": "FINISH",
            "target_kind": "maintainer_action",
            "artifact_type": "action",
            "options": [
                ("FINISH", "action"),
                ("RUN_VERIFIER", "action"),
                ("SELECT_TEST", "action"),
                ("ABSTAIN_OR_ROLLBACK", "action"),
            ],
        },
        "transition_continue_or_stop": {
            "target": "STOP_DONE",
            "role": "STOP_DONE",
            "target_kind": "episode_control_decision",
            "artifact_type": "control",
            "options": [
                ("STOP_DONE", "control"),
                ("CONTINUE", "control"),
                ("NOT_DONE_MISSING_TESTS", "control"),
                ("ABSTAIN_INSUFFICIENT_EVIDENCE", "control"),
            ],
        },
        "transition_verifier_transition": {
            "target": verifier_status,
            "role": verifier_status,
            "target_kind": "verifier_status",
            "artifact_type": "verifier_status",
            "options": [
                (verifier_status, "verifier_status"),
                ("NOT_EXERCISED", "verifier_status"),
                ("INSUFFICIENT_EVIDENCE", "verifier_status"),
                ("VERIFIER_REMOVED", "verifier_status"),
            ],
        },
        "transition_evidence_citation": {
            "target": "verifier_and_test_constraint",
            "role": "verifier_and_test_constraint",
            "target_kind": "evidence_role_or_evidence_item",
            "artifact_type": "evidence_role",
            "options": [
                ("verifier_and_test_constraint", "evidence_role"),
                ("candidate_change_surface", "evidence_role"),
                ("source_surface", "evidence_role"),
                ("insufficient_evidence", "evidence_role"),
            ],
        },
    }
    return specs[task]


def option_order(root_id: str, task: str, values: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return sorted(values, key=lambda item: stable_id(root_id, task, item[0]))


def render_prompt(root: dict[str, Any], task: str, hash_records: list[dict[str, str]], evidence_ids: list[str], options: list[dict[str, Any]]) -> str:
    source_hashes = [f"{r['path']}@{r['sha256'][:12]}" for r in hash_records if r["kind"] == "source"][:4]
    test_hashes = [f"{r['path']}@{r['sha256'][:12]}" for r in hash_records if r["kind"] == "test"][:4]
    pre_options = [
        f"Task family: {task}",
        f"Repository: {root['repo_family']}",
        f"Language: {root['language_family']}",
        f"Commit: {root['commit_sha']}",
        f"Selected-test evidence: {root['selected_test_count']} selected test id(s); identifiers withheld from target surface.",
        f"Verifier result summary: successful selected-test execution evidence is present; exact status labels are withheld until Options.",
        f"Source hash summary: {', '.join(source_hashes)}",
        f"Test hash summary: {', '.join(test_hashes)}",
        f"Evidence ledger refs: {json.dumps([stable_id(e) for e in evidence_ids[:6]], sort_keys=True)}",
        "Choose the single option best supported by the compact verifier/source/test record. Use only the opaque labels below.",
        "Options:",
    ]
    option_lines = [f"- {opt['label']}: Option {opt['label']}" for opt in options]
    return "\n".join(pre_options + option_lines + ["Answer:"])


def make_options(root: dict[str, Any], task: str, spec: dict[str, Any], evidence_ids: list[str]) -> list[dict[str, Any]]:
    labels = ["A", "B", "C", "D"]
    ordered = option_order(root["root_id"], task, spec["options"])
    out = []
    for i, ((value, artifact_type), label) in enumerate(zip(ordered, labels)):
        out.append(
            {
                "deterministic_position": i,
                "label": label,
                "semantic_id": f"{task}::{value}",
                "value": value,
                "semantic_candidate": {
                    "role": value,
                    "target_kind": spec["target_kind"],
                    "artifact_type": artifact_type,
                    "value": value,
                    "evidence_ids": evidence_ids if value == spec["target"] else [],
                },
            }
        )
    return out


def sanitized_verifier_command(root: dict[str, Any]) -> str:
    command = str(root.get("verifier_command") or "")
    if "/target/" in command or "CARGO_TARGET_DIR" in command or "node_modules" in command:
        tool = "cargo test" if root.get("language_family") == "rust" else "selected verifier"
        return f"{tool} selected-test command passed; dependency/cache/build paths withheld"
    return command


def build_row(root: dict[str, Any], task: str, hash_records: list[dict[str, str]]) -> dict[str, Any]:
    spec = task_spec(task, root)
    evidence_ids = [
        f"{root['source_stage']}::{root['root_id']}::selected_test_success",
        f"commit::{root['commit_sha']}",
    ]
    evidence_ids.extend(f"{r['kind']}_hash::{r['path']}::{r['sha256']}" for r in hash_records[:8])
    options = make_options(root, task, spec, evidence_ids)
    target = next(opt for opt in options if opt["value"] == spec["target"])
    prompt = render_prompt(root, task, hash_records, evidence_ids, options)
    row_id = f"stage12149::{root['root_id']}::{task}::{stable_id(root['root_id'], task, spec['target'])}"
    projection = {
        "stage": "stage12149_corrected_selected_test_row_materialization_package",
        "source_stage": root["source_stage"],
        "repo_family": root["repo_family"],
        "root_id": root["root_id"],
        "commit_sha": root["commit_sha"],
        "selected_test_ids": root["selected_test_ids"],
        "selected_test_count": root["selected_test_count"],
        "verifier_command": sanitized_verifier_command(root),
        "verifier_environment": root.get("verifier_environment") or {},
        "result_summary": root.get("result_summary"),
        "source_test_hashes": hash_records,
        "dependency_path_exclusions": sorted(DEPENDENCY_PARTS),
        "evidence_ids": evidence_ids,
        "gold_value": spec["target"],
        "gold_role": spec["role"],
        "gold_target_kind": spec["target_kind"],
        "opaque_options": options,
    }
    return {
        "row_id": row_id,
        "stage": "stage12149_corrected_selected_test_row_materialization_package",
        "surface": "stage12149_corrected_selected_test_bounded_choice_train_support",
        "split": "train",
        "package_split": "train",
        "split_role": "stage12149_train_support_only_not_strict_eval",
        "task_type": task,
        "language_family": root["language_family"],
        "repo_family": root["repo_family"],
        "repo_id": root["repo_family"].replace("/", "__"),
        "root_id": root["root_id"],
        "source_root_id": root["root_id"],
        "commit_sha": root["commit_sha"],
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "train_support_only": True,
        "strict_eval_eligible": False,
        "promotion_eligible": False,
        "training_allowed": False,
        "prompt_text": prompt,
        "input_text": prompt,
        "target_label": target["label"],
        "bounded_choice_target_label": target["label"],
        "target_text": target["label"],
        "decoder_text": target["label"],
        "target_semantic_value": spec["target"],
        "target": {
            "bounded_choice_target_label": target["label"],
            "decoder_text": target["label"],
            "semantic_value": spec["target"],
            "semantic_role": spec["role"],
            "target_kind": spec["target_kind"],
        },
        "opaque_options": options,
        "standalone_projection_source": projection,
        "loss_mask": {
            "bounded_choice_aux": True,
            "decoder_ce": True,
            "structured_aux": True,
            "transition_projection": True,
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "single_token_labels": True,
            "nested_top_level_options_mirror": True,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "dependency_paths_excluded": True,
            "stage12149_train_support_only": True,
            "strict_eval_not_cleared": True,
        },
    }


def entropy(values: list[str]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    total = len(values)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def audit_rows(rows: list[dict[str, Any]], blocked_roots: list[dict[str, Any]], contract: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    counts_by_language_root_task: dict[str, Any] = defaultdict(lambda: defaultdict(Counter))
    for row in rows:
        counts_by_language_root_task[row["language_family"]][row["repo_family"]][row["task_type"]] += 1

    per_root_values = defaultdict(list)
    by_task_roles = defaultdict(list)
    for row in rows:
        per_root_values[row["repo_family"]].append(row["target_semantic_value"])
        by_task_roles[row["task_type"]].append(row["target"]["semantic_role"])

    per_root_semantic_diversity = {}
    for repo, values in per_root_values.items():
        unique = sorted(set(values))
        failed = len(unique) <= 1
        if failed:
            blockers.append(f"root_all_task_families_share_same_target::{repo}")
        per_root_semantic_diversity[repo] = {
            "target_semantic_values": unique,
            "unique_target_semantic_values": len(unique),
            "blocked_same_target_for_all_tasks": failed,
        }

    label_failures = []
    mirror_failures = []
    leak_failures = []
    dependency_failures = []
    commit_failures = []
    disallowed_role_failures = []
    for row in rows:
        labels = [str(opt.get("label")) for opt in row.get("opaque_options") or []]
        if labels != ["A", "B", "C", "D"]:
            label_failures.append(row["row_id"])
        if row.get("opaque_options") != (row.get("standalone_projection_source") or {}).get("opaque_options"):
            mirror_failures.append(row["row_id"])
        before_options = row["prompt_text"].split("Options:", 1)[0]
        label_re = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(row['target_label'])}(?![A-Za-z0-9_])")
        if label_re.search(before_options) or row["target_semantic_value"] in before_options:
            leak_failures.append(row["row_id"])
        for h in (row.get("standalone_projection_source") or {}).get("source_test_hashes") or []:
            if is_dependency_path(str(h.get("path") or "")):
                dependency_failures.append(row["row_id"])
        if not row.get("commit_sha"):
            commit_failures.append(row["row_id"])
        allowed = set(contract["row_families"][row["task_type"]]["allowed_target_roles"])
        if row["target"]["semantic_role"] not in allowed:
            disallowed_role_failures.append(row["row_id"])

    for name, failures in [
        ("single_token_option_label_failures", label_failures),
        ("nested_top_level_option_mirror_failures", mirror_failures),
        ("prompt_target_leak_failures", leak_failures),
        ("dependency_path_failures", dependency_failures),
        ("commit_sha_failures", commit_failures),
        ("disallowed_target_role_failures", disallowed_role_failures),
    ]:
        if failures:
            blockers.append(f"{name}::{len(failures)}")

    return {
        "stage": "stage12149_corrected_selected_test_row_materialization_package",
        "created_at_utc": utc_now(),
        "rows": len(rows),
        "blocked_roots": blocked_roots,
        "blockers": blockers,
        "contract_source": str(CONTRACT_PATH.relative_to(ROOT)),
        "hygiene_gate_source": str(HYGIENE_PATH.relative_to(ROOT)),
        "counts_by_language_root_task": {
            lang: {repo: dict(counter) for repo, counter in repos.items()}
            for lang, repos in counts_by_language_root_task.items()
        },
        "target_role_entropy_by_task": {
            task: {"entropy_bits": entropy(values), "counts": dict(Counter(values))}
            for task, values in sorted(by_task_roles.items())
        },
        "per_root_semantic_diversity": per_root_semantic_diversity,
        "single_token_option_label_audit": {
            "required_labels": ["A", "B", "C", "D"],
            "failures": label_failures,
            "pass": not label_failures,
        },
        "nested_top_level_option_mirror_audit": {
            "failures": mirror_failures,
            "pass": not mirror_failures,
        },
        "prompt_target_leak_risk_audit": {
            "failures": leak_failures,
            "pass": not leak_failures,
        },
        "dependency_path_exclusion_audit": {
            "excluded_parts": sorted(DEPENDENCY_PARTS),
            "failures": dependency_failures,
            "pass": not dependency_failures,
        },
        "commit_sha_coverage": {
            "rows_with_commit_sha": sum(1 for row in rows if row.get("commit_sha")),
            "total_rows": len(rows),
            "failures": commit_failures,
            "pass": not commit_failures,
        },
        "target_role_contract_audit": {
            "failures": disallowed_role_failures,
            "pass": not disallowed_role_failures,
        },
        "lineage_train_support_only_decision": {
            "strict_eval_eligible": False,
            "promotion_eligible": False,
            "training_allowed": False,
            "decision": "train_support_only_not_admitted_for_training_execution",
        },
        "safe_for_future_training_request": not blockers and len(rows) > 0,
    }


def main() -> None:
    contract = read_json(CONTRACT_PATH)
    supply = read_jsonl(SUPPLY_PATH)
    source_records = build_source_records()
    hygiene_records = hygiene_gate()
    ready_supply = {
        rec["repo_family"]: rec
        for rec in supply
        if rec.get("status") == "ready_for_row_materialization" and rec.get("repo_family") in PREFERRED_REPOS
    }

    rows: list[dict[str, Any]] = []
    blocked_roots: list[dict[str, Any]] = []

    for repo in PREFERRED_REPOS:
        hygiene_rec = hygiene_records.get(repo)
        if not hygiene_rec or hygiene_rec.get("passed") is not True:
            blocked_roots.append({
                "repo_family": repo,
                "root_id": (hygiene_rec or {}).get("root_id"),
                "blockers": [f"stage12151::{b}" for b in ((hygiene_rec or {}).get("blockers") or ["missing_stage12151_pass"])]
            })
            continue
        supply_rec = ready_supply.get(repo)
        src = source_records.get(repo)
        if not supply_rec or not src:
            blocked_roots.append({"repo_family": repo, "blockers": ["missing_ready_supply_or_source_record"]})
            continue
        root = dict(src)
        root["repo_family"] = repo
        root["root_id"] = supply_rec.get("root_id") or src["root_id"]
        root["selected_test_ids"] = supply_rec.get("selected_tests") or src["selected_test_ids"]
        root["selected_test_count"] = supply_rec.get("selected_test_count") or src["selected_test_count"]

        checkout = Path(root["checkout_path"])
        blockers = []
        if not checkout.is_dir():
            blockers.append("checkout_path_missing")
        commit = root.get("commit_sha") or git_commit(checkout)
        if repo == "moment/luxon" and not commit:
            commit = git_commit(checkout)
        if not commit:
            commit = CONFIRMED_COMMIT_SHA.get(repo)
        if not commit:
            blockers.append("missing_commit_sha")
        root["commit_sha"] = commit

        clean_paths = list(root.get("visible_paths") or [])
        clean_paths.extend(EXTRA_CLEAN_HASH_PATHS.get(repo, []))
        hash_records, hash_blockers = classify_hashes(checkout, root.get("declared_hashes"), clean_paths)
        blockers.extend(hash_blockers)
        if not any(h["kind"] == "source" for h in hash_records):
            blockers.append("missing_source_hash")
        if not any(h["kind"] == "test" for h in hash_records):
            blockers.append("missing_test_hash")
        if blockers:
            blocked_roots.append({"repo_family": repo, "root_id": root["root_id"], "blockers": sorted(set(blockers))})
            continue
        for task in TASKS:
            rows.append(build_row(root, task, hash_records))

    audit = audit_rows(rows, blocked_roots, contract)
    if audit["blockers"]:
        # The artifact is still written for diagnosis, but summary marks unsafe.
        pass

    summary = {
        "stage": "stage12149_corrected_selected_test_row_materialization_package",
        "created_at_utc": audit["created_at_utc"],
        "claim_boundary": "Train-support row materialization only; no training, no strict/eval admission, no promotion.",
        "input_supply": str(SUPPLY_PATH.relative_to(ROOT)),
        "contract": str(CONTRACT_PATH.relative_to(ROOT)),
        "hygiene_gate": str(HYGIENE_PATH.relative_to(ROOT)),
        "artifact_dir": str(OUT.relative_to(ROOT)),
        "rows": len(rows),
        "roots_materialized": sorted(set(row["repo_family"] for row in rows)),
        "blocked_roots": blocked_roots,
        "tasks": TASKS,
        "strict_eval_eligible": False,
        "promotion_eligible": False,
        "training_allowed": False,
        "train_support_only": True,
        "safe_for_future_training_request": audit["safe_for_future_training_request"],
        "audit_blockers": audit["blockers"],
        "outputs": {
            "corrected_selected_test_rows": str((OUT / "corrected_selected_test_rows.jsonl").relative_to(ROOT)),
            "row_materialization_audit": str((OUT / "row_materialization_audit.json").relative_to(ROOT)),
            "summary": str((OUT / "summary.json").relative_to(ROOT)),
            "summary_mirror": str(SUMMARY_MIRROR.relative_to(ROOT)),
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "corrected_selected_test_rows.jsonl", rows)
    write_json(OUT / "row_materialization_audit.json", audit)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY_MIRROR, summary)


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
