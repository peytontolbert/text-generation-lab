from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py"
    spec = importlib.util.spec_from_file_location("runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_runner_builds_prompt_and_uses_supported_skill_mapping():
    mod = _load()
    rows = mod.load_packet_rows(mod.load_jsonl(mod.PACKETS)[0])
    field = mod.target_field_for_skill("symbol_binding")
    labels = mod.label_vocab(rows, field)
    prompt = mod.build_prompt(row=rows[0], field=field, labels=labels)
    assert field == "symbol_binding"
    assert "Return only the exact label" in prompt
    assert "Structured input surface:" in prompt
    assert "language=" in prompt
    assert labels


def test_runner_surface_hash_matches_packet_hash_for_first_packet():
    mod = _load()
    packet = mod.load_jsonl(mod.PACKETS)[0]
    rows = mod.load_packet_rows(packet)
    assert mod.prompt_surface_hash(rows) == packet["same_surface_packet"]["surface_hash"]


def test_runner_can_select_bounded_split_slice():
    mod = _load()
    packet = mod.load_jsonl(mod.PACKETS)[0]
    rows = mod.load_packet_rows(packet)
    selected = mod.select_rows(rows, split="strict_eval", max_rows=2)
    assert len(selected) == 2
    assert all(row["split"] == "strict_eval" for row in selected)


def test_bounded_slice_uses_full_packet_label_vocab():
    mod = _load()
    packet = mod.load_jsonl(mod.PACKETS)[0]
    all_rows = mod.load_packet_rows(packet)
    selected = mod.select_rows(all_rows, split="strict_eval", max_rows=2)
    labels = mod.label_vocab(all_rows, mod.target_field_for_skill("symbol_binding"))
    prompt = mod.build_prompt(row=selected[0], field="symbol_binding", labels=labels)
    assert "ABSTAIN_UNBOUND" in prompt
    assert "BIND_IMPORT_TO_MODULE" in prompt
    assert "BIND_TEST_TO_SYMBOL" in prompt
    assert "RETRIEVE_MORE" in prompt


def test_run_packet_result_records_full_packet_label_vocab_scope(monkeypatch, tmp_path):
    mod = _load()
    packet = dict(mod.load_jsonl(mod.PACKETS)[0])
    packet['review_packet_paths'] = {'same_prompt_surface_gemma12b_outputs': 'tmp/test_run_packet_gemma_outputs.json'}
    monkeypatch.setattr(mod, 'ollama_generate', lambda model, prompt, seed=0, temperature=0.0: 'BIND_CALL_TO_SYMBOL')
    result = mod.run_packet(packet, model='gemma3:12b', dry_run=False, split='strict_eval', max_rows=1)
    assert result['label_vocab_scope'] == 'full_packet'
    assert result['decoder_seed'] == 0
    assert result['decoder_temperature'] == 0.0


def test_load_jsonl_accepts_concatenated_multiline_json_objects(tmp_path):
    mod = _load()
    payload = tmp_path / "rows.jsonl"
    payload.write_text(
        """{
  "row_id": "a",
  "value": 1
}
{
  "row_id": "b",
  "value": 2
}
""",
        encoding="utf-8",
    )
    rows = mod.load_jsonl(payload)
    assert [row["row_id"] for row in rows] == ["a", "b"]
    assert [row["value"] for row in rows] == [1, 2]


def test_run_packet_records_full_packet_surface_hash_for_bounded_slice(monkeypatch):
    mod = _load()
    packet = next(row for row in mod.load_jsonl(mod.PACKETS) if row.get('cell_key') == 'standalone_100m_weights::python::edit_localization')
    packet = dict(packet)
    packet['review_packet_paths'] = {'same_prompt_surface_gemma12b_outputs': 'tmp/test_run_packet_surface_hash.json'}
    monkeypatch.setattr(mod, 'ollama_generate', lambda model, prompt, seed=0, temperature=0.0: 'TARGET_SYMBOL')
    result = mod.run_packet(packet, model='gemma3:12b', dry_run=False, split='strict_eval', max_rows=1)
    assert result['same_surface_verified'] is True
    assert result['executed_subset_matches_full_packet'] is False
    assert result['full_packet_surface_hash_gemma12b'] == packet['same_surface_packet']['surface_hash']

