#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9763
NAME = "stage9763_gemma_presence_and_runner_gap_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "gemma_presence_and_runner_gap_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GEMMA_PRESENCE_AND_RUNNER_GAP_AUDIT_STAGE9763.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

ARXIV_ROOT = Path("/arxiv")
ARXIV_REPOSITORIES = ARXIV_ROOT / "repositories"
STAGE9750_RUNBOOK = (
    ROOT
    / "runs/local/artifacts/stage9750_deferred_comparison_execution_runbook"
    / "deferred_comparison_execution_runbook.json"
)
SOURCE_ROOTS = [ROOT / "scripts", ROOT / "legacy_src"]

RUNNER_MARKERS = (
    "vllm",
    "AutoModelForCausalLM",
    "transformers.pipeline",
    "llama.cpp",
    "ollama run",
    "text-generation-inference",
    "sglang",
)
WEIGHT_SUFFIXES = (".safetensors", ".bin", ".gguf", ".ckpt", ".pth", ".pt")
MODEL_ASSET_NAMES = ("config.json", "tokenizer.json", "tokenizer.model", "tokenizer_config.json")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _display_path(path: Path, *, base: Path = ROOT) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _iter_paths(root: Path, *, max_depth: int) -> Iterable[Path]:
    if not root.exists():
        return []
    base_depth = len(root.parts)

    def _onerror(_: OSError) -> None:
        return None

    def _generator() -> Iterable[Path]:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, onerror=_onerror):
            current = Path(dirpath)
            depth = len(current.parts) - base_depth
            dirnames[:] = [name for name in dirnames if name not in {".git", ".venv", "__pycache__", "node_modules"}]
            if depth >= max_depth:
                dirnames[:] = []
            for dirname in dirnames:
                yield current / dirname
            for filename in filenames:
                yield current / filename

    return _generator()


def _gemma_candidate_roots() -> list[Path]:
    if not ARXIV_REPOSITORIES.exists():
        return []
    roots: list[Path] = []
    for path in _iter_paths(ARXIV_REPOSITORIES, max_depth=2):
        if path.is_dir() and "gemma" in path.name.lower() and not path.name.startswith("."):
            roots.append(path)
    return sorted(set(roots))



def _scan_arxiv() -> dict[str, Any]:
    gemma_dirs: list[str] = []
    weight_like: list[str] = []
    model_assets: list[str] = []
    candidate_roots = _gemma_candidate_roots()
    for root in candidate_roots:
        gemma_dirs.append(str(root))
        for path in _iter_paths(root, max_depth=4):
            if path.is_dir():
                if "gemma" in path.name.lower() and not path.name.startswith("."):
                    gemma_dirs.append(str(path))
                continue
            lowered = str(path).lower()
            name = path.name.lower()
            if "gemma" not in lowered:
                continue
            if name.endswith(WEIGHT_SUFFIXES):
                weight_like.append(str(path))
            elif name in MODEL_ASSET_NAMES:
                model_assets.append(str(path))
    gemma_12b_weight_like = [candidate for candidate in weight_like if "12b" in candidate.lower()]
    return {
        "arxiv_root_exists": ARXIV_ROOT.exists(),
        "repositories_root_exists": ARXIV_REPOSITORIES.exists(),
        "gemma_candidate_roots": [str(root) for root in candidate_roots[:50]],
        "gemma_named_directories": sorted(set(gemma_dirs))[:50],
        "gemma_named_directory_count": len(set(gemma_dirs)),
        "gemma_weight_like_files": sorted(set(weight_like))[:50],
        "gemma_weight_like_file_count": len(set(weight_like)),
        "gemma_model_asset_files": sorted(set(model_assets))[:50],
        "gemma_model_asset_file_count": len(set(model_assets)),
        "gemma_12b_weight_like_files": sorted(set(gemma_12b_weight_like)),
        "gemma_12b_present": bool(gemma_12b_weight_like),
    }


