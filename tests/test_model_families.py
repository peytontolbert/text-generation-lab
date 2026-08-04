from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch

from legacy_src.agentkernel_lite import AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite import MambaRepoStateCompressor as ExportedMambaRepoStateCompressor
from legacy_src.agentkernel_lite import RecurrentGemmaMaintainerModel
from legacy_src.agentkernel_lite import build_model_family as exported_build_model_family
from legacy_src.agentkernel_lite.model_families import (
    MODEL_FAMILY_CLASSES,
    MODEL_FAMILY_IMPLEMENTATIONS,
    AdversarialHardNegativeGAN,
    AutoencoderCompressor,
    BayesianCalibration,
    CRFHMMSequenceLabeler,
    DenoiserMaskedLM,
    DiagonalStateSpaceRepoCompressor,
    MambaRepoStateCompressor,
    DiffusionIterativeRepair,
    EncoderOnlyRetrieverScorer,
    EnergyRewardModel,
    GNNRepoGraphEncoder,
    LinearTreeMLPHeads,
    MoELoRAAdapters,
    NGramMarkovPrior,
    RLBanditController,
    RNNTraceCompressor,
    SymbolicVerifierSuite,
    WorldModelCounterfactual,
    build_model_family,
    get_model_family_class,
)


def assert_backward(loss: torch.Tensor) -> None:
    loss.backward()
    assert loss.ndim == 0


def test_all_registry_families_have_reference_implementations() -> None:
    expected = {
        "ngram_markov",
        "linear_tree_mlp_heads",
        "rnn_lstm_gru_trace",
        "state_space_mamba",
        "gnn_repo_graph",
        "encoder_only_retriever",
        "encoder_decoder_seq2seq",
        "decoder_only_causal",
        "denoiser_masked_lm",
        "diffusion_iterative_repair",
        "autoencoder_compressor",
        "energy_reward_model",
        "gan_adversarial_generator",
        "crf_hmm_sequence_labeler",
        "bayesian_calibration",
        "moe_lora_adapters",
        "rl_bandit_controller",
        "world_model_counterfactual",
        "symbolic_verifiers",
    }
    assert expected <= set(MODEL_FAMILY_IMPLEMENTATIONS)
    assert expected <= set(MODEL_FAMILY_CLASSES)
    assert MODEL_FAMILY_IMPLEMENTATIONS["state_space_mamba"] == "MambaRepoStateCompressor"
    assert MODEL_FAMILY_CLASSES["state_space_mamba"] is MambaRepoStateCompressor
    assert MODEL_FAMILY_CLASSES["encoder_decoder_seq2seq"] is AgentKernelLiteTransformerSeq2Seq
    assert MODEL_FAMILY_CLASSES["decoder_only_causal"] is RecurrentGemmaMaintainerModel
    for family, class_name in MODEL_FAMILY_IMPLEMENTATIONS.items():
        assert MODEL_FAMILY_CLASSES[family].__name__ == class_name
        assert get_model_family_class(family) is MODEL_FAMILY_CLASSES[family]


def test_registry_json_matches_python_model_family_wiring() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = json.loads((root / "configs/software_maintainer/model_family_stack_registry.json").read_text())
    registry_families = registry["model_families"]

    assert set(registry_families) == set(MODEL_FAMILY_CLASSES)
    assert registry["implementation_registry"]["class_map"] == dict(MODEL_FAMILY_IMPLEMENTATIONS)
    for family, spec in registry_families.items():
        assert spec["implementation_class"] == MODEL_FAMILY_IMPLEMENTATIONS[family]
        assert spec["training_authority"] is False
        assert spec["runtime_authority"] is False
        assert spec["fallback_allowed"] is False
    assert registry_families["state_space_mamba"]["implementation_status"] == "wired_cuda_mamba_selective_scan_no_fallback"
    assert registry_families["state_space_mamba"]["state_vector_kind"] == "mamba_selective_scan_embedding"


def test_package_exports_and_factory_resolve_model_families() -> None:
    assert ExportedMambaRepoStateCompressor is MambaRepoStateCompressor
    assert exported_build_model_family is build_model_family

    ngram = build_model_family("ngram_markov", n=2)
    verifier = build_model_family("symbolic_verifiers")
    mlp = build_model_family("linear_tree_mlp_heads", input_dim=3, hidden_dim=4, route_count=2)

    assert isinstance(ngram, NGramMarkovPrior)
    assert isinstance(verifier, SymbolicVerifierSuite)
    assert isinstance(mlp, LinearTreeMLPHeads)
    with pytest.raises(KeyError, match="unknown model family"):
        get_model_family_class("missing_family")


