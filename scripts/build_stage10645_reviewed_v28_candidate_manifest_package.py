#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"


def load_json(path: Path):
    return json.loads(path.read_text())


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2) + "\n")


def write_jsonl(path: Path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def main():
    stage10420_dir = ARTIFACTS / "stage10420_reviewed_multilingual_v27_manifest_package"
    stage10644_dir = ARTIFACTS / "stage10644_reviewed_v27_replenishment_candidate_audit"

    package = load_json(stage10420_dir / "reviewed_multilingual_v27_manifest_package.json")
    root_manifest = load_jsonl(stage10420_dir / "reviewed_multilingual_v27_root_manifest.jsonl")
    bounded_rows = load_jsonl(stage10420_dir / "reviewed_multilingual_v27_bounded_rows.jsonl")
    train_rows = load_jsonl(stage10420_dir / "agentkernel_lite_encdec_train.jsonl")
    validation_rows = load_jsonl(stage10420_dir / "agentkernel_lite_encdec_validation.jsonl")
    strict_rows = load_jsonl(stage10420_dir / "agentkernel_lite_encdec_strict_eval.jsonl")
    stress_rows = load_jsonl(stage10420_dir / "agentkernel_lite_encdec_stress_eval.jsonl")

    replenishment = load_json(stage10644_dir / "reviewed_v27_replenishment_candidate_audit.json")
    candidate_rows = load_jsonl(stage10644_dir / "reviewed_v27_replenishment_candidate_rows.jsonl")
    candidate_by_bundle = {row["bundle_id"]: row for row in candidate_rows}
    root_by_bundle = {row.get("bundle_id", row.get("root_id")): row for row in root_manifest}

    web_validation_bundle = (
        "stage10119::localsess_bddy_website_sessseed_codex_sessions_rollout_2025_11_28t14_11_27_019acacd_f95c_7802_9bfe_7232_index_html_f0be60dc44_aug_1500000_8b46e7f662::web_js_ts_html"
    )
    rust_replacement_bundles = {
        "stage10126::candle::candle-core::rust",
        "stage10413::candle::candle-flash-attn::rust",
    }
    web_overlap_bundle = (
        "stage10176::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t13_13_10_019bff96_2dc5_7162_88f8_83eb_src_code_assist_orchestrator_cognitive_perfection_py_src_code_assist_orchestrato_3a0f6d8311_aug_1500000_8b46e7f662::web_js_ts_html"
    )

    def claim_role_for_bundle(bundle_id: str) -> str:
        if bundle_id == web_overlap_bundle:
            return "stress_overlap_only"
        if bundle_id == web_validation_bundle:
            return "pure_web_same_manifest_validation"
        if bundle_id in rust_replacement_bundles:
            return "rust_replacement_experiment"
        root = root_by_bundle.get(bundle_id, {})
        if root.get("split_role") == "strict_heldout":
            return "headline_strict"
        if root.get("split_role") == "validation":
            return "headline_validation"
        if root.get("split_role") == "train_support":
            return "train_support"
        return "unassigned_reviewed"

    def claim_role_for_row(row):
        bundle_id = row.get("source_bundle_id")
        if bundle_id:
            return claim_role_for_bundle(bundle_id)
        split_role = row.get("split_role")
        if split_role == "stress_overlap":
            return "stress_overlap_only"
        if split_role == "train_support":
            return "train_support"
        if split_role == "validation":
            return "headline_validation"
        if split_role == "strict_heldout":
            return "headline_strict"
        return "unassigned_reviewed"

    def headline_eligible(bundle_id: str) -> bool:
        return claim_role_for_bundle(bundle_id) in {"headline_strict", "headline_validation"}

    enriched_root_manifest = []
    for root in root_manifest:
        bundle_id = root.get("bundle_id", root.get("root_id"))
        candidate = candidate_by_bundle.get(bundle_id, {})
        claim_role = claim_role_for_bundle(bundle_id)
        enriched = dict(root)
        enriched["claim_role"] = claim_role
        enriched["headline_eligible"] = headline_eligible(bundle_id)
        enriched["replenishment_candidate"] = bundle_id in candidate_by_bundle
        enriched["replenishment_notes"] = candidate.get("claim_boundary_notes", [])
        enriched["replenishment_source_heldout_headline_admissible"] = candidate.get(
            "source_heldout_headline_admissible"
        )
        enriched["replenishment_reduces_selected_test_gap"] = candidate.get(
            "reduces_selected_test_gap_vs_current_strict", False
        )
        enriched["replenishment_reduces_verifier_anchor_gap"] = candidate.get(
            "reduces_verifier_anchor_gap_vs_current_strict", False
        )
        enriched["replenishment_reduces_abstention_heavy_gap"] = candidate.get(
            "reduces_abstention_heavy_gap_vs_current_strict", False
        )
        enriched_root_manifest.append(enriched)

    def enrich_rows(rows):
        out = []
        for row in rows:
            bundle_id = row.get("source_bundle_id")
            candidate = candidate_by_bundle.get(bundle_id, {})
            enriched = dict(row)
            enriched["claim_role"] = claim_role_for_row(row)
            enriched["headline_eligible"] = enriched["claim_role"] in {"headline_strict", "headline_validation"}
            enriched["claim_boundary_notes"] = candidate.get("claim_boundary_notes", [])
            enriched["source_heldout_headline_admissible"] = candidate.get(
                "source_heldout_headline_admissible",
                row.get("source_heldout_admissible"),
            )
            enriched["replenishment_candidate"] = bundle_id in candidate_by_bundle
            out.append(enriched)
        return out

    headline_strict_rows = enrich_rows(strict_rows)
    headline_validation_rows = enrich_rows(validation_rows)
    train_support_rows = enrich_rows(train_rows)
    stress_overlap_rows = enrich_rows(stress_rows)
    rust_replacement_rows = enrich_rows(
        [row for row in bounded_rows if row.get("source_bundle_id") in rust_replacement_bundles]
    )
    pure_web_validation_rows = enrich_rows(
        [row for row in bounded_rows if row.get("source_bundle_id") == web_validation_bundle]
    )
    reviewed_support_rows = enrich_rows(bounded_rows)

    metrics = {
        "headline_strict_rows": len(headline_strict_rows),
        "headline_validation_rows": len(headline_validation_rows),
        "train_support_rows": len(train_support_rows),
        "stress_overlap_rows": len(stress_overlap_rows),
        "rust_replacement_rows": len(rust_replacement_rows),
        "pure_web_validation_rows": len(pure_web_validation_rows),
        "reviewed_support_rows": len(reviewed_support_rows),
        "headline_strict_languages": sorted({row["language_family"] for row in headline_strict_rows}),
        "rust_replacement_bundles": sorted(rust_replacement_bundles),
        "pure_web_validation_bundle": web_validation_bundle,
        "web_overlap_bundle": web_overlap_bundle,
    }

    summary = {
        "stage": 10645,
        "stage_name": "stage10645_reviewed_v28_candidate_manifest_package",
        "passed": True,
        "created_from": {
            "stage10420_package": str(stage10420_dir / "reviewed_multilingual_v27_manifest_package.json"),
            "stage10644_replenishment_audit": str(
                stage10644_dir / "reviewed_v27_replenishment_candidate_audit.json"
            ),
        },
        "metrics": metrics,
        "claim_boundary": [
            "headline_strict preserves the honest v2.7 same-manifest multilingual comparison boundary.",
            "pure_web_validation extends reviewed pure-web coverage but does not fix the missing verifier-anchor gap.",
            "rust_replacement_experiment provides alternative reviewed Rust roots to probe abstention-heaviness and verifier anchoring without upgrading the headline claim automatically.",
            "stress_overlap_rows remain non-headline because code_assist is mixed-language and overlap-risk.",
        ],
        "recommended_next_step": [
            "Run 100M and Gemma on headline_strict plus rust_replacement_rows as a replacement experiment, not a claim upgrade.",
            "Use stress_overlap_rows only for web stress evaluation or support, not for source-heldout or pure-web headline claims.",
            "Mine fresh pure-web verifier-anchored roots and fresh non-abstention-heavy Rust roots before promoting a stronger v2.8 multilingual headline.",
        ],
        "v27_headline_preserved": {
            "strict_rows": len(strict_rows),
            "strict_source": str(stage10420_dir / "agentkernel_lite_encdec_strict_eval.jsonl"),
            "v27_package_source": str(stage10420_dir / "reviewed_multilingual_v27_manifest_package.json"),
        },
    }

    out_dir = ARTIFACTS / "stage10645_reviewed_v28_candidate_manifest_package"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "reviewed_v28_candidate_manifest_package.json", summary)
    write_jsonl(out_dir / "reviewed_v28_candidate_root_manifest.jsonl", enriched_root_manifest)
    write_jsonl(out_dir / "headline_strict_eval.jsonl", headline_strict_rows)
    write_jsonl(out_dir / "headline_validation.jsonl", headline_validation_rows)
    write_jsonl(out_dir / "train_support.jsonl", train_support_rows)
    write_jsonl(out_dir / "stress_overlap_eval.jsonl", stress_overlap_rows)
    write_jsonl(out_dir / "rust_replacement_experiment_eval.jsonl", rust_replacement_rows)
    write_jsonl(out_dir / "pure_web_same_manifest_validation.jsonl", pure_web_validation_rows)
    write_jsonl(out_dir / "reviewed_support_inventory.jsonl", reviewed_support_rows)
    print(out_dir / "reviewed_v28_candidate_manifest_package.json")


if __name__ == "__main__":
    main()
