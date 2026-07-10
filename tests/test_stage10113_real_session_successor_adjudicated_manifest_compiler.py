from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage10113_pending_reviews_remain_blocked() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10113_real_session_successor_adjudicated_manifest_compiler.py",
        "stage10113_pending",
    )
    built = mod.compile_adjudications()
    assert built["audit"]["passed"] is True
    assert built["audit"]["metrics"]["bridge_rows"] == 41
    assert built["audit"]["metrics"]["adjudicated_rows"] == 0
    assert built["audit"]["metrics"]["blocked_rows"] == 41
    assert built["audit"]["claim_boundary"]["supports_training_or_scoring_now"] is False
    first = built["blocked_rows"][0]
    assert "expert_review_incomplete" in first["block_reasons"]
    assert "anti_cheat_review_incomplete" in first["block_reasons"]


def test_stage10113_compiles_completed_adjudication(tmp_path: Path) -> None:
    mod = _load(
        ROOT / "scripts/build_stage10113_real_session_successor_adjudicated_manifest_compiler.py",
        "stage10113_complete",
    )
    bridge_path = tmp_path / "bridge.json"
    review_root = tmp_path / "review_packets"
    row_id = "stage10110::demo_row::python_implementation_vs_config"
    packet_dir = mod.review_packet_dir(review_root, row_id)
    packet_dir.mkdir(parents=True, exist_ok=True)
    bridge_payload = {
        "passed": True,
        "records": [
            {
                "row_id": row_id,
                "episode_id": "demo_episode",
                "repo_id": "demo_repo",
                "language_family": "python",
                "successor_template": "python_implementation_vs_config",
                "prompt_surface": {
                    "candidate_choices": [
                        {"candidate_id": "A", "surface_family": "IMPLEMENTATION"},
                        {"candidate_id": "B", "surface_family": "CONFIG"},
                    ]
                },
                "hidden_metadata": {"raw_change_paths_withheld_from_prompt": True},
                "review_workbook_path": "runs/local/artifacts/stage10111_real_session_successor_review_packets/real_session_successor_signoff_workbook.json",
            }
        ],
    }
    bridge_path.write_text(json.dumps(bridge_payload, indent=2) + "\n", encoding="utf-8")
    (packet_dir / "expert_maintainer_rubric_review.json").write_text(
        json.dumps(
            {
                "row_id": row_id,
                "status": "completed_human_review",
                "passed": True,
                "gold_label_slot": {
                    "selected_candidate_id": "A",
                    "abstain_due_to_insufficient_evidence": False,
                    "reviewer_rationale": "Candidate A is the only maintainer-plausible source of the visible behavior.",
                },
                "rubric_lines": {key: True for key in mod.RUBRIC_LINES},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (packet_dir / "anti_cheat_review_card.json").write_text(
        json.dumps(
            {
                "row_id": row_id,
                "status": "completed_human_review",
                "passed": True,
                "reviewer_notes": "No template prior or candidate-order shortcut survives the visible prompt.",
                "challenge_lines": {key: True for key in mod.ANTI_CHEAT_LINES},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    adjudicated_path = tmp_path / "adjudicated.jsonl"
    blocked_path = tmp_path / "blocked.jsonl"
    audit_path = tmp_path / "audit.json"
    built = mod.compile_adjudications(
        bridge_artifact=bridge_path,
        review_root=review_root,
        adjudicated_manifest_path=adjudicated_path,
        blocked_rows_path=blocked_path,
        audit_path=audit_path,
        expected_bridge_rows=1,
    )
    assert built["audit"]["passed"] is True
    assert built["audit"]["metrics"]["adjudicated_rows"] == 1
    assert built["audit"]["metrics"]["blocked_rows"] == 0
    assert built["audit"]["claim_boundary"]["supports_training_or_scoring_now"] is True
    compiled = [json.loads(line) for line in adjudicated_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert compiled[0]["gold_answer"] == "A"

