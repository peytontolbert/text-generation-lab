#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11528
NAME = "stage11528_web_verifier_root_supply_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_verifier_root_supply_audit.json"
ROOTS_OUT = OUT / "web_verifier_root_supply_roots.jsonl"
ROWS_OUT = OUT / "web_verifier_root_supply_rows.jsonl"
WORKLIST_OUT = OUT / "web_verifier_root_supply_worklist.jsonl"


SOURCES: list[dict[str, Any]] = [
    {
        "source_id": "stage11347_static_web",
        "rows": ART / "stage11347_web_static_verifier_maintainer_rows/web_static_verifier_train_support_rows.jsonl",
        "summary": SUMMARIES / "stage11347_web_static_verifier_maintainer_rows.json",
        "role": "train_support_static",
        "repo_family_hint": "stage11347_static",
        "verifier_backed": False,
        "executed": False,
        "strict_eval_candidate": False,
        "quality": "silver_static_verifier",
        "notes": "Static verifier assertions recovered; targeted tests not executed in this stage.",
    },
    {
        "source_id": "stage11354_executed_web",
        "rows": ART / "stage11354_web_executed_verifier_support_rows/web_executed_verifier_train_support_rows.jsonl",
        "summary": SUMMARIES / "stage11354_web_executed_verifier_support_rows.json",
        "role": "train_support",
        "repo_family_hint": "stage11354_executed",
        "verifier_backed": True,
        "executed": True,
        "strict_eval_candidate": False,
        "quality": "gold_train_support",
        "notes": "Executed verifier support rows; not strict-eligible because roots derive from prior support.",
    },
    {
        "source_id": "stage11364_sourcebot_executed",
        "rows": ART / "stage11364_web_sourcebot_executed_support_rows/web_sourcebot_executed_support_rows.jsonl",
        "summary": SUMMARIES / "stage11364_web_sourcebot_executed_support_rows.json",
        "role": "train_support",
        "repo_family_hint": "sourcebot",
        "verifier_backed": True,
        "executed": True,
        "strict_eval_candidate": False,
        "quality": "gold_train_support",
        "notes": "Executed Sourcebot verifier support root.",
    },
    {
        "source_id": "stage11373_sourcebot_extra",
        "rows": ART / "stage11373_web_sourcebot_extra_support_rows/web_sourcebot_extra_support_rows.jsonl",
        "summary": SUMMARIES / "stage11373_web_sourcebot_extra_support_rows.json",
        "role": "train_support",
        "repo_family_hint": "sourcebot",
        "verifier_backed": True,
        "executed": True,
        "strict_eval_candidate": False,
        "quality": "gold_train_support",
        "notes": "Extra executed Sourcebot support roots.",
    },
    {
        "source_id": "stage11382_sourcebot_true_abstention",
        "rows": ART / "stage11382_web_sourcebot_true_abstention_counterfactual_rows/web_sourcebot_true_abstention_counterfactual_rows.jsonl",
        "summary": SUMMARIES / "stage11382_web_sourcebot_true_abstention_counterfactual_rows.json",
        "role": "train_support_counterfactual",
        "repo_family_hint": "sourcebot",
        "verifier_backed": True,
        "executed": True,
        "strict_eval_candidate": False,
        "quality": "gold_train_support_counterfactual",
        "notes": "True-abstention counterfactual rows from Sourcebot support roots.",
    },
    {
        "source_id": "stage11388_mcp_fresh",
        "rows": ART / "stage11388_mcp_fresh_web_verifier_support_rows/mcp_fresh_web_verifier_support_rows.jsonl",
        "summary": SUMMARIES / "stage11388_mcp_fresh_web_verifier_support_rows.json",
        "role": "train_support",
        "repo_family_hint": "mcp",
        "verifier_backed": True,
        "executed": True,
        "strict_eval_candidate": False,
        "quality": "gold_train_support",
        "notes": "Executed MCP verifier support roots; same family as prior MCP support.",
    },
    {
        "source_id": "stage11394_openhands_support",
        "rows": ART / "stage11394_openhands_support_unit_verifier_train_rows/openhands_support_unit_verifier_train_rows.jsonl",
        "summary": SUMMARIES / "stage11394_openhands_support_unit_verifier_train_rows.json",
        "role": "train_support",
        "repo_family_hint": "openhands",
        "verifier_backed": True,
        "executed": True,
        "strict_eval_candidate": False,
        "quality": "gold_train_support",
        "notes": "OpenHands executed support roots; same repo family as OpenHands heldout.",
    },
    {
        "source_id": "stage11361_llama_stack_heldout",
        "rows": ART / "stage11361_web_llama_stack_executed_heldout_rows/web_llama_stack_executed_heldout_rows.jsonl",
        "summary": SUMMARIES / "stage11361_web_llama_stack_executed_heldout_rows.json",
        "role": "sealed_heldout",
        "repo_family_hint": "llama_stack",
        "verifier_backed": True,
        "executed": True,
        "strict_eval_candidate": True,
        "quality": "gold_heldout",
        "notes": "Executed Llama Stack heldout smoke root.",
    },
    {
        "source_id": "stage11390_openhands_heldout",
        "rows": ART / "stage11390_openhands_unit_verifier_heldout_candidate_rows/openhands_unit_verifier_heldout_candidate_rows.jsonl",
        "summary": SUMMARIES / "stage11390_openhands_unit_verifier_heldout_candidate_rows.json",
        "role": "sealed_heldout_candidate",
        "repo_family_hint": "openhands",
        "verifier_backed": True,
        "executed": True,
        "strict_eval_candidate": True,
        "quality": "gold_heldout_candidate",
        "notes": "Executed OpenHands heldout candidates; one Web repo family, needs final admission for broad claim.",
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_id_for(row: dict[str, Any]) -> str:
    for key in ("root_id", "source_bundle_id", "bundle_id"):
        if row.get(key):
            return str(row[key])
    row_id = str(row.get("row_id") or "")
    parts = row_id.split("::")
    return "::".join(parts[:2]) if len(parts) >= 2 else row_id


def repo_family_for(row: dict[str, Any], source: dict[str, Any]) -> str:
    for key in ("repo_family", "repo_id", "source_repo_family"):
        if row.get(key):
            return str(row[key])
    root = root_id_for(row).lower()
    for token in ("openhands", "llama", "sourcebot", "mcp", "server", "sep", "qa_lab", "code_assist"):
        if token in root:
            return token
    return str(source["repo_family_hint"])


def anti_flags(row: dict[str, Any]) -> dict[str, bool]:
    anti = row.get("anti_cheat") or {}
    return {
        "deterministic_option_shuffle": anti.get("deterministic_option_shuffle") is True,
        "executed_verifier_output_attached": anti.get("executed_verifier_output_attached") is True,
        "source_and_verifier_snippets_visible": anti.get("source_and_verifier_snippets_visible") is True,
        "target_label_not_visible_before_options": anti.get("target_label_not_visible_before_options") is True,
        "gold_value_not_used_as_label": anti.get("gold_value_not_used_as_label") is True,
        "train_support_declared": anti.get("not_strict_eval_eligible") is True or anti.get("not_train_support") is not True,
        "heldout_declared": anti.get("not_train_support") is True or anti.get("diagnostic_heldout_not_train") is True,
    }


def row_admission(row: dict[str, Any], source: dict[str, Any]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    options = row.get("opaque_options") or []
    flags = anti_flags(row)
    if row.get("language_family") != "web_js_ts_html":
        blockers.append("not_web_language")
    if len(options) < 2:
        blockers.append("missing_or_singleton_options")
    if not flags["deterministic_option_shuffle"]:
        blockers.append("deterministic_option_shuffle_missing")
    if not flags["target_label_not_visible_before_options"]:
        blockers.append("target_label_visibility_flag_missing")
    if source["executed"] and not (flags["executed_verifier_output_attached"] or source["source_id"] in {"stage11354_executed_web", "stage11364_sourcebot_executed", "stage11373_sourcebot_extra", "stage11388_mcp_fresh"}):
        blockers.append("executed_verifier_flag_missing")
    if source["role"].startswith("sealed") and not flags["heldout_declared"]:
        blockers.append("heldout_not_declared")
    if source["role"].startswith("train") and row.get("anti_cheat", {}).get("not_train_support") is True:
        blockers.append("train_row_declared_not_train")
    return ("admitted" if not blockers else "blocked", blockers)


def main() -> None:
    row_cards: list[dict[str, Any]] = []
    root_map: dict[str, dict[str, Any]] = {}
    source_cards: list[dict[str, Any]] = []
    for source in SOURCES:
        rows = load_jsonl(source["rows"])
        summary = load_json(source["summary"])
        source_cards.append(
            {
                "source_id": source["source_id"],
                "rows_path": rel(source["rows"]),
                "summary_path": rel(source["summary"]),
                "role": source["role"],
                "quality": source["quality"],
                "rows": len(rows),
                "summary_decision": summary.get("decision"),
                "summary_passed": summary.get("passed"),
                "summary_counts": summary.get("counts"),
            }
        )
        for row in rows:
            root_id = root_id_for(row)
            repo_family = repo_family_for(row, source)
            status, blockers = row_admission(row, source)
            card = {
                "source_id": source["source_id"],
                "row_id": row.get("row_id"),
                "root_id": root_id,
                "repo_family": repo_family,
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "role": source["role"],
                "quality": source["quality"],
                "verifier_backed": source["verifier_backed"],
                "executed": source["executed"],
                "strict_eval_candidate": source["strict_eval_candidate"],
                "option_count": len(row.get("opaque_options") or []),
                "anti_cheat_flags": anti_flags(row),
                "admission": status,
                "blockers": blockers,
            }
            row_cards.append(card)
            root = root_map.setdefault(
                root_id,
                {
                    "root_id": root_id,
                    "repo_family": repo_family,
                    "sources": set(),
                    "roles": set(),
                    "qualities": set(),
                    "tasks": set(),
                    "rows": 0,
                    "admitted_rows": 0,
                    "blocked_rows": 0,
                    "verifier_backed": False,
                    "executed": False,
                    "strict_eval_candidate": False,
                },
            )
            root["sources"].add(source["source_id"])
            root["roles"].add(source["role"])
            root["qualities"].add(source["quality"])
            root["tasks"].add(str(row.get("task_type")))
            root["rows"] += 1
            root["admitted_rows"] += int(status == "admitted")
            root["blocked_rows"] += int(status != "admitted")
            root["verifier_backed"] = root["verifier_backed"] or bool(source["verifier_backed"])
            root["executed"] = root["executed"] or bool(source["executed"])
            root["strict_eval_candidate"] = root["strict_eval_candidate"] or bool(source["strict_eval_candidate"])

    roots = []
    for root in root_map.values():
        role_set = set(root["roles"])
        root["sources"] = sorted(root["sources"])
        root["roles"] = sorted(root["roles"])
        root["qualities"] = sorted(root["qualities"])
        root["tasks"] = sorted(root["tasks"])
        if "sealed_heldout" in role_set or "sealed_heldout_candidate" in role_set:
            root["admit_role"] = "sealed_heldout"
        elif root["executed"] and root["verifier_backed"]:
            root["admit_role"] = "train_support"
        else:
            root["admit_role"] = "train_support_static_or_lower"
        roots.append(root)
    roots.sort(key=lambda item: (item["admit_role"], item["repo_family"], item["root_id"]))

    admitted_rows = [row for row in row_cards if row["admission"] == "admitted"]
    blocked_rows = [row for row in row_cards if row["admission"] != "admitted"]
    train_roots = [root for root in roots if root["admit_role"] == "train_support" and root["admitted_rows"] > 0]
    heldout_roots = [root for root in roots if root["admit_role"] == "sealed_heldout" and root["admitted_rows"] > 0]
    train_repo_families = sorted({root["repo_family"] for root in train_roots})
    heldout_repo_families = sorted({root["repo_family"] for root in heldout_roots})
    task_counts_train = Counter()
    task_counts_heldout = Counter()
    for row in admitted_rows:
        root = root_map[row["root_id"]]
        if root["strict_eval_candidate"]:
            task_counts_heldout[str(row["task_type"])] += 1
        elif root["executed"] and root["verifier_backed"]:
            task_counts_train[str(row["task_type"])] += 1
    blockers = Counter(blocker for row in blocked_rows for blocker in row["blockers"])
    stage11527_gate = {
        "train_roots_required": 20,
        "train_roots_available": len(train_roots),
        "heldout_roots_required": 10,
        "heldout_roots_available": len(heldout_roots),
        "fresh_web_repo_families_required": 3,
        "train_repo_families_available": len(train_repo_families),
        "heldout_repo_families_available": len(heldout_repo_families),
        "task_balance_train": dict(sorted(task_counts_train.items())),
        "task_balance_heldout": dict(sorted(task_counts_heldout.items())),
        "passes_minimum_next_web_package_gate": len(train_roots) >= 20 and len(heldout_roots) >= 10 and len(train_repo_families) >= 3,
    }
    worklist = [
        {
            "priority": 1,
            "work_item": "materialize_more_executed_web_train_roots",
            "needed": max(0, 20 - len(train_roots)),
            "details": "Need verifier-backed Web train roots beyond OpenHands/Sourcebot/MCP without using sealed heldout roots.",
        },
        {
            "priority": 2,
            "work_item": "materialize_more_sealed_web_heldout_roots",
            "needed": max(0, 10 - len(heldout_roots)),
            "details": "Need sealed source/verifier-backed Web roots from repo families not used for training.",
        },
        {
            "priority": 3,
            "work_item": "upgrade_static_web_roots_with_execution",
            "needed": len([root for root in roots if root["admit_role"] == "train_support_static_or_lower"]),
            "details": "Stage11347 static verifier roots should be rerun with focused test execution before entering gold train support.",
        },
        {
            "priority": 4,
            "work_item": "avoid_openhands_only_training",
            "needed": 1,
            "details": "Stage11523/11525 showed OpenHands-only support overfits and regresses canaries; next package must be multi-family.",
        },
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "web_verifier_supply_insufficient_for_stage11527_gate",
        "source_cards": source_cards,
        "metrics": {
            "sources": len(SOURCES),
            "rows_examined": len(row_cards),
            "admitted_rows": len(admitted_rows),
            "blocked_rows": len(blocked_rows),
            "unique_roots": len(roots),
            "train_support_roots_executed": len(train_roots),
            "train_support_repo_families": train_repo_families,
            "heldout_roots": len(heldout_roots),
            "heldout_repo_families": heldout_repo_families,
            "blocked_reasons": dict(sorted(blockers.items())),
        },
        "stage11527_gate": stage11527_gate,
        "worklist": worklist,
        "claim_boundary": [
            "This is a supply audit, not a model improvement.",
            "Existing Web rows are useful but do not yet meet the Stage11527 minimum package gate.",
            "OpenHands and Llama Stack heldout packets remain valid diagnostics; they should not be trained on.",
        ],
        "outputs": {
            "summary": rel(SUMMARY),
            "roots": rel(ROOTS_OUT),
            "rows": rel(ROWS_OUT),
            "worklist": rel(WORKLIST_OUT),
        },
    }
    write_jsonl(ROOTS_OUT, roots)
    write_jsonl(ROWS_OUT, row_cards)
    write_jsonl(WORKLIST_OUT, worklist)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": summary["metrics"], "stage11527_gate": stage11527_gate, "worklist": worklist}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
