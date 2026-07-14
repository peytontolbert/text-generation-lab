#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11451
NAME = "stage11451_non_codex_rust_verifier_log_capture"
OUT = ART / NAME
SUMMARY = OUT / "non_codex_rust_verifier_log_capture.json"
QUEUE = OUT / "non_codex_rust_verifier_log_queue.jsonl"

TARGETS = [
    {
        "repo_family": "agent_kernel_rust_wasm",
        "root_id": "local_selected_test_rust::data_agentkernel_agent_kernel_rust_wasm",
        "manifest": "/data/agentkernel/agent_kernel_rust_wasm/Cargo.toml",
        "source_paths": [
            "/data/agentkernel/agent_kernel_rust_wasm/src/lib.rs",
            "/data/agentkernel/agent_kernel_rust_wasm/src/policy.rs",
        ],
        "command": ["cargo", "test", "--manifest-path", "/data/agentkernel/agent_kernel_rust_wasm/Cargo.toml", "--lib"],
    },
    {
        "repo_family": "agent_kernel_lite_core",
        "root_id": "local_selected_test_rust::data_agent_kernel_lite_wasm_agent_kernel_lite_core",
        "manifest": "/data/agent_kernel_lite/wasm/agent_kernel_lite_core/Cargo.toml",
        "source_paths": [
            "/data/agent_kernel_lite/wasm/agent_kernel_lite_core/src/lib.rs",
            "/data/agent_kernel_lite/wasm/agent_kernel_lite_core/src/policy.rs",
        ],
        "command": ["cargo", "test", "--manifest-path", "/data/agent_kernel_lite/wasm/agent_kernel_lite_core/Cargo.toml", "--lib"],
    },
    {
        "repo_family": "scangithub_mcp_details",
        "root_id": "local_selected_test_rust::data_scangithub_mcp_details",
        "manifest": "/data/scangithub/mcp_details/Cargo.toml",
        "source_paths": [
            "/data/scangithub/mcp_details/src/distributed_server.rs",
            "/data/scangithub/mcp_details/src/lib.rs",
        ],
        "command": ["cargo", "test", "--manifest-path", "/data/scangithub/mcp_details/Cargo.toml", "--lib"],
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def snippet(path: str, max_chars: int = 2400) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    text = p.read_text(errors="replace")
    return text[:max_chars]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for target in TARGETS:
        log_path = OUT / f"{target['root_id'].replace('/', '_').replace(':', '_')}.log"
        started = now()
        try:
            proc = subprocess.run(
                target["command"],
                cwd=str(Path(target["manifest"]).parent),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=180,
                check=False,
            )
            output = proc.stdout
            returncode = proc.returncode
            timeout = False
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + "\n[TIMEOUT]\n"
            returncode = 124
            timeout = True
        log_path.write_text(output)
        source_snippets = {
            path: snippet(path)
            for path in target["source_paths"]
            if Path(path).exists()
        }
        rows.append(
            {
                "stage": STAGE,
                "repo_family": target["repo_family"],
                "root_id": target["root_id"],
                "root_lineage_key": target["root_id"],
                "language_family": "rust",
                "manifest": target["manifest"],
                "command": " ".join(target["command"]),
                "started_at_utc": started,
                "finished_at_utc": now(),
                "returncode": returncode,
                "timed_out": timeout,
                "verifier_log_path": rel(log_path),
                "verifier_status": "passed" if returncode == 0 else "failed",
                "source_snippets": source_snippets,
                "source_paths": list(source_snippets),
                "has_rust_source": bool(source_snippets),
                "has_verifier_log": bool(output.strip()),
                "materializable_for_support_rows": bool(source_snippets and output.strip()),
            }
        )

    materializable = [row for row in rows if row["materializable_for_support_rows"]]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "non_codex_rust_verifier_logs_captured",
        "counts": {
            "targets": len(TARGETS),
            "materializable_roots": len(materializable),
            "passed_verifier_roots": sum(1 for row in rows if row["returncode"] == 0),
            "failed_verifier_roots": sum(1 for row in rows if row["returncode"] != 0),
        },
        "repo_families": sorted({row["repo_family"] for row in materializable}),
        "outputs": {
            "summary": rel(SUMMARY),
            "queue": rel(QUEUE),
        },
    }
    write_jsonl(QUEUE, rows)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
