#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11576
NAME = "stage11576_web_fresh_source_candidate_atlas"
OUT = ART / NAME
SUMMARY = OUT / "web_fresh_source_candidate_atlas.json"
CANDIDATES = OUT / "web_fresh_source_candidate_roots.jsonl"

STAGE11575 = SUMMARIES / "stage11575_web_remaining_gap_fresh_root_materializer.json"
STAGE11529 = ART / "stage11529_web_materialization_queue/web_materialization_work_items.jsonl"

LOCAL_SOURCE_TARGETS = [
    {
        "lane": "materialize_diverse_openhands_transition_roots_with_test_ids_and_fail_pass_labels",
        "git_repo_family": "openhands_openhands",
        "repo_family": "frontend",
        "repo_path": "/data/repositories/OpenHands__OpenHands/frontend",
        "max_roots": 18,
        "preferred_test_fragments": ["utils", "hooks", "routes", "components"],
    },
    {
        "lane": "materialize_llama_stack_train_analogues_with_selected_tests_and_root_disjoint_options",
        "git_repo_family": "llama_stack",
        "repo_family": "llama_stack_ui",
        "repo_path": "/data/repositories/llama-stack/src/llama_stack_ui",
        "max_roots": 14,
        "preferred_test_fragments": ["components", "lib", "app"],
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel_repo(repo: Path, path: Path) -> str:
    return str(path.relative_to(repo))


def is_test(path: Path) -> bool:
    name = path.name.lower()
    return any(token in name for token in [".test.", ".spec."]) and path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx"}


def is_source(path: Path) -> bool:
    name = path.name.lower()
    if path.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx"}:
        return False
    if any(token in name for token in [".test.", ".spec."]):
        return False
    bad_parts = {"node_modules", "dist", "build", ".next", "coverage"}
    return not any(part in bad_parts for part in path.parts)


def base_key(path: Path) -> str:
    name = path.name
    for token in [".test", ".spec"]:
        name = name.replace(token, "")
    return Path(name).stem.replace("-", "_").replace(".", "_").lower()


def choose_sources(repo: Path, test: Path, source_files: list[Path]) -> list[Path]:
    key = base_key(test)
    scored: list[tuple[int, str, Path]] = []
    test_parts = set(test.relative_to(repo).parts[:-1])
    for src in source_files:
        src_key = base_key(src)
        src_parts = set(src.relative_to(repo).parts[:-1])
        score = 0
        if src_key == key:
            score += 100
        if key and key in src_key:
            score += 40
        score += 5 * len(test_parts & src_parts)
        if "utils" in test_parts and "utils" in src_parts:
            score += 10
        if "components" in test_parts and "components" in src_parts:
            score += 10
        if score > 0:
            scored.append((score, rel_repo(repo, src), src))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:4]]


def prompt_snippet(path: Path, max_chars: int = 800) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:max_chars]


def mine_local_target(target: dict[str, Any]) -> list[dict[str, Any]]:
    repo = Path(target["repo_path"])
    if not repo.exists():
        return []
    files = [p for p in repo.rglob("*") if p.is_file()]
    test_files = [p for p in files if is_test(p)]
    source_files = [p for p in files if is_source(p)]
    preferred = target.get("preferred_test_fragments") or []

    def test_sort_key(path: Path) -> tuple[int, str]:
        rel = rel_repo(repo, path)
        priority = 0 if any(fragment in rel for fragment in preferred) else 1
        return priority, rel

    rows: list[dict[str, Any]] = []
    for test in sorted(test_files, key=test_sort_key):
        sources = choose_sources(repo, test, source_files)
        if not sources:
            continue
        root_seed = f"{target['git_repo_family']}::{rel_repo(repo, test)}::{','.join(rel_repo(repo, s) for s in sources[:2])}"
        root_hash = sha_text(root_seed)[:12]
        rows.append(
            {
                "root_id": f"stage11576::{target['git_repo_family']}::{target['repo_family']}::{root_hash}",
                "lane": target["lane"],
                "status": "source_candidate_pending_gold_verifier_transition_and_anti_cheat",
                "language_family": "web_js_ts_html",
                "git_repo_family": target["git_repo_family"],
                "repo_family": target["repo_family"],
                "repo_path": str(repo),
                "selected_verifier_path_proposal": rel_repo(repo, test),
                "selected_verifier_sha256": file_sha(test),
                "candidate_change_surface_paths": [rel_repo(repo, src) for src in sources],
                "candidate_change_surface_sha256": {rel_repo(repo, src): file_sha(src) for src in sources[:4]},
                "verifier_preview": prompt_snippet(test),
                "source_previews": {rel_repo(repo, src): prompt_snippet(src) for src in sources[:3]},
                "candidate_options_prepared": [
                    {"semantic_role": "candidate_change_surface", "path": rel_repo(repo, sources[0])},
                    {"semantic_role": "verifier_and_test_constraint", "path": rel_repo(repo, test)},
                    {"semantic_role": "symptom_or_call_path_analogue", "path": rel_repo(repo, sources[1] if len(sources) > 1 else sources[0])},
                    {"semantic_role": "abstain_insufficient_evidence", "path": None},
                ],
                "missing_for_admission": [
                    "root_task_or_bug_description",
                    "observed_verifier_transition",
                    "gold_perspective_answers",
                    "anti_cheat_decision",
                    "root_split_assignment",
                    "prompt_target_leak_audit",
                ],
                "trainable_now": False,
                "strict_eval_eligible_now": False,
            }
        )
        if len(rows) >= int(target.get("max_roots") or 10):
            break
    return rows


