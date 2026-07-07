from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9117_metadata_only_inventory_runner_static_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_audit,
    validate_audit,
)
from scripts.metadata_only_inventory_runner import build_parser, validate_args  # noqa: E402


def registry(latest: int = 9116) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_metadata_only_inventory_runner_parser_has_required_flags() -> None:
    parser = build_parser()
    option_strings = {option for action in parser._actions for option in action.option_strings}

    for option in [
        "--datasets-root",
        "--repositories-root",
        "--output-dir",
        "--max-depth",
        "--metadata-only",
        "--no-row-reads",
        "--no-source-body-reads",
        "--no-arxiv-writes",
        "--no-follow-symlinks",
        "--require-ticket-audit",
    ]:
        assert option in option_strings


def test_metadata_only_inventory_runner_validate_args_rejects_unsafe_values() -> None:
    args = Namespace(
        datasets_root="/tmp/not_datasets",
        repositories_root="/tmp/not_repositories",
        output_dir="/tmp/outside",
        max_depth=99,
        metadata_only=False,
        no_row_reads=False,
        no_source_body_reads=False,
        no_arxiv_writes=False,
        no_follow_symlinks=False,
        require_ticket_audit="/tmp/missing_audit.json",
    )

    failures = validate_args(args)
    assert "datasets_root_is_not_arxiv_datasets" in failures
    assert "repositories_root_is_not_arxiv_repositories" in failures
    assert "output_dir_not_under_runs_local_artifacts" in failures
    assert "max_depth_out_of_bounds" in failures
    assert "metadata_only_flag_required" in failures
    assert "row_reads_not_disabled" in failures
    assert "source_body_reads_not_disabled" in failures
    assert "arxiv_writes_not_disabled" in failures
    assert "symlink_follow_not_disabled" in failures
    assert "ticket_audit_missing" in failures


def test_stage9117_static_audit_passes_without_execution() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["checks"]["source_stage9116_passed"] is True
    assert audit["checks"]["runner_present"] is True
    assert audit["checks"]["required_cli_flags_present"] is True
    assert audit["checks"]["runtime_assertion_terms_present"] is True
    assert audit["checks"]["follow_symlinks_false_present"] is True
    assert audit["checks"]["forbidden_source_patterns_absent"] is True
    assert audit["metrics"]["runner_executed_now"] is False
    assert audit["metrics"]["arxiv_access_performed"] is False
    assert audit["metrics"]["dataset_rows_loaded"] is False
    assert audit["metrics"]["repository_source_bodies_loaded"] is False
    assert not any(audit["authority"].values())


def test_stage9117_validation_rejects_execution_access_or_bad_frontier() -> None:
    audit = build_audit(registry())
    assert validate_audit(audit, registry()) == []

    runner = build_audit(registry())
    runner["metrics"]["runner_executed_now"] = True
    assert "runner_executed_now" in validate_audit(runner, registry())

    arxiv = build_audit(registry())
    arxiv["metrics"]["arxiv_access_performed"] = True
    assert "arxiv_access_performed" in validate_audit(arxiv, registry())

    source = build_audit(registry())
    source["metrics"]["repository_source_bodies_loaded"] = True
    assert "repository_source_bodies_loaded" in validate_audit(source, registry())

    authority = build_audit(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_audit(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_audit(audit, registry(latest=9999))
