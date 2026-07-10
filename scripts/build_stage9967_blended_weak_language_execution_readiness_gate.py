#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from safe_cleanup import safe_cleanup_checkpoints
    from safe_paths import UnsafePathError, assert_no_destructive_command_tokens, build_safe_cleanup_plan, require_safe_child_path
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.safe_cleanup import safe_cleanup_checkpoints  # type: ignore
    from scripts.safe_paths import UnsafePathError, assert_no_destructive_command_tokens, build_safe_cleanup_plan, require_safe_child_path  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9967
NAME = "stage9967_blended_weak_language_execution_readiness_gate"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9966_blended_weak_language_target100m_execution_request.json"
REQUEST = ROOT / "runs/local/artifacts/stage9966_blended_weak_language_target100m_execution_request/blended_weak_language_target100m_execution_request.json"
STAGE9963_RUNS = ROOT / "runs/local/artifacts/stage9963_blended_weak_language_target100m_contract_preflight/contract_runs"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
READINESS = OUT_DIR / "blended_weak_language_execution_readiness.json"
FIRST_SURFACE = OUT_DIR / "first_surface_execution_candidate_edit_localization.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BLENDED_WEAK_LANGUAGE_EXECUTION_READINESS_GATE_STAGE9967.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

MIN_REPO_FREE_GB = 50
MIN_TMP_FREE_GB = 20
FIRST_SURFACE_NAME = "edit_localization"
FUTURE_STAGE = 9965


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def gib_free(path: Path) -> float:
    usage = shutil.disk_usage(path)
    return usage.free / (1024 ** 3)


def _selected_surface_request() -> dict[str, Any]:
    request = load_json(REQUEST)
    rows = [row for row in (request.get("surface_requests") or []) if isinstance(row, dict)]
    for row in rows:
        if str(row.get("surface") or "") == FIRST_SURFACE_NAME:
            return row
    return {}


def future_command() -> list[str]:
    row = _selected_surface_request()
    return [str(item) for item in (row.get("command") or [])]


def future_output_dir() -> Path:
    row = _selected_surface_request()
    return ROOT / str(row.get("output_dir") or "")


def future_run_id() -> str:
    row = _selected_surface_request()
    return str(row.get("run_id") or "")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_cleanup_dry_runs() -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for surface_dir in sorted(path for path in STAGE9963_RUNS.iterdir() if path.is_dir()):
        marker = surface_dir / ".agentkernel_probe_output"
        if not marker.exists():
            failures.append(f"missing_marker:{surface_dir.name}")
            continue
        text = marker.read_text(encoding="utf-8", errors="replace")
        run_id = ""
        for line in text.splitlines():
            if line.startswith("run_id="):
                run_id = line.split("=", 1)[1]
        if not run_id:
            failures.append(f"missing_run_id_in_marker:{surface_dir.name}")
            continue
        try:
            results.append(safe_cleanup_checkpoints(repo_root=ROOT, output_dir=surface_dir, run_id=run_id, dry_run=True))
        except UnsafePathError as exc:
            failures.append(f"safe_cleanup_dry_run_failed:{surface_dir.name}:{exc}")
    return results, failures


def negative_safety_checks() -> tuple[dict[str, Any], list[str]]:
    checks: dict[str, Any] = {}
    failures: list[str] = []
    for name, kwargs in {
        "reject_arxiv_output": {"repo_root": ROOT, "output_dir": Path("/arxiv"), "run_id": "stage9965"},
        "reject_data_output": {"repo_root": ROOT, "output_dir": Path("/data"), "run_id": "stage9965"},
        "reject_root_output": {"repo_root": ROOT, "output_dir": Path("/"), "run_id": "stage9965"},
    }.items():
        try:
            build_safe_cleanup_plan(**kwargs)
            checks[name] = False
            failures.append(name)
        except UnsafePathError:
            checks[name] = True
    for token_name, cmd in {
        "reject_rm_rf_arxiv_token": ["bash", "-lc", "rm -rf /arxiv"],
        "reject_rm_rf_data_token": ["bash", "-lc", "rm -rf /data"],
    }.items():
        try:
            assert_no_destructive_command_tokens(cmd)
            checks[token_name] = False
            failures.append(token_name)
        except UnsafePathError:
            checks[token_name] = True
    return checks, failures


