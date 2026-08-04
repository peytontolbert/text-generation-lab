from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEGACY_SRC = ROOT / "legacy_src"
if str(LEGACY_SRC) not in sys.path:
    sys.path.insert(0, str(LEGACY_SRC))

from agentkernel_lite import training_loop


def _bundle(
    tmp_path: Path,
    *,
    source: str = "encoder_option_biencoder",
    provenance: bool = True,
    used_sources: list[str] | None = None,
) -> Path:
    bundle_dir = tmp_path / "runtime"
    bundle_dir.mkdir()
    weights = bundle_dir / "model_state.pt"
    weights.write_bytes(b"focused-runtime-weights")
    metadata: dict[str, object] = {"bounded_choice_aux_source": source}
    if provenance:
        metadata["training_provenance"] = {
            "schema": training_loop.RUNTIME_BUNDLE_PROVENANCE_SCHEMA,
            "training_mode": "bounded_decoder_ce_probe",
            "bounded_choice_aux_source": source,
            "bounded_choice_aux_source_active": True,
            "deterministic_placeholder_sources_used": used_sources or [],
            "deterministic_placeholder_free": not used_sources,
            "source_model_provenance": "fresh_initialization",
            "parent_weights_sha256": None,
        }
    card = {
        "weights_path": "model_state.pt",
        "weights_sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
        "state_dict_keys": 1,
        "metadata": metadata,
    }
    path = bundle_dir / "runtime_model_bundle.json"
    path.write_text(json.dumps(card), encoding="utf-8")
    return path


def _load_cli_module():
    path = LEGACY_SRC / "scripts" / "train_agentkernel_lite_encdec.py"
    spec = importlib.util.spec_from_file_location("runtime_provenance_cli", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_admits_explicit_clean_runtime_bundle(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    result = training_loop.validate_runtime_model_bundle_provenance(bundle)
    assert result["training_provenance"]["deterministic_placeholder_free"] is True
    _load_cli_module()._validate_runtime_initialization_provenance(bundle)


def test_rejects_raw_weights_without_bundle_provenance(tmp_path: Path) -> None:
    weights = tmp_path / "model_state.pt"
    weights.write_bytes(b"weights")
    with pytest.raises(ValueError, match="raw model_state.pt files are not admissible"):
        training_loop.validate_runtime_model_bundle_provenance(weights)


def test_rejects_legacy_bundle_without_training_provenance(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, provenance=False)
    with pytest.raises(ValueError, match="lacks required training_provenance"):
        training_loop.validate_runtime_model_bundle_provenance(bundle)


@pytest.mark.parametrize("source", sorted(training_loop.DETERMINISTIC_PLACEHOLDER_BOUNDED_CHOICE_AUX_SOURCES))
def test_rejects_every_deterministic_placeholder_source(tmp_path: Path, source: str) -> None:
    bundle = _bundle(tmp_path, source=source)
    with pytest.raises(ValueError, match="deterministic placeholder"):
        training_loop.validate_runtime_model_bundle_provenance(bundle)


def test_rejects_hidden_blocked_source_in_used_source_ledger(tmp_path: Path) -> None:
    blocked = "encoder_option_retrieval_evidence_judgment_head"
    bundle = _bundle(tmp_path, used_sources=[blocked])
    with pytest.raises(ValueError, match=blocked):
        training_loop.validate_runtime_model_bundle_provenance(bundle)


def test_rejects_blocked_source_hidden_in_metadata_history(tmp_path: Path) -> None:
    blocked = "encoder_option_retrieval_transition_status_head"
    bundle = _bundle(tmp_path)
    card = json.loads(bundle.read_text(encoding="utf-8"))
    card["metadata"]["ancestor_training_sources"] = [blocked]
    bundle.write_text(json.dumps(card), encoding="utf-8")
    with pytest.raises(ValueError, match=blocked):
        training_loop.validate_runtime_model_bundle_provenance(bundle)
    with pytest.raises(ValueError, match=blocked):
        _load_cli_module()._validate_runtime_initialization_provenance(bundle)


def test_rejects_hash_mismatch(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    card = json.loads(bundle.read_text(encoding="utf-8"))
    card["weights_sha256"] = "0" * 64
    bundle.write_text(json.dumps(card), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        training_loop.validate_runtime_model_bundle_provenance(bundle)


def test_loader_rejects_before_torch_deserialization(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _bundle(tmp_path, provenance=False)
    called = False

    def forbidden_load(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("torch.load must not run")

    monkeypatch.setattr(training_loop.torch, "load", forbidden_load)
    with pytest.raises(ValueError, match="lacks required training_provenance"):
        training_loop._load_runtime_model_bundle(bundle, model=object())
    assert called is False
