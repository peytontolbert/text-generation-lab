#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9257
NAME = "stage9257_repo_state_compiler_cache_metadata_fixture_audit"
SOURCE_STAGE = ROOT / "runs/local/artifacts/stage9256_repo_state_compiler_cache_manifest_design/repo_state_compiler_cache_manifest_design.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9256_repo_state_compiler_cache_manifest_design.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
FIXTURE = OUT_DIR / "repo_state_cache_metadata_fixture_rows.jsonl"
AUDIT = OUT_DIR / "repo_state_cache_metadata_fixture_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_STATE_COMPILER_CACHE_METADATA_FIXTURE_AUDIT_STAGE9257.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

FORBIDDEN_TEXT_FIELDS = {
    "source_text",
    "body",
    "raw_body",
    "decoder_text",
    "target_text",
    "expected_answer",
    "hidden_eval",
    "locked_eval",
}

FORBIDDEN_SUBSTRINGS = [
    "/arxiv",
    "def ",
    "class ",
    "function ",
    "#include",
    "fn ",
    "=>",
    "expected_answer",
    "hidden_eval",
    "locked_eval",
    "target_body",
]

OPAQUE_ID_RE = re.compile(r"^o[0-9a-f]{12}$")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def opaque_id(seed: str) -> str:
    return "o" + sha(seed)[:12]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_fixture_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    layers = manifest.get("cache_layers") or []
    for index, layer in enumerate(layers):
        layer_id = str(layer["layer_id"])
        repo_id = opaque_id(f"repo:{index % 3}")
        commit_hash = sha(f"commit:{index % 4}")[:40]
        path_id = opaque_id(f"path:{layer_id}:{index}")
        source_hash = sha(f"source-hash-only:{layer_id}:{index}")
        cache_key = {
            "repo_id": repo_id,
            "commit_hash": commit_hash,
            "path_id": path_id,
            "extractor_version": "metadata_fixture_v1",
            "source_sha256": source_hash,
        }
        for required in layer.get("cache_key_fields", []):
            cache_key.setdefault(required, sha(f"{required}:{layer_id}:{index}")[:32])
        rows.append(
            {
                "row_id": opaque_id(f"row:{layer_id}:{index}"),
                "stage": STAGE,
                "layer_id": layer_id,
                "modality": layer["modality"],
                "future_artifact": layer["future_artifact"],
                "cache_key": cache_key,
                "invalidation": {
                    "commit_hash": commit_hash,
                    "source_sha256": source_hash,
                    "dependency_lock_hash": cache_key.get("dependency_lock_hash"),
                    "extractor_version": cache_key.get("extractor_version") or cache_key.get("compressor_version"),
                    "must_rebuild_when_any_key_changes": True,
                },
                "input_packet": {
                    "repo_id": repo_id,
                    "path_id": path_id,
                    "metadata_only": True,
                    "opaque_ids_only": True,
                    "body_ref": None,
                    "body_text_present": False,
                },
                "target_contract": {
                    "target_ref_only": True,
                    "target_text_present": False,
                    "decoder_text_present": False,
                    "losses_enabled": [],
                },
                "authority": dict(AUTHORITY_CLOSED),
            }
        )
    return rows


