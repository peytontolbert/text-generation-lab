#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"


def load_json(path: Path):
    return json.loads(path.read_text())


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    claim = load_json(
        ARTIFACTS
        / "stage10643_reviewed_v27_claim_readiness_audit"
        / "reviewed_v27_claim_readiness_audit.json"
    )
    atlas = load_json(
        ARTIFACTS
        / "stage10417_multilingual_reviewed_scaling_atlas"
        / "multilingual_reviewed_scaling_atlas.json"
    )
    web_gap = load_json(
        ARTIFACTS
        / "stage10418_pure_web_verifier_anchor_gap_audit"
        / "pure_web_verifier_anchor_gap_audit.json"
    )
    strict_rows = load_jsonl(
        ARTIFACTS
        / "stage10420_reviewed_multilingual_v27_manifest_package"
        / "agentkernel_lite_encdec_strict_eval.jsonl"
    )

    current_root_by_language = {}
    for row in strict_rows:
        lang = row["language_family"]
        current_root_by_language.setdefault(
            lang,
            row.get("source_bundle_id")
            or row.get("source_root_id")
            or row["row_id"].rsplit("::", 2)[0],
        )

    stronger_claim_caveats_by_language = claim["metrics"][
        "stronger_claim_caveats_by_language"
    ]
    admitted = {row["bundle_id"]: row for row in atlas["admitted_bundle_rows"]}

    def assess(bundle_id: str):
        row = admitted[bundle_id]
        lang = row["language_family"]
        visible_keys = set(row.get("visible_evidence_keys", []))
        selected_tests_count = row.get("selected_tests_count", len(row.get("selected_tests", [])))
        selected_test_anchor_present = selected_tests_count > 0
        verifier_anchor_present = (
            selected_test_anchor_present and "verifier_and_test_constraint" in visible_keys
        )
        abstention_count = row.get("abstention_count", 0)
        current_caveats = stronger_claim_caveats_by_language.get(lang, {})

        claim_boundary_notes = []
        candidate_role = "strict_replacement_candidate"
        source_heldout_headline_admissible = True

        if lang == "web_js_ts_html":
            if row["repo_id"] == "code_assist":
                candidate_role = "stress_or_support_only"
                source_heldout_headline_admissible = False
                claim_boundary_notes.extend(
                    ["mixed_language_web_root", "same_repo_overlap_risk_for_known_successors"]
                )
            elif not selected_test_anchor_present or not verifier_anchor_present:
                candidate_role = "same_manifest_only"
                if not selected_test_anchor_present:
                    claim_boundary_notes.append("no_selected_tests")
                if not verifier_anchor_present:
                    claim_boundary_notes.append("no_verifier_anchor")

        if lang == "rust":
            if abstention_count >= 4:
                claim_boundary_notes.append("abstention_heavy")
            if not selected_test_anchor_present:
                claim_boundary_notes.append("no_selected_tests")
            if "verifier_and_test_constraint" not in visible_keys:
                claim_boundary_notes.append("no_verifier_constraint_evidence")
            if bundle_id != current_root_by_language.get(lang):
                candidate_role = "support_or_replacement_experiment"

        return {
            "bundle_id": bundle_id,
            "language_family": lang,
            "repo_id": row["repo_id"],
            "current_strict_root_for_language": current_root_by_language.get(lang),
            "same_as_current_strict_root": bundle_id == current_root_by_language.get(lang),
            "selected_tests_count": selected_tests_count,
            "selected_test_anchor_present": selected_test_anchor_present,
            "verifier_anchor_present": verifier_anchor_present,
            "abstention_count": abstention_count,
            "non_abstention_count": row.get(
                "non_abstention_count", row.get("gold_answer_count", 0) - abstention_count
            ),
            "candidate_paths_count": row.get("candidate_paths_count"),
            "visible_evidence_keys": row.get("visible_evidence_keys", []),
            "reduces_selected_test_gap_vs_current_strict": bool(
                current_caveats.get("selected_test_anchor_absent", 0)
                and selected_test_anchor_present
            ),
            "reduces_verifier_anchor_gap_vs_current_strict": bool(
                current_caveats.get("verifier_anchor_absent", 0) and verifier_anchor_present
            ),
            "reduces_abstention_heavy_gap_vs_current_strict": bool(
                current_caveats.get("abstention_heavy", 0) and abstention_count < 4
            ),
            "source_heldout_headline_admissible": source_heldout_headline_admissible,
            "candidate_role": candidate_role,
            "decision_rationale": row.get("decision_rationale"),
            "claim_boundary_notes": claim_boundary_notes,
        }

    candidate_ids = [
        "stage10119::localsess_bddy_website_sessseed_codex_sessions_rollout_2025_11_28t14_11_27_019acacd_f95c_7802_9bfe_7232_index_html_f0be60dc44_aug_1500000_8b46e7f662::web_js_ts_html",
        "stage10176::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t13_13_10_019bff96_2dc5_7162_88f8_83eb_src_code_assist_orchestrator_cognitive_perfection_py_src_code_assist_orchestrato_3a0f6d8311_aug_1500000_8b46e7f662::web_js_ts_html",
        "stage10126::candle::candle-core::rust",
        "stage10413::candle::candle-flash-attn::rust",
    ]
    assessments = [assess(bundle_id) for bundle_id in candidate_ids]

    summary = {
        "stage": 10644,
        "stage_name": "stage10644_reviewed_v27_replenishment_candidate_audit",
        "passed": True,
        "current_strict_root_by_language": current_root_by_language,
        "current_claim_caveats_by_language": stronger_claim_caveats_by_language,
        "web_gap_verdict": web_gap["verdict"],
        "candidate_assessments": assessments,
        "recommended_next_moves": [
            "Use stage10176 code_assist only as web stress/support or same-manifest caveat reduction, not as a source-heldout pure-web headline root.",
            "Use candle-core to reduce Rust abstention-heaviness in support or replacement experiments, but note it lacks selected-test/verifier anchoring.",
            "Use candle-flash-attn as the selected-test/verifier-anchored Rust support root, but not as the sole Rust headline root because it remains abstention-heavy.",
            "For a stronger v2.8 claim boundary, replenish with fresh pure-web verifier-anchored roots and fresh non-abstention-heavy Rust roots rather than only reshuffling current reviewed supply.",
        ],
        "decision": "reviewed_supply_can_reduce_some_same_manifest_caveats_but_cannot_fully_close_web_and_rust_headline_gaps",
    }

    out_dir = ARTIFACTS / "stage10644_reviewed_v27_replenishment_candidate_audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reviewed_v27_replenishment_candidate_audit.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    (out_dir / "reviewed_v27_replenishment_candidate_rows.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in assessments)
    )
    print(out_dir / "reviewed_v27_replenishment_candidate_audit.json")


if __name__ == "__main__":
    main()
