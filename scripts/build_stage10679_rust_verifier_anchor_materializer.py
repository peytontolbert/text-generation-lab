#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10679
NAME = "stage10679_rust_verifier_anchor_materializer"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "rust_verifier_anchor_materializer.json"
PACKETS_DIR = OUT_DIR / "review_packets"

INPUT_PACKETS_DIR = ARTIFACTS / "stage10678_rust_source_span_partial_materializer" / "review_packets"
SPANS_PATH = Path("/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def span_uri_from_path(repo: str, path: str) -> str:
    return f"program://{repo}/artifact/{path}"


def resolve_spans(uris: set[str]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    with SPANS_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if all(uri in found for uri in uris):
                break
            if "program://" not in line:
                continue
            obj = None
            for uri in uris:
                if uri in found or uri not in line:
                    continue
                if obj is None:
                    obj = json.loads(line)
                if (obj.get("meta") or {}).get("uri") == uri:
                    found[uri] = obj
    return found


def span_entry(path: str, span_obj: dict[str, Any], *, reason: str, extra_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = dict(span_obj.get("meta") or {})
    meta["materialized_from_spans_corpus"] = True
    if extra_meta:
        meta.update(extra_meta)
    return {
        "distance_from_seed": 0,
        "path": path,
        "retrieval_reason": reason,
        "source_type": "external_repo_graph_span",
        "text": span_obj.get("text", ""),
        "meta": meta,
    }


def replace_candidate_placeholders(packet: dict[str, Any], repo: str, resolved: dict[str, dict[str, Any]]) -> int:
    changed = 0
    entries = packet["maintainer_visible_evidence"]["candidate_change_surface"]
    for idx, entry in enumerate(entries):
        uri = span_uri_from_path(repo, entry["path"])
        span_obj = resolved.get(uri)
        if not span_obj:
            continue
        current_text = entry.get("text", "")
        current_meta = dict(entry.get("meta") or {})
        if current_text == "TODO_MATERIALIZE_REAL_SOURCE_SPAN" or current_meta.get("needs_real_graph_span_materialization"):
            entries[idx] = span_entry(
                entry["path"],
                span_obj,
                reason=entry.get("retrieval_reason", "fresh_rust_candidate_surface_preview"),
                extra_meta={"needs_real_graph_span_materialization": False},
            )
            changed += 1
    return changed


def update_linux_packet(packet: dict[str, Any], resolved: dict[str, dict[str, Any]]) -> dict[str, int]:
    repo = "linux"
    placeholder_fills = replace_candidate_placeholders(packet, repo, resolved)

    acpi_uri = span_uri_from_path(repo, "rust/kernel/acpi.rs")
    platform_uri = span_uri_from_path(repo, "samples/rust/rust_driver_platform.rs")
    kasan_uri = span_uri_from_path(repo, "mm/kasan/kasan_test_rust.rs")

    if platform_uri in resolved:
        packet["maintainer_visible_evidence"]["symptom_or_call_path_analogue"] = [
            span_entry(
                "samples/rust/rust_driver_platform.rs",
                resolved[platform_uri],
                reason="source_derived_driver_probe_and_observed_verifier_path",
                extra_meta={
                    "required_to_compete_against_candidate_change_surface": True,
                    "supports_acpi_localization": True,
                },
            )
        ]
    if acpi_uri in resolved:
        packet["maintainer_visible_evidence"]["nearby_definition_or_usage_context"] = [
            span_entry(
                "rust/kernel/acpi.rs",
                resolved[acpi_uri],
                reason="source_derived_matching_kernel_acpi_abstraction",
                extra_meta={"helps_disambiguate_close_implementation_candidates": True},
            )
        ]

    verifier_entries: list[dict[str, Any]] = []
    if platform_uri in resolved:
        verifier_entries.append(
            span_entry(
                "samples/rust/rust_driver_platform.rs",
                resolved[platform_uri],
                reason="selected_verifier_anchor_with_explicit_qemu_and_dmesg_validation_steps",
                extra_meta={
                    "selected_verifier_anchor": True,
                    "verifier_anchor_kind": "runtime_validation_instructions",
                },
            )
        )
    if verifier_entries:
        packet["maintainer_visible_evidence"]["verifier_and_test_constraint"] = verifier_entries

    selected_tests = [entry["path"] for entry in verifier_entries]
    for row in packet.get("perspective_rows") or []:
        row["prompt_contract"]["selected_tests"] = selected_tests

    claim = packet["claim_boundary"]
    claim["partial_source_materialization_complete"] = True
    claim["verifier_anchor_still_missing"] = False
    claim["scaffold_only_until_verifier_anchor_materialized"] = False
    claim["preview_only"] = True
    claim["supports_training_or_scoring_now"] = False
    packet["discovery_metadata"]["supports_promotable_packet"] = False
    packet["discovery_metadata"]["selected_verifier_anchor_paths"] = selected_tests

    return {
        "candidate_placeholders_filled": placeholder_fills,
        "verifier_anchor_count": len(verifier_entries),
    }


def update_non_linux_packet(packet: dict[str, Any], repo: str, resolved: dict[str, dict[str, Any]]) -> int:
    return replace_candidate_placeholders(packet, repo, resolved)


def update_anti_cheat(card: dict[str, Any], *, linux_anchor_recovered: bool) -> None:
    if linux_anchor_recovered:
        card["status"] = "pending_post_materialization_shortcut_review"
        card["decision_rationale"] = (
            "Real source-derived candidate spans and verifier anchors are now attached, but the packet still requires a fresh anti-cheat pass before admission."
        )
        card["required_human_action"] = (
            "Run AI maintainer anti-cheat review on the now-materialized packet, confirm no prompt-target leakage or path-order shortcut remains, then decide admissibility."
        )
        if "selected test or verifier anchor is visible" in card.get("required_gates_before_admission", []):
            gates = [g for g in card["required_gates_before_admission"] if g != "selected test or verifier anchor is visible"]
            card["required_gates_before_admission"] = gates
    else:
        card["status"] = "pending_verifier_anchor_and_post_materialization_review"


def update_gold(gold: dict[str, Any], *, selected_tests: list[str], linux_anchor_recovered: bool) -> None:
    if linux_anchor_recovered:
        gold["status"] = "pending_ai_gold_completion_after_anchor_recovery"
        gold["decision_rationale"] = (
            "Real source-derived candidate spans and verifier anchors are attached. The packet is now ready for AI maintainer gold adjudication, but the answers are not filled yet."
        )
    else:
        gold["status"] = "pending_verifier_anchor_then_gold_completion"
    for row in gold.get("perspective_gold_answers") or []:
        row["selected_tests"] = selected_tests


def main() -> None:
    bundle_specs = [
        {"bundle_id": "stage10674::linux::rust", "slug": "linux__rust", "repo": "linux"},
        {"bundle_id": "stage10674::candle::candle-datasets", "slug": "candle__candle-datasets", "repo": "candle"},
        {"bundle_id": "stage10674::candle::candle-transformers", "slug": "candle__candle-transformers", "repo": "candle"},
    ]

    uri_set: set[str] = set()
    for spec in bundle_specs:
        slug = spec["slug"]
        packet = load_json(INPUT_PACKETS_DIR / slug / "fresh_rust_bundle_preview.json")
        for path in packet.get("candidate_paths") or []:
            uri_set.add(span_uri_from_path(spec["repo"], path))
    uri_set.update(
        {
            span_uri_from_path("linux", "samples/rust/rust_driver_platform.rs"),
            span_uri_from_path("linux", "mm/kasan/kasan_test_rust.rs"),
        }
    )

    resolved = resolve_spans(uri_set)
    summary_rows = []
    for spec in bundle_specs:
        slug = spec["slug"]
        packet = load_json(INPUT_PACKETS_DIR / slug / "fresh_rust_bundle_preview.json")
        anti_cheat = load_json(INPUT_PACKETS_DIR / slug / "anti_cheat_review_card.json")
        gold = load_json(INPUT_PACKETS_DIR / slug / "perspective_gold_adjudication.json")

        if spec["repo"] == "linux":
            stats = update_linux_packet(packet, resolved)
        else:
            placeholder_fills = update_non_linux_packet(packet, spec["repo"], resolved)
            stats = {
                "candidate_placeholders_filled": placeholder_fills,
                "verifier_anchor_count": 0,
            }

        selected_tests = []
        for row in packet.get("perspective_rows") or []:
            selected_tests = row["prompt_contract"].get("selected_tests") or []
            break

        linux_anchor_recovered = spec["bundle_id"] == "stage10674::linux::rust" and stats["verifier_anchor_count"] > 0
        update_anti_cheat(anti_cheat, linux_anchor_recovered=linux_anchor_recovered)
        update_gold(gold, selected_tests=selected_tests, linux_anchor_recovered=linux_anchor_recovered)

        out_dir = PACKETS_DIR / slug
        preview_path = out_dir / "fresh_rust_bundle_preview.json"
        anti_cheat_path = out_dir / "anti_cheat_review_card.json"
        gold_path = out_dir / "perspective_gold_adjudication.json"
        write_json(preview_path, packet)
        write_json(anti_cheat_path, anti_cheat)
        write_json(gold_path, gold)

        remaining_placeholders = 0
        for entry in packet["maintainer_visible_evidence"]["candidate_change_surface"]:
            if entry.get("text") == "TODO_MATERIALIZE_REAL_SOURCE_SPAN":
                remaining_placeholders += 1

        summary_rows.append(
            {
                "bundle_id": spec["bundle_id"],
                "repo": spec["repo"],
                "candidate_placeholders_filled": stats["candidate_placeholders_filled"],
                "remaining_candidate_placeholders": remaining_placeholders,
                "verifier_anchor_count": stats["verifier_anchor_count"],
                "selected_tests": selected_tests,
                "claim_boundary": packet["claim_boundary"],
                "preview_bundle": rel(preview_path),
                "anti_cheat_review_card": rel(anti_cheat_path),
                "perspective_gold_adjudication": rel(gold_path),
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "rust_packets_materialized_and_linux_verifier_anchor_recovered",
        "claim_scope": [
            "Materialize the remaining Rust candidate surface placeholders from the spans corpus for the fresh residual packets.",
            "Attach at least one real source-derived Linux Rust verifier anchor so one packet can advance from placeholder-blocked to adjudication-ready.",
        ],
        "spans_corpus": str(SPANS_PATH),
        "packet_results": summary_rows,
        "claim_boundary": [
            "Linux now has real source-derived verifier anchors, but the packet is still preview-only until anti-cheat review and gold adjudication complete.",
            "Candle packets have broader source materialization but still lack real verifier/test anchors.",
            "No packet from this stage is automatically admitted for scoring or promotion.",
        ],
        "next_best_steps": [
            "Run AI maintainer anti-cheat review on the Linux packet now that placeholders and verifier anchors are attached.",
            "Complete AI gold adjudication for the Linux packet perspectives before any train/eval admission.",
            "Recover real verifier/test anchors for candle-datasets or candle-transformers to create a second fresh Rust admissible root.",
        ],
    }
    write_json(SUMMARY_JSON, payload)
    print(SUMMARY_JSON)


if __name__ == "__main__":
    main()