def audit_rows(rows: list[dict[str, Any]], manifest: dict[str, Any], source_summary: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    layer_ids = {layer.get("layer_id") for layer in manifest.get("cache_layers") or []}
    seen_rows: set[str] = set()
    seen_cache_keys: set[str] = set()
    endpoint_failures = 0
    label_leak_rows = 0
    raw_body_rows = 0
    authority_rows = 0
    arxiv_rows = 0
    invalid_opaque_id_rows = 0
    missing_invalidation_rows = 0
    duplicate_cache_key_rows = 0

    if source_summary.get("passed") is not True:
        failures.append("source_stage9256_not_passed")
    if len(rows) != len(layer_ids):
        failures.append("fixture_rows_do_not_match_cache_layers")

    for row in rows:
        if row.get("row_id") in seen_rows:
            failures.append(f"duplicate_row_id:{row.get('row_id')}")
        seen_rows.add(str(row.get("row_id")))
        if row.get("layer_id") not in layer_ids:
            endpoint_failures += 1
        serialized = json.dumps(row, sort_keys=True).lower()
        if any(token in serialized for token in FORBIDDEN_SUBSTRINGS):
            label_leak_rows += 1
        if any(field in row for field in FORBIDDEN_TEXT_FIELDS):
            raw_body_rows += 1
        if any((row.get("authority") or {}).values()):
            authority_rows += 1
        if "/arxiv" in serialized:
            arxiv_rows += 1
        ids = [
            row.get("row_id"),
            (row.get("input_packet") or {}).get("repo_id"),
            (row.get("input_packet") or {}).get("path_id"),
            (row.get("cache_key") or {}).get("repo_id"),
            (row.get("cache_key") or {}).get("path_id"),
        ]
        if not all(isinstance(value, str) and OPAQUE_ID_RE.match(value) for value in ids):
            invalid_opaque_id_rows += 1
        invalidation = row.get("invalidation") or {}
        if not invalidation.get("commit_hash") or not invalidation.get("source_sha256") or invalidation.get("must_rebuild_when_any_key_changes") is not True:
            missing_invalidation_rows += 1
        key = json.dumps(row.get("cache_key") or {}, sort_keys=True)
        if key in seen_cache_keys:
            duplicate_cache_key_rows += 1
        seen_cache_keys.add(key)

    metrics = {
        "rows": len(rows),
        "cache_layers": len(layer_ids),
        "endpoint_failures": endpoint_failures,
        "label_leak_rows": label_leak_rows,
        "raw_body_rows": raw_body_rows,
        "authority_rows": authority_rows,
        "arxiv_path_rows": arxiv_rows,
        "invalid_opaque_id_rows": invalid_opaque_id_rows,
        "missing_invalidation_rows": missing_invalidation_rows,
        "duplicate_cache_key_rows": duplicate_cache_key_rows,
        "real_repo_body_reads_attempted": False,
        "arxiv_reads_attempted": False,
        "training_authorized_now": False,
        "model_execution_authorized_now": False,
        "runtime_authorized_now": False,
    }
    for key in [
        "endpoint_failures",
        "label_leak_rows",
        "raw_body_rows",
        "authority_rows",
        "arxiv_path_rows",
        "invalid_opaque_id_rows",
        "missing_invalidation_rows",
        "duplicate_cache_key_rows",
    ]:
        if metrics[key] != 0:
            failures.append(f"{key}_nonzero")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
    }


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
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    manifest = load_json(SOURCE_STAGE)
    source_summary = load_json(SOURCE_SUMMARY)
    rows = build_fixture_rows(manifest)
    audit = audit_rows(rows, manifest, source_summary)
    FIXTURE.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
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
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Validated metadata-only repo-state compiler cache fixtures without repo body reads, /arxiv access, runtime, training, or model execution." if audit["passed"] else "Repo-state compiler cache metadata fixture audit failed.",
        "next_best_step": "Design the first real repo_state_compiler extraction preflight that inventories metadata paths only and still blocks body reads, runtime, training, and /arxiv writes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9257 Repo-State Compiler Cache Metadata Fixture Audit",
                "",
                "Stage9257 validates the Stage9256 cache manifest with synthetic metadata-only rows.",
                "",
                "It does not read repository bodies, source files, `/arxiv`, runtime outputs, hidden evals, decoder targets, or training manifests.",
                "",
                "The audit checks opaque IDs, cache-key uniqueness, invalidation fields, authority closure, and forbidden text leakage.",
                "",
                f"Rows: {audit['metrics']['rows']}",
                f"Passed: {audit['passed']}",
                "",
                "Next: design a real extraction preflight that inventories metadata paths only before any source-body extraction is considered.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"passed": summary["passed"], "stage": STAGE, "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