def test_ngram_markov_scores_unusual_tokens_without_authority() -> None:
    prior = NGramMarkovPrior(n=2).fit([["def", "name", "(", ")"], ["def", "other", "(", ")"]])

    familiar = prior.style_anomaly_score(["def", "name", "(", ")"])
    unusual = prior.style_anomaly_score(["return", "???", "pass"])

    assert unusual > familiar


def test_mamba_repo_state_compressor_has_no_cpu_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    with pytest.raises(RuntimeError, match="requires CUDA"):
        MambaRepoStateCompressor(input_dim=5, state_dim=7)


def test_mamba_repo_state_compressor_rejects_cpu_device() -> None:
    if not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")

    with pytest.raises(RuntimeError, match="constructed on CUDA"):
        MambaRepoStateCompressor(input_dim=5, state_dim=7, device="cpu")


def test_mamba_repo_state_compressor_true_cuda_forward() -> None:
    if not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    try:
        free_bytes, _ = torch.cuda.mem_get_info()
    except Exception as exc:
        pytest.skip(f"CUDA memory info unavailable: {exc}")
    if free_bytes < 1_000_000_000:
        pytest.skip("insufficient free GPU memory for mamba_ssm CUDA smoke test")

    device = torch.device("cuda", torch.cuda.current_device())
    model = MambaRepoStateCompressor(input_dim=5, state_dim=8, d_state=4, d_conv=2, expand=1, device=device)
    out = model(
        torch.randn(2, 4, 5, device=device),
        mask=torch.tensor([[1, 1, 0, 0], [1, 1, 1, 1]], device=device, dtype=torch.bool),
    )

    assert out["compressed_repo_state"].shape == (2, 8)
    assert out["state_vector_kind"] == "mamba_selective_scan_embedding"
    assert out["uses_true_mamba_selective_scan"] is True
    assert out["fallback_used"] is False
    assert_backward(out["retrieval_hints"].mean())


def test_mlp_trace_diagonal_reference_and_retriever_modules_are_differentiable() -> None:
    mlp = LinearTreeMLPHeads(input_dim=6, hidden_dim=8, route_count=3)
    trace = RNNTraceCompressor(input_dim=5, hidden_dim=7, workflow_states=4)
    ssm = DiagonalStateSpaceRepoCompressor(input_dim=5, state_dim=7)
    retriever = EncoderOnlyRetrieverScorer(input_dim=6, embedding_dim=4)

    mlp_out = mlp(torch.randn(2, 6))
    trace_out = trace(torch.randn(2, 3, 5))
    ssm_out = ssm(torch.randn(2, 4, 5), mask=torch.tensor([[1, 1, 0, 0], [1, 1, 1, 1]], dtype=torch.bool))
    retrieval_out = retriever(torch.randn(2, 6), torch.randn(3, 6))

    assert mlp_out["route_logits"].shape == (2, 3)
    assert trace_out["workflow_state_logits"].shape == (2, 4)
    assert ssm_out["compressed_repo_state"].shape == (2, 7)
    assert ssm_out["state_vector_kind"] == "diagonal_ssm_embedding"
    assert ssm_out["uses_true_mamba_selective_scan"] is False
    assert retrieval_out["top_k_scores"].shape == (2, 3)

    loss = (
        mlp_out["risk_score"].mean()
        + trace_out["loop_risk"].mean()
        + ssm_out["retrieval_hints"].mean()
        + retrieval_out["top_k_scores"].mean()
    )
    assert_backward(loss)


def test_gnn_repo_graph_encoder_batches_nodes_and_edges() -> None:
    model = GNNRepoGraphEncoder(
        node_feature_dim=4,
        hidden_dim=6,
        node_type_count=3,
        edge_type_count=2,
        layers=2,
    )
    out = model(
        node_features=torch.randn(5, 4),
        node_type_ids=torch.tensor([0, 1, 2, 1, 0]),
        edge_index=torch.tensor([[0, 1, 3], [1, 2, 4]]),
        edge_type_ids=torch.tensor([0, 1, 0]),
        graph_ids=torch.tensor([0, 0, 0, 1, 1]),
    )

    assert out["node_embeddings"].shape == (5, 6)
    assert out["graph_embeddings"].shape == (2, 6)
    assert out["binding_candidates"].shape == (5,)
    assert_backward(out["risk_propagation"].mean())