def mine_queue_evidence_candidates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in load_jsonl(STAGE11529):
        repo_family = str(item.get("repo_family") or "")
        git_family = str(item.get("git_repo_family") or "")
        if not any(token in repo_family.lower() or token in git_family.lower() for token in ["mcp", "modelcontextprotocol", "sep", "server"]):
            continue
        repo = Path(str(item.get("repo_path") or ""))
        if not repo.exists():
            continue
        verifier_paths = list(item.get("verifier_and_test_constraint_paths") or [])
        source_paths = list(item.get("candidate_change_surface_paths") or [])
        if not verifier_paths or not source_paths:
            continue
        root_seed = f"{git_family}::{repo_family}::{verifier_paths[0]}::{source_paths[0]}"
        root_hash = sha_text(root_seed)[:12]
        rows.append(
            {
                "root_id": f"stage11576::{git_family}::{repo_family}::{root_hash}",
                "lane": "build_all_supported_evidence_item_judgment_rows_with_decisive_vs_distractor_labels",
                "status": "evidence_candidate_pending_role_ledger_gold_and_anti_cheat",
                "language_family": "web_js_ts_html",
                "git_repo_family": git_family,
                "repo_family": repo_family,
                "repo_path": str(repo),
                "selected_verifier_path_proposal": verifier_paths[0],
                "selected_verifier_sha256": file_sha(repo / verifier_paths[0]),
                "candidate_change_surface_paths": source_paths[:4],
                "candidate_change_surface_sha256": {path: file_sha(repo / path) for path in source_paths[:4]},
                "verifier_preview": prompt_snippet(repo / verifier_paths[0]),
                "source_previews": {path: prompt_snippet(repo / path) for path in source_paths[:3]},
                "candidate_options_prepared": [
                    {"semantic_role": "candidate_change_surface", "path": source_paths[0]},
                    {"semantic_role": "verifier_and_test_constraint", "path": verifier_paths[0]},
                    {"semantic_role": "symptom_or_call_path_analogue", "path": source_paths[1] if len(source_paths) > 1 else source_paths[0]},
                    {"semantic_role": "abstain_insufficient_evidence", "path": None},
                ],
                "missing_for_admission": [
                    "role_distinct_evidence_ledger",
                    "root_task_or_bug_description",
                    "gold_evidence_item_answer",
                    "anti_cheat_decision",
                    "root_split_assignment",
                    "prompt_target_leak_audit",
                ],
                "trainable_now": False,
                "strict_eval_eligible_now": False,
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage11575 = load_json(STAGE11575)
    candidates: list[dict[str, Any]] = []
    for target in LOCAL_SOURCE_TARGETS:
        candidates.extend(mine_local_target(target))
    candidates.extend(mine_queue_evidence_candidates())

    lane_counts: dict[str, Any] = {}
    for lane in sorted({row["lane"] for row in candidates}):
        lane_rows = [row for row in candidates if row["lane"] == lane]
        lane_counts[lane] = {
            "candidate_roots": len({row["root_id"] for row in lane_rows}),
            "repo_families": sorted({row["repo_family"] for row in lane_rows}),
            "trainable_now": sum(1 for row in lane_rows if row.get("trainable_now")),
            "strict_eval_eligible_now": sum(1 for row in lane_rows if row.get("strict_eval_eligible_now")),
        }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "fresh_source_candidates_mined_pending_gold_and_anticheat",
        "candidate_roots": len(candidates),
        "lane_counts": lane_counts,
        "stage11575_supply_gap_before_atlas": stage11575.get("metrics", {}),
        "next_required_actions": [
            "Convert candidate roots into reviewed train/heldout rows by adding task descriptions, verifier transitions, gold answers, and anti-cheat decisions.",
            "Run a Stage11577 admission audit against Stage11574 gates after gold/verifier fields are filled.",
            "Do not train on Stage11576 rows directly; they are source candidates only.",
        ],
        "claim_boundary": [
            "This mines local source/test candidates only.",
            "No verifier commands were executed and no model training was run.",
            "Rows are not trainable until gold, verifier transition, split, and anti-cheat fields are completed.",
        ],
        "source_artifacts": {
            "stage11575": rel(STAGE11575),
            "stage11529_queue": rel(STAGE11529),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "candidate_roots": rel(CANDIDATES),
        },
    }
    write_jsonl(CANDIDATES, candidates)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "candidate_roots": len(candidates), "lane_counts": lane_counts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
