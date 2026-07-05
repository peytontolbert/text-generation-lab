#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8889
NAME = "stage8889_metadata_inventory_inactive_ticket_gate"
DESIGN_SUMMARY = ROOT / "runs/summaries/stage8883_metadata_only_commit_inventory_preflight_design.json"
DESIGN_MANIFEST = ROOT / "runs/local/artifacts/stage8883_metadata_only_commit_inventory_preflight_design/metadata_only_commit_inventory_preflight_design.jsonl"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_INVENTORY_INACTIVE_TICKET_GATE_STAGE8889.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

DENIED_OPERATIONS = [
    "walk_arxiv_repositories",
    "walk_repository_tree",
    "read_git_commit_object",
    "read_commit_message_body",
    "read_diff_body",
    "read_patch_body",
    "read_source_body",
    "emit_training_row",
    "emit_decoder_target",
    "open_model_execution",
    "open_runtime_execution",
]

ALLOWED_FUTURE_METADATA_FIELDS = [
    "repo_id",
    "repo_path_alias",
    "source_inventory_id",
    "source_provenance_id",
    "license_route",
    "contamination_route",
    "locked_eval_exclusion",
    "commit_count_cap",
    "branch_policy",
    "commit_sha",
    "parent_sha",
    "author_time_bucket",
    "commit_message_hash",
    "changed_file_count",
    "diff_line_count",
    "test_file_touch_count",
    "config_file_touch_count",
    "generated_vendor_lockfile_touch_count",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_registry() -> dict[str, Any]:
    return load_json(REGISTRY) if REGISTRY.exists() else {"rows": [], "metrics": {}}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    design = load_json(DESIGN_SUMMARY)
    rows = load_jsonl(DESIGN_MANIFEST)
    ticket = {
        "ticket_id": "metadata_only_commit_inventory__draft_inactive",
        "ticket_status": "DRAFT_INACTIVE",
        "requested_stage": "future_metadata_inventory_only",
        "request_scope": "metadata_header_inventory_schema_only",
        "requires_explicit_user_authorization": True,
        "requires_fresh_preflight_gate": True,
        "execution_authorized_now": False,
        "repository_walks_now": 0,
        "commit_reads_now": 0,
        "diff_body_reads_now": 0,
        "patch_body_reads_now": 0,
        "source_body_reads_now": 0,
        "training_rows_now": 0,
        "allowed_operations_now": [],
        "denied_operations": DENIED_OPERATIONS,
        "allowed_future_metadata_fields": ALLOWED_FUTURE_METADATA_FIELDS,
        "future_caps_require_new_ticket": {
            "max_repositories": 0,
            "max_commit_headers_per_repo": 0,
            "max_diffstat_only_commits_per_repo": 0,
            "patch_bodies": 0,
            "source_bodies": 0,
            "training_rows": 0,
        },
        "forbidden_roots_without_explicit_ticket": ["/", "/data", "/arxiv", str(ROOT)],
        "output_scope_now": {
            "writes_ticket_only": True,
            "writes_inventory_rows": False,
            "writes_training_rows": False,
            "writes_decoder_targets": False,
        },
        "authority": AUTHORITY_CLOSED,
    }
    checks = [
        {"item": "design_passed", "passed": design.get("passed") is True},
        {"item": "design_rows_present", "passed": len(rows) > 0},
        {"item": "ticket_inactive", "passed": ticket["ticket_status"] == "DRAFT_INACTIVE"},
        {"item": "requires_explicit_user_authorization", "passed": ticket["requires_explicit_user_authorization"] is True},
        {"item": "no_repository_walks_now", "passed": ticket["repository_walks_now"] == 0},
        {"item": "no_commit_reads_now", "passed": ticket["commit_reads_now"] == 0},
        {"item": "no_diff_or_patch_body_reads_now", "passed": ticket["diff_body_reads_now"] == 0 and ticket["patch_body_reads_now"] == 0},
        {"item": "no_source_body_reads_now", "passed": ticket["source_body_reads_now"] == 0},
        {"item": "no_training_rows_now", "passed": ticket["training_rows_now"] == 0},
        {"item": "allowed_operations_empty", "passed": ticket["allowed_operations_now"] == []},
        {"item": "future_caps_zero", "passed": all(value == 0 for value in ticket["future_caps_require_new_ticket"].values())},
        {"item": "arxiv_protected", "passed": "/arxiv" in ticket["forbidden_roots_without_explicit_ticket"]},
        {"item": "authority_closed", "passed": not any(AUTHORITY_CLOSED.values())},
    ]
    failures = [check for check in checks if not check["passed"]]
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "checks": len(checks),
            "failures": len(failures),
            "ticket_status": ticket["ticket_status"],
            "repository_walks_now": 0,
            "commit_reads_now": 0,
            "diff_body_reads_now": 0,
            "patch_body_reads_now": 0,
            "source_body_reads_now": 0,
            "training_rows_now": 0,
            "allowed_operations_now": 0,
            "future_inventory_requires_new_ticket": True,
            "training_authorized": False,
            "model_execution_authorized_now": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "checks": checks,
        "ticket": ticket,
        "artifacts": {
            "ticket": str((OUT_DIR / "metadata_inventory_inactive_ticket.json").relative_to(ROOT)),
            "source_design": str(DESIGN_SUMMARY.relative_to(ROOT)),
            "source_manifest": str(DESIGN_MANIFEST.relative_to(ROOT)),
        },
        "decision": "Metadata inventory ticket gate passed as inactive/no-read/no-walk/no-training." if not failures else "Metadata inventory inactive ticket gate failed.",
        "next_best_step": "No optional recovery gaps remain active. Either explicitly authorize the one-run Stage8890 structured probe later, or continue improving no-execution telemetry/gate tests.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "metadata_inventory_inactive_ticket.json").write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "metadata_inventory_inactive_ticket_gate_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8889 Metadata Inventory Inactive Ticket Gate",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage closes the optional commit inventory branch as an inactive ticket only.",
        "",
        "Current reads/writes:",
        "",
        "- repository walks now: `0`",
        "- commit reads now: `0`",
        "- diff/patch/source body reads now: `0`",
        "- training rows now: `0`",
        "",
        "`/arxiv` remains protected and is not walked.",
        "",
    ]), encoding="utf-8")
    registry = load_registry()
    rows_reg = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows_reg.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card["passed"],
        "path": str(SUMMARY),
        "authority": AUTHORITY_CLOSED,
        "next_best_step": card["next_best_step"],
    })
    rows_reg = sorted(rows_reg, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows_reg
    registry["passed"] = card["passed"]
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows_reg),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8889 Metadata Inventory Inactive Ticket"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8889 closes the optional metadata-only commit inventory branch as a draft inactive ticket. It performs no repository walk, no commit read, no diff/patch/source body read, no mining, and no training row emission. Future metadata inventory would require a separate explicit ticket with caps.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
