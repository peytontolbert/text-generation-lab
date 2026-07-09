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
STAGE = 9697
NAME = "stage9697_disk_safe_cleanup_execution_readiness_gate"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9696_capped_multisurface_structured_target_100m_contract_preflight.json"
STAGE9695_TICKET = ROOT / "runs/local/artifacts/stage9695_multisurface_structured_tiny_execution_review/multisurface_structured_tiny_execution_review_inactive.json"
STAGE9696_RUNS = ROOT / "runs/local/artifacts/stage9696_capped_multisurface_structured_target_100m_contract_preflight/contract_runs"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
READINESS = OUT_DIR / "disk_safe_cleanup_execution_readiness.json"
FIRST_SURFACE = OUT_DIR / "first_surface_execution_candidate_symbol_binding.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DISK_SAFE_CLEANUP_EXECUTION_READINESS_GATE_STAGE9697.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

MIN_REPO_FREE_GB = 50
MIN_TMP_FREE_GB = 20
FIRST_SURFACE_NAME = "symbol_binding"
FUTURE_STAGE = 9698
FUTURE_RUN_ID = "stage9698_symbol_binding_target_100m_structured_tiny_probe"
FUTURE_OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9698_symbol_binding_target_100m_structured_tiny_probe/symbol_binding_probe"
FUTURE_MANIFEST = "runs/local/artifacts/stage9695_multisurface_structured_tiny_execution_review/tiny_structured_manifests/symbol_binding_tiny.jsonl"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def gib_free(path: Path) -> float:
    usage = shutil.disk_usage(path)
    return usage.free / (1024 ** 3)


def future_command() -> list[str]:
    return [
        "python",
        "legacy_src/scripts/train_agentkernel_lite_encdec.py",
        "--repo-root", str(ROOT),
        "--manifest", FUTURE_MANIFEST,
        "--mode", "symbol_binding_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
        "--tokenizer-json", "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
        "--tokenizer-config", "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
        "--tokenizer-hashlock", "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
        "--max-train-rows", "32",
        "--max-eval-rows", "16",
        "--max-strict-rows", "16",
        "--max-steps", "8",
        "--batch-size", "2",
        "--learning-rate", "5e-5",
        "--max-encoder-tokens", "512",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.0",
        "--structured-aux-weight", "1.0",
        "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save", "1",
        "--output-dir", str(FUTURE_OUTPUT_DIR.relative_to(ROOT)),
        "--run-id", FUTURE_RUN_ID,
        "--execution-authorized-for-recovery-probe",
    ]


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
    for surface_dir in sorted(path for path in STAGE9696_RUNS.iterdir() if path.is_dir()):
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
            result = safe_cleanup_checkpoints(repo_root=ROOT, output_dir=surface_dir, run_id=run_id, dry_run=True)
            results.append(result)
        except UnsafePathError as exc:
            failures.append(f"safe_cleanup_dry_run_failed:{surface_dir.name}:{exc}")
    return results, failures


def negative_safety_checks() -> tuple[dict[str, Any], list[str]]:
    checks: dict[str, Any] = {}
    failures: list[str] = []
    for name, kwargs in {
        "reject_arxiv_output": {"repo_root": ROOT, "output_dir": Path("/arxiv"), "run_id": "stage9697"},
        "reject_data_output": {"repo_root": ROOT, "output_dir": Path("/data"), "run_id": "stage9697"},
        "reject_root_output": {"repo_root": ROOT, "output_dir": Path("/"), "run_id": "stage9697"},
    }.items():
        try:
            build_safe_cleanup_plan(**kwargs)
            checks[name] = False
            failures.append(name)
        except UnsafePathError:
            checks[name] = True
    try:
        assert_no_destructive_command_tokens(["bash", "-lc", "rm -rf /arxiv"])
        checks["reject_rm_rf_arxiv_token"] = False
        failures.append("reject_rm_rf_arxiv_token")
    except UnsafePathError:
        checks["reject_rm_rf_arxiv_token"] = True
    try:
        assert_no_destructive_command_tokens(["bash", "-lc", "rm -rf /data"])
        checks["reject_rm_rf_data_token"] = False
        failures.append("reject_rm_rf_data_token")
    except UnsafePathError:
        checks["reject_rm_rf_data_token"] = True
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
    try:
        require_safe_child_path(repo_root=ROOT, output_dir=FUTURE_OUTPUT_DIR, candidate=FUTURE_OUTPUT_DIR / "checkpoints")
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
    if f"stage{STAGE}_" in text or "stage9696_" in text:
        failures.append("future_command_reuses_readiness_or_contract_stage_namespace")
        checks["future_command_uses_fresh_stage9698_namespace"] = False
    else:
        checks["future_command_uses_fresh_stage9698_namespace"] = "stage9698_" in text
        if "stage9698_" not in text:
            failures.append("future_command_missing_stage9698_namespace")
    return checks, failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    ticket = load_json(STAGE9695_TICKET)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9696_not_passed")
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
    stale_stage9695_namespace_rows = []
    for surface, old_cmd in (ticket.get("surface_commands") or {}).items():
        if "stage9696_" in " ".join(str(part) for part in old_cmd):
            stale_stage9695_namespace_rows.append(surface)
    candidate = {
        "selected_surface": FIRST_SURFACE_NAME,
        "future_stage": FUTURE_STAGE,
        "future_run_id": FUTURE_RUN_ID,
        "future_output_dir": str(FUTURE_OUTPUT_DIR.relative_to(ROOT)),
        "command": cmd,
        "reason": "Run one structured surface first after Stage9696 contract-only success; symbol binding is the smallest recovered source-backed surface and excludes decoder CE.",
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
        "stale_stage9695_future_command_surfaces": stale_stage9695_namespace_rows,
        "selected_first_surface_candidate": str(FIRST_SURFACE.relative_to(ROOT)),
        "source_stage9696_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "authority": dict(AUTHORITY_CLOSED),
    }
    READINESS.write_text(json.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "With explicit confirmation, run Stage9698 symbol-binding target-100M tiny structured execution using the Stage9697 candidate command; otherwise stop before execution or inspect readiness artifacts."
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
            "execution_authorized_now": False,
            "model_execution_authorized_next": False,
        },
        "artifacts": {"readiness": str(READINESS.relative_to(ROOT)), "first_surface_candidate": str(FIRST_SURFACE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Validated disk and cleanup readiness for one future tiny structured target-100M execution candidate, but did not authorize or run execution.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9697 Disk/Safe-Cleanup Execution Readiness Gate",
        "",
        f"Passed: `{summary['passed']}`",
        f"Repo free GB: `{disk_checks['repo_free_gb']}`",
        f"/data/tmp free GB: `{disk_checks['data_tmp_free_gb']}`",
        f"Safe cleanup dry-runs: `{len(dry_runs)}`",
        f"Selected first surface: `{FIRST_SURFACE_NAME}`",
        f"Future stage: `{FUTURE_STAGE}`",
        "Execution authorized now: `False`",
        "",
        "This stage validates disk space, safe-cleanup dry-runs, negative /arxiv and /data rejection checks, and the first-surface future command. It does not run model execution.",
        "",
        "No runtime, source/body emission, Gemma, harness, scoring, decoder CE, denoise CE, checkpoint export, model execution, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "repo_free_gb": disk_checks["repo_free_gb"], "data_tmp_free_gb": disk_checks["data_tmp_free_gb"], "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
