#!/usr/bin/env python3
"""Run temporary semantic FAIL_TO_PASS probes for Stage12053."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path("/data/tmp/stage12053_semantic_fail_to_pass_probes")
OUT = Path("runs/local/artifacts/stage12053_semantic_fail_to_pass_floor_closure_rows/semantic_fail_to_pass_probe_results.json")


def run(cmd: str, cwd: Path, timeout: int = 18) -> dict[str, Any]:
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
    combined = ((stdout or "") + "\n" + (stderr or "")).strip()
    return {
        "command": cmd,
        "cwd": str(cwd),
        "returncode": 124 if timed_out else proc.returncode,
        "stdout_tail": "\n".join(combined.splitlines()[-24:]) or ("command timed out" if timed_out else ""),
        "timed_out": timed_out,
    }


def copy_repo(src: Path, dst: Path, ignore: tuple[str, ...]) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*ignore))


def mutate_file(path: Path, old: str, new: str) -> str:
    original = path.read_text()
    if old not in original:
        raise RuntimeError(f"mutation target not found in {path}: {old!r}")
    path.write_text(original.replace(old, new, 1))
    return original


REPOS: dict[str, dict[str, Any]] = {
    "method_comparison": {
        "src": Path("/data/repositories/method_comparison"),
        "ignore": ("__pycache__", ".pytest_cache"),
        "language_family": "python",
    },
    "SWE-agent__SWE-ReX": {
        "src": Path("/data/repositories/SWE-agent__SWE-ReX"),
        "ignore": (".git", "__pycache__", ".pytest_cache"),
        "language_family": "python",
    },
    "openclaw__clawhub": {
        "src": Path("/data/repositories/openclaw__clawhub"),
        "ignore": (".git", ".next", ".convex", "dist", "node_modules"),
        "language_family": "web_js_ts_html",
    },
}


SPECS: list[dict[str, str]] = [
    # Python filter parser: semantic operator and boolean-composition changes.
    {"repo_family": "method_comparison", "selected_verifier_path": "test_sanitizer.py", "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12053_pytest_cache test_sanitizer.py", "mutation_file": "sanitizer.py", "mutation_kind": "and_operator_becomes_or", "old": "result &= _evaluate_node(df, node.values[i])", "new": "result |= _evaluate_node(df, node.values[i])"},
    {"repo_family": "method_comparison", "selected_verifier_path": "test_sanitizer.py", "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12053_pytest_cache test_sanitizer.py", "mutation_file": "sanitizer.py", "mutation_kind": "or_operator_becomes_and", "old": "result |= _evaluate_node(df, node.values[i])", "new": "result &= _evaluate_node(df, node.values[i])"},
    {"repo_family": "method_comparison", "selected_verifier_path": "test_sanitizer.py", "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12053_pytest_cache test_sanitizer.py", "mutation_file": "sanitizer.py", "mutation_kind": "negation_removed", "old": "return ~_evaluate_node(df, node.operand)", "new": "return _evaluate_node(df, node.operand)"},
    {"repo_family": "method_comparison", "selected_verifier_path": "test_sanitizer.py", "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12053_pytest_cache test_sanitizer.py", "mutation_file": "sanitizer.py", "mutation_kind": "in_operator_replaced_by_equality", "old": "ast.In:    lambda c, v: df[c].isin(v),", "new": "ast.In:    lambda c, v: df[c] == v,"},
    # Footer/docs verifier: content/config semantics, not syntax failures.
    {"repo_family": "SWE-agent__SWE-ReX", "selected_verifier_path": "test_footer.py", "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12053_pytest_cache test_footer.py", "mutation_file": "mkdocs.yml", "mutation_kind": "mkdocs_include_markdown_removed", "old": "include-markdown", "new": "include-markdown-disabled"},
    {"repo_family": "SWE-agent__SWE-ReX", "selected_verifier_path": "test_footer.py", "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12053_pytest_cache test_footer.py", "mutation_file": "mkdocs.yml", "mutation_kind": "navigation_css_removed", "old": "css/navigation_cards.css", "new": "css/navigation_cards_disabled.css"},
    {"repo_family": "SWE-agent__SWE-ReX", "selected_verifier_path": "test_footer.py", "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12053_pytest_cache test_footer.py", "mutation_file": "docs/_footer.md", "mutation_kind": "bug_report_link_removed", "old": "bug_report", "new": "bug_report_disabled"},
    {"repo_family": "SWE-agent__SWE-ReX", "selected_verifier_path": "test_footer.py", "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12053_pytest_cache test_footer.py", "mutation_file": "docs/_footer.md", "mutation_kind": "github_footer_link_removed", "old": "GitHub", "new": "CodeHost"},
    {"repo_family": "SWE-agent__SWE-ReX", "selected_verifier_path": "test_footer.py", "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12053_pytest_cache test_footer.py", "mutation_file": "docs/_footer.md", "mutation_kind": "slack_footer_link_removed", "old": "Slack", "new": "Chat"},
    {"repo_family": "SWE-agent__SWE-ReX", "selected_verifier_path": "test_footer.py", "command": "python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12053_pytest_cache test_footer.py", "mutation_file": "docs/index.md", "mutation_kind": "index_footer_include_removed", "old": "{% include-markdown \"_footer.md\" %}", "new": "{% include-markdown \"_footer_disabled.md\" %}"},
    # OpenClaw token encoding and auth/access/rate-limit semantics.
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/tokens.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/tokens.test.ts", "mutation_file": "convex/lib/tokens.ts", "mutation_kind": "token_prefix_changed", "old": 'export const API_TOKEN_PREFIX = "clh_";', "new": 'export const API_TOKEN_PREFIX = "clx_";'},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/tokens.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/tokens.test.ts", "mutation_file": "convex/lib/tokens.ts", "mutation_kind": "token_prefix_length_shortened", "old": "const prefix = token.slice(0, 12);", "new": "const prefix = token.slice(0, 10);"},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/tokens.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/tokens.test.ts", "mutation_file": "convex/lib/tokens.ts", "mutation_kind": "hex_zero_padding_removed", "old": 'byte.toString(16).padStart(2, "0")', "new": 'byte.toString(16).padStart(1, "0")'},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/tokens.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/tokens.test.ts", "mutation_file": "convex/lib/tokens.ts", "mutation_kind": "base64url_plus_not_replaced", "old": 'return base64.replace(/\\+/g, "-").replace(/\\//g, "_").replace(/=+$/g, "");', "new": 'return base64.replace(/\\+/g, "+").replace(/\\//g, "_").replace(/=+$/g, "");'},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/tokens.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/tokens.test.ts", "mutation_file": "convex/lib/tokens.ts", "mutation_kind": "base64url_padding_not_stripped", "old": 'return base64.replace(/\\+/g, "-").replace(/\\//g, "_").replace(/=+$/g, "");', "new": 'return base64.replace(/\\+/g, "-").replace(/\\//g, "_");'},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/skillSlugValidator.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/skillSlugValidator.test.ts", "mutation_file": "convex/lib/skillSlugValidator.ts", "mutation_kind": "slug_lowercase_removed", "old": 'return (raw ?? "").trim().toLowerCase();', "new": 'return (raw ?? "").trim();'},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/skillSlugValidator.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/skillSlugValidator.test.ts", "mutation_file": "convex/lib/skillSlugValidator.ts", "mutation_kind": "slug_min_length_tightened", "old": "const MIN_SLUG_LENGTH = 3;", "new": "const MIN_SLUG_LENGTH = 4;"},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/skillSlugValidator.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/skillSlugValidator.test.ts", "mutation_file": "convex/lib/skillSlugValidator.ts", "mutation_kind": "slug_max_length_tightened", "old": "const MAX_SLUG_LENGTH = 48;", "new": "const MAX_SLUG_LENGTH = 47;"},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/skillSlugValidator.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/skillSlugValidator.test.ts", "mutation_file": "convex/lib/skillSlugValidator.ts", "mutation_kind": "reserved_slug_check_disabled", "old": "if (!options.allowReserved && RESERVED_SKILL_SLUGS.has(normalized)) {", "new": "if (!options.allowReserved && false && RESERVED_SKILL_SLUGS.has(normalized)) {"},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/skillSlugValidator.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/skillSlugValidator.test.ts", "mutation_file": "convex/lib/skillSlugValidator.ts", "mutation_kind": "single_char_searchable_slug_rejected", "old": "if (normalized.length === 1) {", "new": "if (normalized.length === 2) {"},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/access.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/access.test.ts", "mutation_file": "convex/lib/access.ts", "mutation_kind": "missing_auth_error_changed", "old": 'if (!userId) throw new Error("Unauthorized");', "new": 'if (!userId) throw new Error("User not found");'},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/access.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/access.test.ts", "mutation_file": "convex/lib/access.ts", "mutation_kind": "role_assertion_inverted", "old": "if (!user.role || !allowed.includes(user.role as Role)) {", "new": "if (!user.role || allowed.includes(user.role as Role)) {"},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/access.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/access.test.ts", "mutation_file": "convex/lib/access.ts", "mutation_kind": "moderator_role_removed", "old": 'assertRole(user, ["admin", "moderator"]);', "new": 'assertRole(user, ["admin"]);'},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/httpRateLimit.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/httpRateLimit.test.ts", "mutation_file": "convex/lib/httpRateLimit.ts", "mutation_kind": "download_ip_limit_lowered", "old": "download: { ip: 1200, key: 6000, adminKey: 60000 },", "new": "download: { ip: 1199, key: 6000, adminKey: 60000 },"},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/httpRateLimit.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/httpRateLimit.test.ts", "mutation_file": "convex/lib/httpRateLimit.ts", "mutation_kind": "retry_after_uses_epoch_reset", "old": '"Retry-After": String(resetDelaySeconds)', "new": '"Retry-After": String(resetSeconds)'},
    {"repo_family": "openclaw__clawhub", "selected_verifier_path": "convex/lib/httpRateLimit.test.ts", "command": "./node_modules/.bin/vitest run --globals convex/lib/httpRateLimit.test.ts", "mutation_file": "convex/lib/httpRateLimit.ts", "mutation_kind": "unknown_ip_write_key_uses_download_scope", "old": 'if (kind !== "download") return `ip:unknown:${kind}`;', "new": 'if (kind !== "download") return `ip:unknown:download:${getDownloadRateLimitScope(request)}`;'},
]


def probe(spec: dict[str, str], roots: dict[str, Path]) -> dict[str, Any]:
    repo_family = spec["repo_family"]
    repo = roots[repo_family]
    target_file = repo / spec["mutation_file"]
    baseline = run(spec["command"], repo)
    original = mutate_file(target_file, spec["old"], spec["new"])
    mutant = run(spec["command"], repo)
    target_file.write_text(original)
    restored = run(spec["command"], repo)
    return {
        "language_family": REPOS[repo_family]["language_family"],
        "repo_family": repo_family,
        "selected_verifier_path": spec["selected_verifier_path"],
        "mutation_file": str(target_file),
        "mutation_kind": spec["mutation_kind"],
        "baseline": baseline,
        "mutant": mutant,
        "restored": restored,
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    roots: dict[str, Path] = {}
    for repo_family, cfg in REPOS.items():
        dst = ROOT / repo_family
        copy_repo(cfg["src"], dst, cfg["ignore"])
        node_modules = cfg["src"] / "node_modules"
        if node_modules.exists() and not (dst / "node_modules").exists():
            (dst / "node_modules").symlink_to(node_modules, target_is_directory=True)
        roots[repo_family] = dst
    probes: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for spec in SPECS:
        try:
            probes.append(probe(spec, roots))
            OUT.write_text(json.dumps({"stage": "stage12053_semantic_fail_to_pass_probes", "probes": probes, "probe_failures": failures}, indent=2, sort_keys=True) + "\n")
            print(f"probed {spec['repo_family']}::{spec['mutation_kind']}", flush=True)
        except Exception as exc:
            failures.append({"repo_family": spec["repo_family"], "mutation_kind": spec["mutation_kind"], "error": f"{type(exc).__name__}: {exc}"})
            OUT.write_text(json.dumps({"stage": "stage12053_semantic_fail_to_pass_probes", "probes": probes, "probe_failures": failures}, indent=2, sort_keys=True) + "\n")
            print(f"failed {spec['repo_family']}::{spec['mutation_kind']}: {type(exc).__name__}", flush=True)
    admitted = [
        p
        for p in probes
        if p["baseline"]["returncode"] == 0 and p["mutant"]["returncode"] != 0 and p["restored"]["returncode"] == 0
    ]
    OUT.write_text(json.dumps({"stage": "stage12053_semantic_fail_to_pass_probes", "probes": probes, "probe_failures": failures}, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"probes": len(probes), "probe_failures": len(failures), "admissible_fail_to_pass": len(admitted), "out": str(OUT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