def test_repair_compressor_reward_gan_moe_bandit_and_world_model_shapes() -> None:
    denoiser = DenoiserMaskedLM(vocab_size=17, hidden_dim=8, layers=1, heads=2, max_positions=8)
    diffusion = DiffusionIterativeRepair(state_dim=6, condition_dim=5, max_steps=4)
    autoencoder = AutoencoderCompressor(input_dim=7, latent_dim=3, hidden_dim=9)
    reward = EnergyRewardModel(repo_dim=4, patch_dim=5, verifier_dim=2, hidden_dim=8)
    gan = AdversarialHardNegativeGAN(noise_dim=3, context_dim=4, example_dim=5, hidden_dim=7)
    moe = MoELoRAAdapters(input_dim=6, output_dim=4, expert_count=3, rank=2)
    bandit = RLBanditController(state_dim=5, action_dim=4, hidden_dim=6)
    world = WorldModelCounterfactual(state_dim=5, action_dim=4, hidden_dim=7, verifier_classes=3)

    denoise_out = denoiser(torch.tensor([[1, 2, 0], [3, 4, 5]]), torch.tensor([[1, 1, 0], [1, 1, 1]]))
    diff_out = diffusion(torch.randn(2, 6), torch.randn(2, 5), torch.tensor([0, 3]))
    ae_out = autoencoder(torch.randn(2, 7))
    reward_out = reward(torch.randn(2, 4), torch.randn(2, 5), torch.randn(2, 2))
    gan_out = gan(torch.randn(2, 3), torch.randn(2, 4))
    moe_out = moe(torch.randn(2, 6))
    bandit_out = bandit(torch.randn(2, 5), torch.randn(2, 4, 4), torch.tensor([[1, 1, 0, 1], [1, 0, 0, 1]], dtype=torch.bool))
    world_out = world(torch.randn(2, 5), torch.randn(2, 4))

    assert denoise_out["cleaned_output_logits"].shape == (2, 3, 17)
    assert diff_out["refined_candidate"].shape == (2, 6)
    assert ae_out["latent_state"].shape == (2, 3)
    assert reward_out["reward_score"].shape == (2,)
    assert gan_out["hard_negative_rows"].shape == (2, 5)
    assert moe_out["specialist_logits"].shape == (2, 4)
    assert bandit_out["next_action_policy"].shape == (2, 4)
    assert world_out["expected_verifier_result"].shape == (2, 3)

    loss = (
        denoise_out["cleaned_output_logits"].mean()
        + diff_out["trajectory_scores"].mean()
        + ae_out["reconstruction_error"].mean()
        + reward_out["candidate_energy"].mean()
        + gan_out["adversarial_shortcut_logits"].mean()
        + moe_out["specialist_logits"].mean()
        + bandit_out["continue_or_stop_logits"].mean()
        + world_out["counterfactual_risk"].mean()
    )
    assert_backward(loss)


def test_crf_sequence_labeler_loss_decode_and_calibration() -> None:
    labeler = CRFHMMSequenceLabeler(input_dim=5, hidden_dim=7, num_labels=3)
    features = torch.randn(2, 4, 5)
    mask = torch.tensor([[1, 1, 1, 0], [1, 1, 1, 1]], dtype=torch.bool)
    labels = torch.tensor([[0, 1, 2, 0], [2, 1, 0, 1]])

    loss = labeler.loss(features, labels, mask)
    decoded = labeler(features, mask)["segment_labels"]
    assert len(decoded) == 2
    assert len(decoded[0]) == 3
    assert len(decoded[1]) == 4
    assert_backward(loss)

    calibrator = BayesianCalibration(evidence_dim=2)
    out = calibrator(torch.randn(2, 3), torch.randn(2, 2))
    assert out["calibrated_probs"].shape == (2, 3)
    assert out["risk_interval"].shape == (2, 2)
    assert_backward(out["calibrated_confidence"].mean())


def test_symbolic_verifier_suite_is_exact_and_non_learned() -> None:
    suite = SymbolicVerifierSuite()

    passed = suite.run("x = 1\n")["python_ast_parse"]
    failed = suite.run("def broken(:\n")["python_ast_parse"]

    assert passed.passed is True
    assert failed.passed is False
    assert failed.repair_signal == "repair_python_syntax"