def future_command_checks(cmd: list[str]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    checks: dict[str, Any] = {}
    try:
        assert_no_destructive_command_tokens(cmd)
        checks["no_destructive_command_tokens"] = True
    except UnsafePathError as exc:
        checks["no_destructive_command_tokens"] = False
        failures.append(f"destructive_command_token:{exc}")
    out_dir = future_output_dir()
    try:
        require_safe_child_path(repo_root=ROOT, output_dir=out_dir, candidate=out_dir / "checkpoints")
        checks["future_checkpoint_dir_safe_child"] = True
    except UnsafePathError as exc:
        checks["future_checkpoint_dir_safe_child"] = False
        failures.append(f"future_checkpoint_dir_not_safe:{exc}")
    text = " ".join(cmd)
    for forbidden in ["/arxiv", "--decoder-ce-weight 1", "--denoise-weight 1", "--mode bounded_decoder_ce_probe"]:
        key = f"future_command_omits_{forbidden.replace('/', '_').replace(' ', '_')}"
        checks[key] = forbidden not in text
        if forbidden in text:
            failures.append(f"future_command_contains_forbidden:{forbidden}")
    checks["future_command_uses_stage9965_namespace"] = "stage9965_" in text
    if "stage9965_" not in text:
        failures.append("future_command_missing_stage9965_namespace")
    if "--execution-authorized-for-recovery-probe" not in cmd:
        failures.append("future_command_missing_execution_authorization_flag")
        checks["future_command_has_execution_authorization_flag"] = False
    else:
        checks["future_command_has_execution_authorization_flag"] = True
    return checks, failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    request = load_json(REQUEST)
    row = _selected_surface_request()
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9966_not_passed")
    if request.get("passed") is not True:
        failures.append("stage9966_request_packet_not_passed")
    if not row:
        failures.append("missing_edit_localization_surface_request")

    repo_free = gib_free(ROOT)
    tmp_free = gib_free(Path("/data/tmp"))
    root_tmp_free = gib_free(Path("/tmp"))
    disk_checks = {
        "repo_free_gb": round(repo_free, 3),
        "data_tmp_free_gb": round(tmp_free, 3),
        "root_tmp_free_gb": round(root_tmp_free, 3),
        "repo_free_gb_min": MIN_REPO_FREE_GB,
        "data_tmp_free_gb_min": MIN_TMP_FREE_GB,
        "repo_free_ok": repo_free >= MIN_REPO_FREE_GB,
        "data_tmp_free_ok": tmp_free >= MIN_TMP_FREE_GB,
    }
    if not disk_checks["repo_free_ok"]:
        failures.append("repo_filesystem_free_space_below_floor")
    if not disk_checks["data_tmp_free_ok"]:
        failures.append("data_tmp_free_space_below_floor")

    dry_runs, dry_failures = safe_cleanup_dry_runs()
    failures.extend(dry_failures)
    negative_checks, negative_failures = negative_safety_checks()
    failures.extend(negative_failures)
    cmd = future_command()
    command_checks, command_failures = future_command_checks(cmd)
    failures.extend(command_failures)

    blend_invariants = {
        "edit_localization_rows": row.get("rows"),
        "edit_localization_python_rows": (row.get("language_counts") or {}).get("python"),
        "edit_localization_c_cpp_rows": (row.get("language_counts") or {}).get("c_cpp"),
        "edit_localization_web_rows": (row.get("language_counts") or {}).get("web_js_ts_html"),
        "edit_localization_split_counts": dict(row.get("split_counts") or {}),
        "stage9961_weak_language_recovery_preserved": int((row.get("language_counts") or {}).get("python", 0) or 0) == 24 and int((row.get("language_counts") or {}).get("c_cpp", 0) or 0) == 30,
        "stage9944_targeted_web_refresh_preserved": int((row.get("language_counts") or {}).get("web_js_ts_html", 0) or 0) == 45,
        "request_status": row.get("request_status"),
    }
    if blend_invariants["edit_localization_rows"] != 120:
        failures.append("edit_localization_rows_not_120")
    if blend_invariants["edit_localization_python_rows"] != 24:
        failures.append("edit_localization_python_rows_not_24")
    if blend_invariants["edit_localization_c_cpp_rows"] != 30:
        failures.append("edit_localization_c_cpp_rows_not_30")
    if blend_invariants["edit_localization_web_rows"] != 45:
        failures.append("edit_localization_web_rows_not_45")
    if blend_invariants["request_status"] != "awaiting_explicit_execution_authorization":
        failures.append("request_status_not_waiting_authorization")

    candidate = {
        "selected_surface": FIRST_SURFACE_NAME,
        "future_stage": FUTURE_STAGE,
        "future_run_id": future_run_id(),
        "future_output_dir": str(future_output_dir().relative_to(ROOT)),
        "command": cmd,
        "reason": "Run the successor blended edit-localization surface first because it carries both the original web recovery rows and the newly added python/c_cpp/web weak-language recovery roots.",
        "blend_invariants": blend_invariants,
        "requires_explicit_user_confirmation_before_execution": True,
        "requires_this_stage_passed": True,
        "authority": dict(AUTHORITY_CLOSED),
    }
    FIRST_SURFACE.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readiness = {
        "passed": not failures,
        "failures": failures,
        "disk_checks": disk_checks,
        "safe_cleanup_dry_runs": dry_runs,
        "safe_cleanup_dry_run_failures": dry_failures,
        "negative_safety_checks": negative_checks,
        "future_command_checks": command_checks,
        "selected_first_surface_candidate": str(FIRST_SURFACE.relative_to(ROOT)),
        "source_stage9966_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "blend_invariants": blend_invariants,
        "authority": dict(AUTHORITY_CLOSED),
    }
    READINESS.write_text(json.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "With explicit confirmation, run Stage9965 edit-localization successor blended target-100M execution using the Stage9967 candidate command; otherwise stop before execution and keep the successor request packet as the authoritative handoff."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": readiness["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "failures": failures,
            "repo_free_gb": disk_checks["repo_free_gb"],
            "data_tmp_free_gb": disk_checks["data_tmp_free_gb"],
            "safe_cleanup_dry_run_count": len(dry_runs),
            "negative_safety_checks_passed": all(negative_checks.values()),
            "future_command_safe": not command_failures,
            "selected_first_surface": FIRST_SURFACE_NAME,
            "selected_python_edit_rows": blend_invariants["edit_localization_python_rows"],
            "selected_c_cpp_edit_rows": blend_invariants["edit_localization_c_cpp_rows"],
            "selected_web_edit_rows": blend_invariants["edit_localization_web_rows"],
            "execution_authorized_now": False,
            "model_execution_authorized_next": False,
        },
        "artifacts": {
            "readiness": str(READINESS.relative_to(ROOT)),
            "first_surface_candidate": str(FIRST_SURFACE.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Validated disk, cleanup, namespace, and successor blended-manifest readiness for a first real target-100M execution candidate on the weak-language recovery mix, without authorizing or running the probe.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9967 Blended Weak-Language Execution Readiness Gate",
        "",
        f"Passed: `{summary['passed']}`",
        f"Repo free GB: `{disk_checks['repo_free_gb']}`",
        f"/data/tmp free GB: `{disk_checks['data_tmp_free_gb']}`",
        f"Safe cleanup dry-runs: `{len(dry_runs)}`",
        f"Selected first surface: `{FIRST_SURFACE_NAME}`",
        f"Future stage: `{FUTURE_STAGE}`",
        f"Selected python edit rows: `{blend_invariants['edit_localization_python_rows']}`",
        f"Selected C/C++ edit rows: `{blend_invariants['edit_localization_c_cpp_rows']}`",
        f"Selected web edit rows: `{blend_invariants['edit_localization_web_rows']}`",
        "Execution authorized now: `False`",
        "",
        "This stage validates disk space, safe-cleanup dry-runs, negative /arxiv and /data rejection checks, and preservation of the successor weak-language edit-localization rows. It does not run model execution.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "repo_free_gb": disk_checks["repo_free_gb"], "data_tmp_free_gb": disk_checks["data_tmp_free_gb"]}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
