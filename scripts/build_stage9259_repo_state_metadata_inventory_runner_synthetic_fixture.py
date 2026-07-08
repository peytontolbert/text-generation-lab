#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import PurePosixPath
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9259
NAME = "stage9259_repo_state_metadata_inventory_runner_synthetic_fixture"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9258_repo_state_metadata_inventory_preflight_design.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
FIXTURE = OUT_DIR / "synthetic_repo_metadata_sidecar.json"
ROWS = OUT_DIR / "metadata_inventory_rows.jsonl"
CELL_CARD = OUT_DIR / "inventory_cell_card.json"
EXTRACTOR_PLAN = OUT_DIR / "extractor_plan_without_body_reads.json"
CACHE_PREVIEW = OUT_DIR / "cache_key_preview.jsonl"
BLOCKED = OUT_DIR / "blocked_operations_card.json"
AUDIT = OUT_DIR / "metadata_inventory_runner_synthetic_fixture_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_STATE_METADATA_INVENTORY_RUNNER_SYNTHETIC_FIXTURE_STAGE9259.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

OPAQUE_ID_RE = re.compile(r"^o[0-9a-f]{12}$")
LANGUAGE_BY_EXT = {
    ".py": "python",
    ".rs": "rust",
    ".cc": "c_family",
    ".cpp": "c_family",
    ".c": "c_family",
    ".h": "c_family",
    ".hpp": "c_family",
    ".ts": "web_js_ts_html",
    ".tsx": "web_js_ts_html",
    ".js": "web_js_ts_html",
    ".jsx": "web_js_ts_html",
    ".html": "web_js_ts_html",
}
EXTRACTORS_BY_LANGUAGE = {
    "python": ["psi_ast_cst_structure", "psi_symbol_table", "psi_import_dependency_graph", "psi_type_signature_map", "psi_call_graph"],
    "rust": ["psi_ast_cst_structure", "psi_symbol_table", "psi_import_dependency_graph", "psi_type_signature_map", "psi_call_graph"],
    "c_family": ["psi_ast_cst_structure", "psi_symbol_table", "psi_import_dependency_graph", "psi_type_signature_map", "psi_call_graph", "psi_data_control_flow"],
    "web_js_ts_html": ["psi_ast_cst_structure", "psi_symbol_table", "psi_import_dependency_graph", "psi_call_graph"],
}
FORBIDDEN_RECORD_KEYS = {
    "body",
    "raw_body",
    "source_text",
    "decoder_text",
    "target_text",
    "expected_answer",
    "hidden_eval",
    "locked_eval",
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def opaque_id(seed: str) -> str:
    return "o" + sha(seed)[:12]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_synthetic_sidecar() -> dict[str, Any]:
    files = [
        {"relative_path": "src/auth/session.py", "size_bytes": 1842, "content_sha256": sha("py-auth-session"), "mtime_bucket": "stable"},
        {"relative_path": "tests/test_auth.py", "size_bytes": 982, "content_sha256": sha("py-test-auth"), "mtime_bucket": "stable"},
        {"relative_path": "crates/core/src/lib.rs", "size_bytes": 2210, "content_sha256": sha("rs-core-lib"), "mtime_bucket": "stable"},
        {"relative_path": "crates/core/tests/parser.rs", "size_bytes": 1280, "content_sha256": sha("rs-parser-test"), "mtime_bucket": "stable"},
        {"relative_path": "src/vector.cpp", "size_bytes": 1704, "content_sha256": sha("cpp-vector"), "mtime_bucket": "stable"},
        {"relative_path": "include/vector.hpp", "size_bytes": 811, "content_sha256": sha("hpp-vector"), "mtime_bucket": "stable"},
        {"relative_path": "web/src/App.tsx", "size_bytes": 1511, "content_sha256": sha("tsx-app"), "mtime_bucket": "stable"},
        {"relative_path": "web/index.html", "size_bytes": 640, "content_sha256": sha("html-index"), "mtime_bucket": "stable"},
    ]
    return {
        "fixture_kind": "synthetic_metadata_sidecar_no_bodies",
        "repo_id": opaque_id("synthetic_repo"),
        "commit_hash": sha("synthetic_commit")[:40],
        "input_root": "synthetic://metadata-sidecar",
        "controls": {
            "metadata_only": True,
            "body_records_present": False,
            "read_source_bodies_now": False,
            "read_arxiv_now": False,
            "runtime_authorized_now": False,
            "training_authorized_now": False,
            "model_execution_authorized_now": False,
        },
        "files": files,
    }


def reject_sidecar(sidecar: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    controls = sidecar.get("controls") or {}
    if sidecar.get("fixture_kind") != "synthetic_metadata_sidecar_no_bodies":
        failures.append("wrong_fixture_kind")
    for key in ["metadata_only"]:
        if controls.get(key) is not True:
            failures.append(f"control_not_true:{key}")
    for key in ["body_records_present", "read_source_bodies_now", "read_arxiv_now", "runtime_authorized_now", "training_authorized_now", "model_execution_authorized_now"]:
        if controls.get(key) is not False:
            failures.append(f"control_not_false:{key}")
    if "/arxiv" in str(sidecar.get("input_root", "")).lower():
        failures.append("input_root_arxiv_forbidden")
    if not OPAQUE_ID_RE.match(str(sidecar.get("repo_id", ""))):
        failures.append("repo_id_not_opaque")
    if not re.match(r"^[0-9a-f]{40}$", str(sidecar.get("commit_hash", ""))):
        failures.append("commit_hash_invalid")
    for index, record in enumerate(sidecar.get("files") or []):
        keys = set(record)
        if keys & FORBIDDEN_RECORD_KEYS:
            failures.append(f"forbidden_record_key:{index}")
        path = str(record.get("relative_path", ""))
        posix = PurePosixPath(path)
        if path.startswith("/") or ".." in posix.parts or path == "" or "\x00" in path:
            failures.append(f"path_boundary_violation:{index}")
        if record.get("symlink_target"):
            failures.append(f"symlink_target_forbidden:{index}")
        if not re.match(r"^[0-9a-f]{64}$", str(record.get("content_sha256", ""))):
            failures.append(f"missing_content_sha256:{index}")
        if not isinstance(record.get("size_bytes"), int) or int(record.get("size_bytes")) < 0:
            failures.append(f"bad_size_bytes:{index}")
    return failures


def language_hint(path: str) -> str:
    return LANGUAGE_BY_EXT.get(PurePosixPath(path).suffix.lower(), "unknown")


def inventory_rows_from_sidecar(sidecar: dict[str, Any]) -> list[dict[str, Any]]:
    failures = reject_sidecar(sidecar)
    if failures:
        raise ValueError(";".join(failures))
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(sidecar["files"]):
        rel = str(record["relative_path"])
        lang = language_hint(rel)
        candidate_extractors = EXTRACTORS_BY_LANGUAGE.get(lang, ["psi_ast_cst_structure"])
        row = {
            "row_id": opaque_id(f"inventory:{sidecar['repo_id']}:{sidecar['commit_hash']}:{rel}"),
            "repo_id": sidecar["repo_id"],
            "commit_hash": sidecar["commit_hash"],
            "path_id": opaque_id(f"path:{rel}"),
            "relative_path_hash": sha(rel),
            "file_extension": PurePosixPath(rel).suffix.lower(),
            "language_hint": lang,
            "size_bytes": int(record["size_bytes"]),
            "mtime_bucket": record.get("mtime_bucket", "unknown"),
            "content_sha256": record["content_sha256"],
            "candidate_extractors": candidate_extractors,
            "cache_layers_requested": candidate_extractors,
            "body_read_authorized": False,
            "runtime_authorized": False,
            "arxiv_root_access_authorized": False,
            "authority": dict(AUTHORITY_CLOSED),
        }
        rows.append(row)
    return rows


def build_cell_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    languages: dict[str, int] = {}
    extensions: dict[str, int] = {}
    for row in rows:
        languages[row["language_hint"]] = languages.get(row["language_hint"], 0) + 1
        extensions[row["file_extension"]] = extensions.get(row["file_extension"], 0) + 1
    return {"rows": len(rows), "languages": languages, "extensions": extensions}


def build_extractor_plan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    planned: dict[str, int] = {}
    for row in rows:
        for extractor in row["candidate_extractors"]:
            planned[extractor] = planned.get(extractor, 0) + 1
    return {
        "plan_status": "METADATA_ONLY_NO_BODY_EXTRACTION",
        "extractor_counts": planned,
        "body_reads_authorized": False,
        "runtime_authorized": False,
        "training_authorized": False,
    }


def build_cache_preview(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for row in rows:
        for layer in row["cache_layers_requested"]:
            previews.append(
                {
                    "cache_key_id": opaque_id(f"cache:{layer}:{row['repo_id']}:{row['commit_hash']}:{row['path_id']}"),
                    "layer_id": layer,
                    "repo_id": row["repo_id"],
                    "commit_hash": row["commit_hash"],
                    "path_id": row["path_id"],
                    "content_sha256": row["content_sha256"],
                    "body_text_present": False,
                }
            )
    return previews


def audit_outputs(sidecar: dict[str, Any], rows: list[dict[str, Any]], plan: dict[str, Any], previews: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9258_not_passed")
    sidecar_failures = reject_sidecar(sidecar)
    failures.extend(sidecar_failures)
    serialized = json.dumps({"sidecar": sidecar, "rows": rows, "plan": plan, "previews": previews}, sort_keys=True).lower()
    for token in ["source_text", "decoder_text", "target_text", "expected_answer", "hidden_eval", "locked_eval", "/arxiv"]:
        if token in serialized:
            failures.append(f"forbidden_token_present:{token}")
    metrics = {
        "rows": len(rows),
        "languages": len({row.get("language_hint") for row in rows}),
        "cache_preview_rows": len(previews),
        "body_read_authorized_rows": sum(1 for row in rows if row.get("body_read_authorized")),
        "runtime_authorized_rows": sum(1 for row in rows if row.get("runtime_authorized")),
        "arxiv_access_authorized_rows": sum(1 for row in rows if row.get("arxiv_root_access_authorized")),
        "authority_rows": sum(1 for row in rows if any((row.get("authority") or {}).values())),
        "invalid_opaque_rows": sum(1 for row in rows if not OPAQUE_ID_RE.match(str(row.get("row_id", ""))) or not OPAQUE_ID_RE.match(str(row.get("path_id", "")))),
        "body_reads_attempted": False,
        "runtime_attempted": False,
        "training_attempted": False,
        "model_execution_attempted": False,
    }
    for key in ["body_read_authorized_rows", "runtime_authorized_rows", "arxiv_access_authorized_rows", "authority_rows", "invalid_opaque_rows"]:
        if metrics[key] != 0:
            failures.append(f"{key}_nonzero")
    if metrics["rows"] != len(sidecar.get("files") or []):
        failures.append("row_count_mismatch")
    if metrics["languages"] < 4:
        failures.append("language_coverage_lt_4")
    if plan.get("plan_status") != "METADATA_ONLY_NO_BODY_EXTRACTION":
        failures.append("bad_plan_status")
    for key in ["body_reads_authorized", "runtime_authorized", "training_authorized"]:
        if plan.get(key) is not False:
            failures.append(f"plan_control_not_false:{key}")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "authority": dict(AUTHORITY_CLOSED)}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    sidecar = build_synthetic_sidecar()
    rows = inventory_rows_from_sidecar(sidecar)
    cell_card = build_cell_card(rows)
    plan = build_extractor_plan(rows)
    previews = build_cache_preview(rows)
    blocked = {
        "blocked_operations": [
            "read_source_body",
            "read_arxiv_repository_body",
            "write_arxiv",
            "execute_runtime",
            "train_model",
            "export_checkpoint",
            "delete_any_path",
        ],
        "body_reads_attempted": False,
        "runtime_attempted": False,
        "training_attempted": False,
    }
    audit = audit_outputs(sidecar, rows, plan, previews, source)
    FIXTURE.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ROWS.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    CELL_CARD.write_text(json.dumps(cell_card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    EXTRACTOR_PLAN.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    CACHE_PREVIEW.write_text("\n".join(json.dumps(row, sort_keys=True) for row in previews) + "\n", encoding="utf-8")
    BLOCKED.write_text(json.dumps(blocked, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"]},
        "artifacts": {
            "fixture": str(FIXTURE.relative_to(ROOT)),
            "rows": str(ROWS.relative_to(ROOT)),
            "cell_card": str(CELL_CARD.relative_to(ROOT)),
            "extractor_plan": str(EXTRACTOR_PLAN.relative_to(ROOT)),
            "cache_preview": str(CACHE_PREVIEW.relative_to(ROOT)),
            "blocked": str(BLOCKED.relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Built and audited a synthetic metadata-only repo inventory runner; body reads, /arxiv access, runtime, training, and model execution remain closed." if audit["passed"] else "Synthetic metadata-only repo inventory runner failed audit.",
        "next_best_step": "Design real repository metadata inventory authorization review: permit path/stat/hash metadata collection only from an explicit non-/arxiv root, still forbidding body capture and training.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9259 Repo-State Metadata Inventory Runner Synthetic Fixture",
                "",
                "Stage9259 implements the first runner-shaped metadata inventory surface using only a synthetic sidecar.",
                "",
                "The runner does not open source files or read repository bodies. It converts metadata records into inventory rows, extractor plans, and cache-key previews.",
                "",
                f"Rows: {audit['metrics']['rows']}",
                f"Languages: {audit['metrics']['languages']}",
                f"Cache preview rows: {audit['metrics']['cache_preview_rows']}",
                f"Passed: {audit['passed']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
