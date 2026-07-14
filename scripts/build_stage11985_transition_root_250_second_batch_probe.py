#!/usr/bin/env python3
"""Second-batch transition-root materialization probes for under-supplied languages.

This stage is review/admission supply only. It deliberately targets Rust, Web/JS,
and C/C++ local roots that Stage11971/11975 did not cover, runs bounded no-network
build/test probes, and emits normalized bounded transition rows for later admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11985
NAME = "stage11985_transition_root_250_second_batch_probe"
OUT = ART / NAME
SUMMARY = OUT / "transition_root_250_second_batch_probe.json"
ROWS = OUT / "transition_root_250_second_batch_review_rows.jsonl"
TMP = Path(os.environ.get("TMPDIR") or "/data/tmp") / NAME

PROTECTED_FAMILIES = {
    "tokenizers",
    "candle",
    "openhands__openhands",
    "openhands_openhands",
    "llama-stack",
    "code_assist",
}
LABELS = list("ABCDEFGHI")
STATUS_OPTIONS = [
    ("PASS_TO_PASS", "focused verifier/test executed from local source and passed"),
    ("PASS_CURRENT_BUILD", "build or static check completed successfully but no verifier body executed"),
    ("PASS_CURRENT_BUILD_AND_RUN", "build completed and a runnable verifier/check also passed"),
    ("FAIL_TO_PASS", "controlled mutation failed and restored source passed"),
    ("FAIL_TO_FAIL", "verifier ran and failed in the current local source state"),
    ("NOT_EXERCISED", "candidate verifier did not exercise the target behavior or did not collect"),
    ("INSUFFICIENT_EVIDENCE", "local dependencies or environment are underhydrated, so no trustworthy verifier transition is available"),
    ("VERIFIER_REMOVED", "verifier evidence was removed and the row should abstain"),
]
PRUNE = {".git", "node_modules", "target", "build", "dist", ".next", "__pycache__"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def repo_key(path: Path) -> str:
    parts = path.parts
    if "repositories" in parts:
        i = parts.index("repositories")
        if i + 1 < len(parts):
            return parts[i + 1].lower().replace("__", "__")
    return path.name.lower().replace(" ", "_")


def footprint(path: Path) -> dict[str, int]:
    counts = Counter()
    for root, dirs, files in os.walk(path):
        rp = Path(root)
        if set(rp.parts) & PRUNE:
            dirs[:] = []
            continue
        try:
            depth = len(rp.relative_to(path).parts) if rp != path else 0
        except ValueError:
            depth = 99
        if depth > 4:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in PRUNE]
        for f in files:
            counts["files"] += 1
            suffix = Path(f).suffix.lower()
            if suffix == ".rs": counts["rust_files"] += 1
            if suffix in {".c", ".cc", ".cpp", ".h", ".hpp"}: counts["cpp_files"] += 1
            if suffix in {".js", ".ts", ".tsx", ".jsx", ".html"}: counts["web_files"] += 1
            lf = f.lower()
            if "test" in str(rp).lower() or "test" in lf or "spec" in lf:
                counts["test_files"] += 1
    return dict(counts)


def scan_candidates() -> list[dict[str, Any]]:
    bases = [Path("/data/repositories"), ROOT]
    candidates: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for base in bases:
        if not base.exists():
            continue
        for marker, language in [("Cargo.toml", "rust"), ("package.json", "web_js_ts_html"), ("CMakeLists.txt", "c_cpp")]:
            for manifest in base.rglob(marker):
                if set(manifest.parts) & PRUNE:
                    continue
                root = manifest.parent.resolve()
                if root in seen:
                    continue
                seen.add(root)
                family = repo_key(root)
                if family in PROTECTED_FAMILIES:
                    continue
                fp = footprint(root)
                if fp.get("files", 0) <= 0 or fp.get("files", 999999) > 260:
                    continue
                if language == "rust" and fp.get("rust_files", 0) <= 0:
                    continue
                if language == "web_js_ts_html" and fp.get("web_files", 0) <= 0:
                    continue
                if language == "c_cpp" and fp.get("cpp_files", 0) <= 0:
                    continue
                priority = 0
                if language in {"rust", "web_js_ts_html", "c_cpp"}:
                    priority += 100
                priority += min(40, fp.get("test_files", 0) * 5)
                priority += max(0, 40 - fp.get("files", 0) // 5)
                candidates.append({
                    "materialization_id": f"stage11985_candidate_{len(candidates)+1:03d}",
                    "source_path": str(root),
                    "repo_family": family,
                    "repo_id": family,
                    "language_family": language,
                    "manifest": marker,
                    "footprint": fp,
                    "priority_score": priority,
                })
    candidates.sort(key=lambda r: (-int(r["priority_score"]), r["language_family"], int(r["footprint"].get("files", 999999)), r["source_path"]))
    # Interleave languages so web/rust/cpp all get attempted.
    by_lang: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        by_lang.setdefault(row["language_family"], []).append(row)
    out: list[dict[str, Any]] = []
    for _ in range(max((len(v) for v in by_lang.values()), default=0)):
        for lang in ["rust", "web_js_ts_html", "c_cpp"]:
            bucket = by_lang.get(lang) or []
            if bucket:
                out.append(bucket.pop(0))
    return out


def run_cmd(cmd: list[str], cwd: Path, timeout: int, log_name: str) -> dict[str, Any]:
    log_dir = OUT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "CUDA_VISIBLE_DEVICES": "",
        "NVIDIA_VISIBLE_DEVICES": "",
        "TMPDIR": str(TMP),
        "TEMP": str(TMP),
        "TMP": str(TMP),
        "PYTHONPYCACHEPREFIX": str(TMP / "pycache"),
        "CI": "1",
        "NO_COLOR": "1",
    })
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=timeout, check=False)
        rc = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        rc = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        timed_out = True
    duration = round(time.time() - started, 3)
    payload = {"command": cmd, "cwd": str(cwd), "returncode": rc, "timed_out": timed_out, "duration_sec": duration, "stdout_tail": stdout[-5000:], "stderr_tail": stderr[-5000:]}
    log_path = log_dir / f"{log_name}.json"
    write_json(log_path, payload)
    return {**payload, "log_path": rel(log_path)}


def classify(kind: str, result: dict[str, Any]) -> str:
    text = f"{result.get('stdout_tail') or ''}\n{result.get('stderr_tail') or ''}".lower()
    if result.get("returncode") == 0 and not result.get("timed_out"):
        if kind in {"cargo_test", "npm_test", "pnpm_test", "vitest", "ctest"}:
            return "PASS_TO_PASS"
        if kind in {"cmake_build_then_ctest", "npm_typecheck_then_test"}:
            return "PASS_CURRENT_BUILD_AND_RUN"
        return "PASS_CURRENT_BUILD"
    underhydrated = ["no such file or directory", "command not found", "cannot find module", "module_not_found", "no module named", "failed to download", "could not resolve", "package not found", "node_modules", "lockfile", "network", "timeout", "timed out"]
    if result.get("timed_out") or any(s in text for s in underhydrated):
        return "INSUFFICIENT_EVIDENCE"
    return "NOT_EXERCISED"


def shuffled_options(row_id: str, target_status: str) -> tuple[list[dict[str, Any]], str]:
    keyed = []
    for status, text in STATUS_OPTIONS:
        digest = hashlib.sha256(f"{row_id}::{status}".encode()).hexdigest()
        keyed.append((digest, status, text))
    options = []
    target_label = ""
    for label, (_, status, text) in zip(LABELS, sorted(keyed)):
        opt = {"label": label, "value": status, "text": text, "role": "verifier_transition_status", "artifact_type": "verifier_status", "canonical_value": status}
        options.append(opt)
        if status == target_status:
            target_label = label
    return options, target_label


def make_row(candidate: dict[str, Any], probe_kind: str, selected: str, result: dict[str, Any]) -> dict[str, Any]:
    status = classify(probe_kind, result)
    base = f"stage11985::{candidate['repo_family']}::{candidate['materialization_id']}::{probe_kind}::{selected}::{status}"
    row_id = base + "::" + hashlib.sha1((base + str(result.get('returncode'))).encode()).hexdigest()[:10]
    options, target_label = shuffled_options(row_id, status)
    input_text = (
        f"Language: {candidate['language_family']}\n"
        f"Perspective: transition_verifier_transition\n"
        f"Task: choose the verifier transition supported by the observed local-source command.\n"
        f"Repository family: {candidate['repo_family']}\n"
        f"Source root: {candidate['source_path']}\n"
        f"Selected verifier/build target: {selected}\n"
        f"Observed command: {' '.join(result.get('command') or [])}\n"
        f"Return code: {result.get('returncode')}\n"
        f"Stdout tail: {str(result.get('stdout_tail') or '')[-1200:]}\n"
        f"Stderr tail: {str(result.get('stderr_tail') or '')[-800:]}\n"
        "Options:\n" + "\n".join(f"{o['label']}. {o['text']}" for o in options) + "\nAnswer:"
    )
    return {
        "row_id": row_id,
        "root_id": base,
        "root_lineage_key": f"stage11985::{candidate['repo_family']}::{candidate['source_path']}",
        "source_root_id": base,
        "source_bundle_id": base,
        "repo_id": candidate["repo_id"],
        "repo_family": candidate["repo_family"],
        "language_family": candidate["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "review_queue_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "observed_verifier_transition": status,
        "selected_test_anchor": probe_kind in {"cargo_test", "npm_test", "pnpm_test", "vitest", "ctest"},
        "input_text": input_text,
        "prompt_text": input_text,
        "decoder_text": target_label,
        "target_text": target_label,
        "bounded_choice_target_label": target_label,
        "target": {"bounded_choice_target_label": target_label, "decoder_text": target_label, "semantic_value": status},
        "opaque_options": options,
        "standalone_projection_source": {
            "projection_mode": "stage11985_second_batch_transition_probe",
            "observed_verifier_transition": status,
            "selected_verifier_path": selected,
            "tool_or_verifier_observation": result,
            "opaque_options": options,
            "gold_label": target_label,
            "gold_value": status,
        },
        "loss_mask": {"bounded_choice_aux": True, "decoder_ce": True, "structured_aux": True, "transition_projection": True},
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "singleton_options": False,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": False,
            "target_value_visible_as_observed_verifier_result": True,
            "review_queue_only": True,
            "not_merged_into_train": True,
        },
        "stage11985_candidate": candidate,
    }


def package_scripts(path: Path) -> dict[str, str]:
    try:
        d = json.loads((path / "package.json").read_text(encoding="utf-8"))
    except Exception:
        return {}
    scripts = d.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


def probe_candidate(candidate: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = Path(candidate["source_path"])
    lang = candidate["language_family"]
    probes: list[tuple[str, str, list[str], int]] = []
    if lang == "rust":
        probes.append(("cargo_check", "Cargo.toml", ["cargo", "check", "--quiet"], 90))
        probes.append(("cargo_test", "Cargo.toml", ["cargo", "test", "--quiet", "--no-fail-fast"], 120))
    elif lang == "web_js_ts_html":
        scripts = package_scripts(path)
        if "typecheck" in scripts:
            probes.append(("npm_typecheck", "package.json#typecheck", ["npm", "run", "typecheck", "--", "--pretty", "false"], 90))
        elif "check" in scripts:
            probes.append(("npm_check", "package.json#check", ["npm", "run", "check"], 90))
        if "test" in scripts and "no test specified" not in scripts.get("test", ""):
            probes.append(("npm_test", "package.json#test", ["npm", "test", "--", "--run"], 120))
    elif lang == "c_cpp":
        build_dir = TMP / "cmake" / candidate["materialization_id"]
        probes.append(("cmake_configure", "CMakeLists.txt", ["cmake", "-S", ".", "-B", str(build_dir), "-DCMAKE_BUILD_TYPE=Release"], 90))
        probes.append(("cmake_build", "CMakeLists.txt", ["cmake", "--build", str(build_dir), "-j2"], 120))
        probes.append(("ctest", "CMakeLists.txt", ["ctest", "--test-dir", str(build_dir), "--output-on-failure"], 90))
    rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for kind, selected, cmd, timeout in probes[:3]:
        result = run_cmd(cmd, cwd=path, timeout=timeout, log_name=f"{candidate['materialization_id']}_{kind}")
        results.append({"kind": kind, "selected": selected, "transition": classify(kind, result), "result": result})
        rows.append(make_row(candidate, kind, selected, result))
        if kind in {"cargo_check", "cmake_configure", "npm_typecheck", "npm_check"} and result.get("returncode") != 0:
            # Avoid spending time on dependent run/test probes after failed build/hydration.
            break
    return rows, {"candidate": candidate, "probe_results": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=36)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    candidates = scan_candidates()
    selected = candidates[: args.limit]
    rows: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    for candidate in selected:
        candidate_rows, card = probe_candidate(candidate)
        rows.extend(candidate_rows)
        cards.append(card)
    write_jsonl(ROWS, rows)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "second_batch_transition_probe_complete_review_only",
        "claim_boundary": "review/admission supply only; no model training or promotion claim",
        "probe_policy": {
            "limit": args.limit,
            "target_languages": ["rust", "web_js_ts_html", "c_cpp"],
            "network_install": False,
            "gpu_visible": False,
            "protected_families_excluded": sorted(PROTECTED_FAMILIES),
        },
        "summary": {
            "candidates_scanned": len(candidates),
            "candidates_probed": len(selected),
            "rows_emitted": len(rows),
            "language_counts": dict(Counter(r["language_family"] for r in rows)),
            "status_counts": dict(Counter(r["observed_verifier_transition"] for r in rows)),
            "repo_family_counts": dict(Counter(r["repo_family"] for r in rows)),
        },
        "candidate_cards": cards,
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS), "logs": rel(OUT / "logs")},
        "next_stage_recommendation": {
            "stage": "stage11986_transition_root_250_second_batch_admission_audit",
            "action": "Admit only non-leaky rows with selected-test/build anchors and useful language/status coverage; keep all rows train-support-only until root breadth is sufficient.",
        },
    }
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "summary": artifact["summary"], "next": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