def _scan_runner_sources() -> dict[str, Any]:
    files_with_markers: list[dict[str, Any]] = []
    for root in SOURCE_ROOTS:
        if not root.exists():
            continue
        for path in _iter_paths(root, max_depth=6):
            if path.resolve() == Path(__file__).resolve():
                continue
            if not path.is_file() or path.suffix not in {".py", ".sh"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            markers = [marker for marker in RUNNER_MARKERS if marker in text]
            if markers:
                files_with_markers.append({
                    "path": str(path.relative_to(ROOT)),
                    "markers": markers,
                })
    return {
        "files_with_inference_backend_markers": files_with_markers,
        "inference_backend_file_count": len(files_with_markers),
        "concrete_gemma_runner_present": bool(files_with_markers),
    }


def build_audit() -> dict[str, Any]:
    stage9750 = load_json(STAGE9750_RUNBOOK)
    arxiv_scan = _scan_arxiv()
    runner_scan = _scan_runner_sources()
    runbook_runners = stage9750.get("runner_surfaces") if isinstance(stage9750.get("runner_surfaces"), dict) else {}

    standalone_runner_present = bool(
        runbook_runners.get("standalone_gemma_runner_present") is True or runner_scan["concrete_gemma_runner_present"]
    )
    harness_runner_present = bool(runbook_runners.get("full_product_harness_runner_present") is True)

    if arxiv_scan["gemma_12b_present"] and standalone_runner_present:
        blocker_state = "gemma_assets_and_runner_present"
    elif arxiv_scan["gemma_12b_present"]:
        blocker_state = "gemma_assets_present_runner_missing"
    elif standalone_runner_present:
        blocker_state = "runner_present_but_gemma_12b_assets_missing"
    else:
        blocker_state = "gemma_12b_assets_missing_and_runner_missing"

    failures: list[str] = []
    if stage9750.get("passed") is not True:
        failures.append("stage9750_runbook_missing_or_not_passed")
    if arxiv_scan["repositories_root_exists"] is not True:
        failures.append("arxiv_repositories_root_missing")

    return {
        "passed": not failures,
        "failures": failures,
        "arxiv_scan": arxiv_scan,
        "runner_scan": runner_scan,
        "stage9750_runner_surface": {
            "runbook_path": _display_path(STAGE9750_RUNBOOK),
            "standalone_gemma_runner_present": runbook_runners.get("standalone_gemma_runner_present") is True,
            "full_product_harness_runner_present": runbook_runners.get("full_product_harness_runner_present") is True,
            "target_100m_probe_trainer_present": (
                (runbook_runners.get("target_100m_probe_trainer") or {}).get("exists") is True
                if isinstance(runbook_runners.get("target_100m_probe_trainer"), dict)
                else False
            ),
        },
        "blocker_state": blocker_state,
        "metrics": {
            "gemma_named_directory_count": arxiv_scan["gemma_named_directory_count"],
            "gemma_weight_like_file_count": arxiv_scan["gemma_weight_like_file_count"],
            "gemma_model_asset_file_count": arxiv_scan["gemma_model_asset_file_count"],
            "gemma_12b_present": arxiv_scan["gemma_12b_present"],
            "repo_inference_backend_file_count": runner_scan["inference_backend_file_count"],
            "standalone_gemma_runner_present": standalone_runner_present,
            "full_product_harness_runner_present": harness_runner_present,
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "If Gemma-12B weights already exist outside the repo, mount or point the comparison pipeline at the exact "
        "artifact paths on /arxiv; otherwise recover or authorize Gemma-12B assets and wire a concrete runner that "
        "fills the existing Stage9748 and Stage9756/9757 comparison slots."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"]},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Audited whether /arxiv already contains Gemma assets and whether repo source exposes a concrete Gemma runner, separating code/examples from actual comparison-readiness.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9763 Gemma Presence And Runner Gap Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Gemma-named directories on /arxiv/repositories: `{summary['metrics']['gemma_named_directory_count']}`",
        f"Gemma weight-like files found: `{summary['metrics']['gemma_weight_like_file_count']}`",
        f"Gemma model-asset files found: `{summary['metrics']['gemma_model_asset_file_count']}`",
        f"Gemma-12B present: `{summary['metrics']['gemma_12b_present']}`",
        f"Repo inference-backend files: `{summary['metrics']['repo_inference_backend_file_count']}`",
        f"Standalone Gemma runner present: `{summary['metrics']['standalone_gemma_runner_present']}`",
        f"Full harness runner present: `{summary['metrics']['full_product_harness_runner_present']}`",
        "",
        "This stage checks whether the blocker is unknown availability or concrete absence. Gemma-related code/examples on /arxiv count separately from weight-like assets, and placeholder packet slots count separately from a runnable inference surface.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "blocker_state": audit["blocker_state"],
        "gemma_12b_present": audit["metrics"]["gemma_12b_present"],
        "repo_inference_backend_file_count": audit["metrics"]["repo_inference_backend_file_count"],
        "standalone_gemma_runner_present": audit["metrics"]["standalone_gemma_runner_present"],
        "full_product_harness_runner_present": audit["metrics"]["full_product_harness_runner_present"],
        "failures": audit["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
