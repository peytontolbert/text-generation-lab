import argparse
import importlib.util
from pathlib import Path

import torch


def _load_eval_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "legacy_src" / "scripts" / "evaluate_agentkernel_lite_retrieval_embeddings.py"
    spec = importlib.util.spec_from_file_location("evaluate_agentkernel_lite_retrieval_embeddings", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_structured_key_values_parse_underscored_values():
    module = _load_eval_module()

    parsed = module._structured_key_values(
        "<AK_OP_ENTITY_CONTEXT> op=entity_context domain=domain_003 entity=entity_003_003"
    )

    assert parsed["op"] == "entity_context"
    assert parsed["domain"] == "domain_003"
    assert parsed["entity"] == "entity_003_003"


def test_structured_key_values_parse_pipe_delimited_bind_key():
    module = _load_eval_module()

    parsed = module._structured_key_values(
        "bind_key=entity_context|domain_003|entity_003_003 domain=domain_003 entity=entity_003_003"
    )

    assert parsed["bind_key"] == "entity_context|domain_003|entity_003_003"


def test_structured_key_rerank_penalizes_adjacent_entity_mismatch():
    module = _load_eval_module()
    query = "<AK_OP_ENTITY_CONTEXT> op=entity_context domain=domain_003 entity=entity_003_003"
    correct_doc = (
        "<AK_OP_ENTITY_CONTEXT> entity_context_card domain=domain_003 entity=entity_003_003 "
        "capital=capital_003_003"
    )
    confuser_doc = (
        "<AK_OP_ENTITY_CONTEXT> entity_context_card domain=domain_003 entity=entity_003_008 "
        "capital=capital_003_008"
    )

    scores = module._structured_key_rerank_scores(
        [query],
        [confuser_doc, correct_doc],
        device=torch.device("cpu"),
        dtype=torch.float32,
        match_bonus=0.05,
        mismatch_penalty=0.10,
    )

    assert scores.shape == (1, 2)
    assert scores[0, 1] > scores[0, 0]


def test_structured_key_hard_filter_masks_nonmatching_candidates():
    module = _load_eval_module()
    query = "<AK_OP_RULE_DEFAULT> op=rule_default rule_key=rule_default|domain_028|entity_028_009|risk domain=domain_028 entity=entity_028_009 field=risk"
    correct_doc = (
        "<AK_OP_RULE_DEFAULT> rule_key=rule_default|domain_028|entity_028_009|risk "
        "schema_card domain=domain_028 entity=entity_028_009 field=risk actual=risk_default_03"
    )
    confuser_doc = (
        "<AK_OP_RULE_DEFAULT> rule_key=rule_default|domain_022|entity_022_003|risk "
        "schema_card domain=domain_022 entity=entity_022_003 field=risk actual=risk_default_02"
    )

    scores = module._structured_key_rerank_scores(
        [query],
        [confuser_doc, correct_doc],
        device=torch.device("cpu"),
        dtype=torch.float32,
        match_bonus=0.05,
        mismatch_penalty=0.10,
        hard_filter=True,
        hard_filter_penalty=1000.0,
    )

    assert scores.shape == (1, 2)
    assert scores[0, 0] < -999.0
    assert scores[0, 1] > 0.0


def test_structured_key_hard_filter_rejects_partial_key_overlap():
    module = _load_eval_module()
    query = "<AK_OP_ENTITY_CONTEXT> op=entity_context domain=domain_003 entity=entity_003_003"
    correct_doc = (
        "<AK_OP_ENTITY_CONTEXT> entity_context_card domain=domain_003 entity=entity_003_003 "
        "capital=capital_003_003"
    )
    partial_doc = (
        "<AK_OP_ENTITY_CONTEXT> entity_context_card domain=domain_003 "
        "capital=capital_003_unknown"
    )

    matches = module._structured_key_matches(
        query,
        [module._structured_key_values(partial_doc), module._structured_key_values(correct_doc)],
    )

    assert matches == [False, True]


def test_doc_matches_expected_content_parses_member_answer():
    module = _load_eval_module()

    assert module._doc_matches_expected_content(
        "member_false",
        "<AK_OP_SET_MEMBER> set_member_card domain=domain_001 entity=entity_001_000 member=false count=1",
    )
    assert not module._doc_matches_expected_content(
        "member_false",
        "<AK_OP_SET_MEMBER> set_member_card domain=domain_001 entity=entity_001_000 member=true count=1",
    )


def test_hard_filter_implies_structured_key_rerank():
    module = _load_eval_module()
    args = argparse.Namespace(structured_key_hard_filter=1, structured_key_rerank=0)

    module._normalize_structured_key_args(args)

    assert args.structured_key_rerank == 1
