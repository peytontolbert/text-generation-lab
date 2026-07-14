#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10678
NAME = "stage10678_rust_source_span_partial_materializer"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "rust_source_span_partial_materializer.json"
PACKETS_DIR = OUT_DIR / "review_packets"

LOCAL_AUDIT = ARTIFACTS / "stage10676_rust_local_supply_recoverability_audit/rust_local_supply_recoverability_audit.json"
SCAFFOLD_DIR = ARTIFACTS / "stage10674_rust_fresh_review_packet_scaffolds" / "review_packets"
SPANS_PATH = Path("/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def scaffold_slug(bundle_id: str) -> str:
    return bundle_id.replace("::", "__")


def sample_span_to_uri(span_id: str) -> str:
    repo, path = span_id.split(":", 1)
    return f"program://{repo}/artifact/{path}"


def resolve_spans(uris: set[str]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    with SPANS_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if all(uri in found for uri in uris):
                break
            for uri in uris:
                if uri in found:
                    continue
                if uri in line:
                    obj = json.loads(line)
                    if (obj.get("meta") or {}).get("uri") == uri:
                        found[uri] = obj
    return found


def replace_text_entry(entry: dict[str, Any], span_obj: dict[str, Any]) -> dict[str, Any]:
    new_entry = dict(entry)
    new_entry["source_type"] = "external_repo_graph_span"
    new_entry["text"] = span_obj.get("text", "")
    meta = dict(new_entry.get("meta") or {})
    meta.update(span_obj.get("meta") or {})
    meta["materialized_from_spans_corpus"] = True
    new_entry["meta"] = meta
    return new_entry


def main() -> None:
    audit = load_json(LOCAL_AUDIT)
    targets = audit.get("targets") or []

    target_to_uris = {
        row["bundle_id"]: [sample_span_to_uri(span_id) for span_id in row.get("sample_span_ids_available") or []]
        for row in targets
    }
    all_uris = {uri for uris in target_to_uris.values() for uri in uris}
    resolved = resolve_spans(all_uris)

    written = []
    for row in targets:
        bundle_id = row["bundle_id"]
        slug = scaffold_slug(bundle_id)
        scaffold_packet = load_json(SCAFFOLD_DIR / slug / "fresh_rust_bundle_preview.json")
        anti_cheat = load_json(SCAFFOLD_DIR / slug / "anti_cheat_review_card.json")
        gold = load_json(SCAFFOLD_DIR / slug / "perspective_gold_adjudication.json")

        uris = target_to_uris[bundle_id]
        span_objs = [resolved[uri] for uri in uris if uri in resolved]

        candidate_entries = scaffold_packet["maintainer_visible_evidence"]["candidate_change_surface"]
        span_by_path = {}
        for span_obj in span_objs:
            uri = (span_obj.get("meta") or {}).get("uri", "")
            path_part = uri.split('/artifact/', 1)[1] if '/artifact/' in uri else None
            if path_part:
                span_by_path[path_part] = span_obj
        for idx, entry in enumerate(candidate_entries):
            span_obj = span_by_path.get(entry.get("path"))
            if span_obj is not None:
                candidate_entries[idx] = replace_text_entry(entry, span_obj)

        if span_objs:
            scaffold_packet["maintainer_visible_evidence"]["symptom_or_call_path_analogue"][0] = replace_text_entry(
                scaffold_packet["maintainer_visible_evidence"]["symptom_or_call_path_analogue"][0],
                span_objs[0],
            )
        if len(span_objs) > 1:
            scaffold_packet["maintainer_visible_evidence"]["nearby_definition_or_usage_context"][0] = replace_text_entry(
                scaffold_packet["maintainer_visible_evidence"]["nearby_definition_or_usage_context"][0],
                span_objs[1],
            )
        scaffold_packet["claim_boundary"]["preview_only"] = True
        scaffold_packet["claim_boundary"]["supports_training_or_scoring_now"] = False
        scaffold_packet["claim_boundary"]["partial_source_materialization_complete"] = True
        scaffold_packet["claim_boundary"]["verifier_anchor_still_missing"] = True
        scaffold_packet["discovery_metadata"]["resolved_sample_span_uri_count"] = len(span_objs)

        anti_cheat["status"] = "pending_verifier_anchor_and_post_materialization_review"
        anti_cheat["decision_rationale"] = (
            "Partial source materialization completed from the spans corpus, but verifier/test anchors remain missing and the packet is not yet admissible."
        )
        anti_cheat["passed"] = False
        anti_cheat["admissible_for_same_surface_comparison"] = False

        gold["status"] = "pending_verifier_anchor_then_gold_completion"
        gold["decision_rationale"] = (
            "Real source spans are now attached for the primary file evidence, but verifier/test anchors are still missing so final gold adjudication remains incomplete."
        )

        out_packet_dir = PACKETS_DIR / slug
        preview_path = out_packet_dir / "fresh_rust_bundle_preview.json"
        anti_cheat_path = out_packet_dir / "anti_cheat_review_card.json"
        gold_path = out_packet_dir / "perspective_gold_adjudication.json"
        write_json(preview_path, scaffold_packet)
        write_json(anti_cheat_path, anti_cheat)
        write_json(gold_path, gold)

        written.append(
            {
                "bundle_id": bundle_id,
                "resolved_sample_span_uri_count": len(span_objs),
                "requested_sample_span_uri_count": len(uris),
                "preview_bundle": rel(preview_path),
                "anti_cheat_review_card": rel(anti_cheat_path),
                "perspective_gold_adjudication": rel(gold_path),
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "rust_source_spans_partially_materialized_from_corpus",
        "claim_scope": [
            "Resolve the pending Rust scaffold targets against the known spans corpus and replace placeholder file evidence with real text where possible.",
            "Advance the packets from scaffold-only to partial source-backed status without overstating them as scoreable while verifier anchors remain missing.",
        ],
        "spans_corpus": str(SPANS_PATH),
        "written_packets": written,
        "claim_boundary": [
            "This stage only materializes source-text evidence for sample span ids.",
            "Verifier/test anchors are still missing, so none of the packets are yet promotable or scoreable.",
            "The next gating step remains recovery of selected test or verifier constraints for at least one target.",
        ],
        "next_best_steps": [
            "Recover a selected test or verifier anchor for one partially materialized Rust target.",
            "Re-run anti-cheat review after the verifier anchor is attached.",
            "Only then complete gold adjudication and admit the target into the next multilingual support/eval package.",
        ],
    }

    write_json(SUMMARY_JSON, payload)
    print(SUMMARY_JSON)


if __name__ == "__main__":
    main()
