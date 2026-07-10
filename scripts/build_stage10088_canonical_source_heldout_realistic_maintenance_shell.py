#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10088
NAME = "stage10088_canonical_source_heldout_realistic_maintenance_shell"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "canonical_source_heldout_realistic_maintenance_shell.json"
MANIFEST = OUT_DIR / "canonical_source_heldout_realistic_maintenance_shell_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_SOURCE_HELDOUT_REALISTIC_MAINTENANCE_SHELL_STAGE10088.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
BASE = ROOT / "runs/local/artifacts/stage10083_canonical_label_aligned_source_heldout_successor_packet/canonical_label_aligned_source_heldout_manifest.jsonl"
REALISM = ROOT / "runs/local/artifacts/stage10087_canonical_source_heldout_realism_audit/canonical_source_heldout_realistic_successor_spec.json"

CANONICAL_LABEL_TO_TARGET = {
    "A": "TARGET_TEST",
    "B": "TARGET_ENTRYPOINT",
    "C": "TARGET_SYMBOL",
    "D": "TARGET_FILE",
    "E": "TARGET_CONFIG",
}
TARGET_TO_SEMANTIC = {
    "TARGET_TEST": "test_surface",
    "TARGET_ENTRYPOINT": "entrypoint_or_invocation_surface",
    "TARGET_SYMBOL": "symbol_definition_or_implementation_surface",
    "TARGET_FILE": "implementation_file_surface",
    "TARGET_CONFIG": "configuration_or_settings_surface",
}
LANGUAGE_PROFILES = {
    "python": {
        "failure_text": "test_login_rejects_empty_email failed: expected HTTP 400, got HTTP 200 after empty-email login request.",
        "trace_excerpt": ["tests/test_login.py::test_login_rejects_empty_email", "auth/routes.py::login", "auth/validators.py::normalize_email"],
        "snippets": {
            "TARGET_TEST": [
                "def test_login_rejects_empty_email(client): response = client.post('/login', json={'email': ''})",
                "assert response.status_code == 400",
            ],
            "TARGET_ENTRYPOINT": [
                "@router.post('/login')",
                "def login(req): email = normalize_email(req.email); return create_session(email)",
            ],
            "TARGET_SYMBOL": [
                "def normalize_email(email): return email.strip().lower()",
                "def login(req): email = normalize_email(req.email)",
            ],
            "TARGET_FILE": [
                "# auth/routes.py owns request validation and session creation",
                "# auth/validators.py contains only normalization helpers",
            ],
            "TARGET_CONFIG": [
                "EMPTY_EMAIL_RETURNS_400 = true",
                "LOGIN_ALLOW_BLANK_EMAIL = false",
            ],
        },
        "candidate_paths": {
            "TARGET_TEST": "tests/test_login.py",
            "TARGET_ENTRYPOINT": "auth/routes.py::login",
            "TARGET_SYMBOL": "auth/validators.py::normalize_email",
            "TARGET_FILE": "auth/routes.py",
            "TARGET_CONFIG": "config/auth.yaml",
        },
    },
    "rust": {
        "failure_text": "login_rejects_empty_email failed: expected StatusCode::BAD_REQUEST but handler returned StatusCode::OK.",
        "trace_excerpt": ["tests/login_flow.rs::login_rejects_empty_email", "src/http/login.rs::login", "src/http/validators.rs::normalize_email"],
        "snippets": {
            "TARGET_TEST": [
                "let response = app.post('/login').json(&json!({ 'email': '' })).send().await?;",
                "assert_eq!(response.status(), StatusCode::BAD_REQUEST);",
            ],
            "TARGET_ENTRYPOINT": [
                "pub async fn login(req: LoginRequest) -> Result<Response>",
                "let email = normalize_email(&req.email); create_session(email).await",
            ],
            "TARGET_SYMBOL": [
                "fn normalize_email(email: &str) -> String { email.trim().to_lowercase() }",
                "let email = normalize_email(&req.email);",
            ],
            "TARGET_FILE": [
                "// src/http/login.rs wires request validation and response codes",
                "// src/http/validators.rs contains helper normalization only",
            ],
            "TARGET_CONFIG": [
                "reject_blank_email = true",
                "session_creation_requires_valid_email = true",
            ],
        },
        "candidate_paths": {
            "TARGET_TEST": "tests/login_flow.rs",
            "TARGET_ENTRYPOINT": "src/http/login.rs::login",
            "TARGET_SYMBOL": "src/http/validators.rs::normalize_email",
            "TARGET_FILE": "src/http/login.rs",
            "TARGET_CONFIG": "config/auth.toml",
        },
    },
    "c_cpp": {
        "failure_text": "LoginRejectsEmptyEmail failed: expected status_code == 400, observed status_code == 200 after empty-email request.",
        "trace_excerpt": ["tests/login_test.cpp::LoginRejectsEmptyEmail", "src/http/login.cc::HandleLogin", "src/http/email_utils.cc::NormalizeEmail"],
        "snippets": {
            "TARGET_TEST": [
                "auto response = client.Post('/login', R'({\"email\":\"\"})');",
                "EXPECT_EQ(response.status_code, 400);",
            ],
            "TARGET_ENTRYPOINT": [
                "Response HandleLogin(const LoginRequest& req)",
                "auto email = NormalizeEmail(req.email); return CreateSession(email);",
            ],
            "TARGET_SYMBOL": [
                "std::string NormalizeEmail(std::string_view email) { return Trim(email); }",
                "auto email = NormalizeEmail(req.email);",
            ],
            "TARGET_FILE": [
                "// login.cc owns request validation and response policy",
                "// email_utils.cc is shared helper code",
            ],
            "TARGET_CONFIG": [
                "allow_blank_email=false",
                "reject_invalid_login_inputs=true",
            ],
        },
        "candidate_paths": {
            "TARGET_TEST": "tests/login_test.cpp",
            "TARGET_ENTRYPOINT": "src/http/login.cc::HandleLogin",
            "TARGET_SYMBOL": "src/http/email_utils.cc::NormalizeEmail",
            "TARGET_FILE": "src/http/login.cc",
            "TARGET_CONFIG": "config/auth.ini",
        },
    },
    "web_js_ts_html": {
        "failure_text": "login rejects empty email regression: expected response.status 400, got 200 after POST /login with empty email.",
        "trace_excerpt": ["tests/login.spec.ts::rejects empty email", "src/routes/login.ts::login", "src/lib/normalizeEmail.ts::normalizeEmail"],
        "snippets": {
            "TARGET_TEST": [
                "const response = await request(app).post('/login').send({ email: '' });",
                "expect(response.status).toBe(400);",
            ],
            "TARGET_ENTRYPOINT": [
                "export async function login(req, res)",
                "const email = normalizeEmail(req.body.email); return createSession(res, email);",
            ],
            "TARGET_SYMBOL": [
                "export function normalizeEmail(email: string) { return email.trim().toLowerCase(); }",
                "const email = normalizeEmail(req.body.email);",
            ],
            "TARGET_FILE": [
                "// src/routes/login.ts owns request validation and response status",
                "// src/lib/normalizeEmail.ts is reusable helper logic",
            ],
            "TARGET_CONFIG": [
                "export const rejectBlankEmail = true;",
                "export const allowLoginWithoutEmail = false;",
            ],
        },
        "candidate_paths": {
            "TARGET_TEST": "tests/login.spec.ts",
            "TARGET_ENTRYPOINT": "src/routes/login.ts::login",
            "TARGET_SYMBOL": "src/lib/normalizeEmail.ts::normalizeEmail",
            "TARGET_FILE": "src/routes/login.ts",
            "TARGET_CONFIG": "src/config/auth.ts",
        },
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
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


def _target_hidden(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return str(clean.get("edit_localization_target_hidden") or CANONICAL_LABEL_TO_TARGET.get(str(clean.get("edit_localization_target") or ""), ""))


def _profile(language_family: str) -> dict[str, Any]:
    return LANGUAGE_PROFILES[language_family]


def _candidate_descriptions(language_family: str, row: dict[str, Any]) -> list[str]:
    profile = _profile(language_family)
    order = row.get("choice_permutation_order") if isinstance(row.get("choice_permutation_order"), list) else []
    mapping = row.get("choice_permutation_map") if isinstance(row.get("choice_permutation_map"), dict) else {}
    descriptions: list[str] = []
    if order and mapping:
        for opaque in [str(x) for x in order]:
            canonical = str(mapping.get(opaque) or "")
            target = CANONICAL_LABEL_TO_TARGET.get(canonical)
            if not target:
                continue
            path = profile["candidate_paths"][target]
            semantic = TARGET_TO_SEMANTIC[target]
            descriptions.append(f"option {opaque}: {path} [{semantic}]")
    else:
        for canonical, target in CANONICAL_LABEL_TO_TARGET.items():
            path = profile["candidate_paths"][target]
            semantic = TARGET_TO_SEMANTIC[target]
            descriptions.append(f"option {canonical}: {path} [{semantic}]")
    return descriptions


def _augment_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(row)
    language_family = str(updated.get("language_family") or "")
    profile = _profile(language_family)
    target_hidden = _target_hidden(updated)
    state = updated.get("input_state") if isinstance(updated.get("input_state"), dict) else {}
    state["failure_text"] = profile["failure_text"]
    state["trace_excerpt"] = list(profile["trace_excerpt"])
    state["relevant_snippets"] = list(profile["snippets"][target_hidden])
    state["candidate_paths"] = list(profile["candidate_paths"].values())
    state["candidate_descriptions"] = _candidate_descriptions(language_family, updated)
    state["test_assertion"] = "Expected invalid empty-email login to fail with 400 instead of creating a session."
    state["expected_vs_actual"] = {"expected": "400 / validation error", "actual": "200 / session created"}
    state["realism_level"] = "L2"
    state["shell_only_not_raw_repo_source"] = True
    updated["input_state"] = state

    anti = updated.get("anti_cheat") if isinstance(updated.get("anti_cheat"), dict) else {}
    anti["stage10088_realistic_maintenance_shell"] = True
    anti["stage10088_shell_uses_synthetic_visible_evidence"] = True
    anti["target_label_literals_in_prompt_surface"] = False
    anti["raw_source_included"] = False
    anti["candidate_descriptions_use_raw_target_literals"] = False
    updated["anti_cheat"] = anti

    updated["surface"] = "canonical_source_heldout_realistic_maintenance_shell_v1"
    updated["stage10088_realism_level"] = "L2"
    return updated


def build_packet() -> dict[str, Any]:
    base_rows = load_jsonl(BASE)
    realism = load_json(REALISM)
    failures: list[str] = []
    if realism.get("preserve_from_stage10083", {}).get("heldout_split_integrity") is not True:
        failures.append("stage10087_spec_missing_heldout_integrity")
    augmented = [_augment_row(row) for row in base_rows]
    write_jsonl(MANIFEST, augmented)

    heldout = [row for row in augmented if str(row.get("split") or "") in {"eval", "strict_eval"}]
    metrics = {
        "rows": len(augmented),
        "heldout_rows": len(heldout),
        "language_counts": dict(sorted(Counter(str(row.get("language_family") or "") for row in augmented).items())),
        "heldout_language_counts": dict(sorted(Counter(str(row.get("language_family") or "") for row in heldout).items())),
        "rows_with_failure_text": sum(1 for row in augmented if (row.get("input_state") or {}).get("failure_text")),
        "rows_with_trace_excerpt": sum(1 for row in augmented if (row.get("input_state") or {}).get("trace_excerpt")),
        "rows_with_relevant_snippets": sum(1 for row in augmented if (row.get("input_state") or {}).get("relevant_snippets")),
        "rows_with_candidate_paths": sum(1 for row in augmented if (row.get("input_state") or {}).get("candidate_paths")),
        "rows_with_candidate_descriptions": sum(1 for row in augmented if (row.get("input_state") or {}).get("candidate_descriptions")),
        "rows_with_expected_vs_actual": sum(1 for row in augmented if (row.get("input_state") or {}).get("expected_vs_actual")),
        "rows_marked_l2": sum(1 for row in augmented if str((row.get("input_state") or {}).get("realism_level") or "") == "L2"),
    }
    if metrics["rows"] != 95:
        failures.append("rows_not_95")
    if metrics["heldout_rows"] != 55:
        failures.append("heldout_rows_not_55")
    for key in [
        "rows_with_failure_text",
        "rows_with_trace_excerpt",
        "rows_with_relevant_snippets",
        "rows_with_candidate_paths",
        "rows_with_candidate_descriptions",
        "rows_with_expected_vs_actual",
        "rows_marked_l2",
    ]:
        if metrics[key] != 95:
            failures.append(f"{key}_not_95")

    packet = {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "policy": {
            "preserve_stage10083_row_identity_and_splits": True,
            "preserve_canonical_label_map": True,
            "upgrade_visible_surface_to_realistic_shell_only": True,
            "not_yet_promotion_ready_as_expert_maintainer_eval": True,
            "raw_repo_source_still_not_visible": True,
        },
        "artifacts": {
            "base_manifest": display(BASE),
            "realism_spec": display(REALISM),
            "manifest": display(MANIFEST),
        },
        "claim_boundary": {
            "supports_shell_level_l2_prompt_design": True,
            "supports_final_expert_maintainer_claim": False,
            "reason": "Visible fields are now more realistic, but they remain synthetic shells rather than independently sourced repository failures and snippets.",
        },
    }
    write_json(PACKET, packet)
    return packet


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    next_step = "Use this shell to build a real source-backed successor where failure text, trace excerpts, snippets, and candidate paths are mined from independent heldout roots rather than synthesized templates."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"packet": display(PACKET), "manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": "Materialized a canonical source-heldout realistic-maintenance shell that preserves the stage10083 row and label structure while upgrading prompt-visible evidence to L2-style failure, trace, snippet, and candidate-path fields without exposing raw repo source.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10088 Canonical Source Heldout Realistic Maintenance Shell",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{built['metrics']['rows']}`",
        f"Heldout rows: `{built['metrics']['heldout_rows']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
