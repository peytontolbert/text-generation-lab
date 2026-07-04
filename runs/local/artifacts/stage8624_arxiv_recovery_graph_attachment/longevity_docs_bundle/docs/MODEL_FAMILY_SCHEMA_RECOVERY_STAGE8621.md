# Stage8621 Model Family Schema Recovery

This document records whether the backed-up Codex sessions contain enough information to reconstruct the separate model-family architecture discussed during v2.7.

## Source

- Session backup: `/arxiv/code/sessions`
- Session files scanned: 741
- Compact index: `runs/local/artifacts/stage8621_model_family_session_recovery/model_family_rg_index.json`

## Session Evidence Counts

| Family bucket | Hits | Files |
|---|---:|---:|
| encoder-decoder / seq2seq / T5 / BART | 437392 | 355 |
| denoising / diffusion | 154930 | 232 |
| confidence / OOD / entropy / calibration | 126978 | 611 |
| MoE / adapters / LoRA | 91830 | 512 |
| activation / logit / gradient / interpretability | 75934 | 480 |
| state-space / Mamba / selective scan | 42414 | 265 |
| RL / bandit / world model / action-value | 29915 | 346 |
| reward / energy / preference | 18603 | 482 |
| causal decoder / autoregressive / KV cache | 16653 | 213 |
| encoder-only / BERT / retriever / reranker | 12361 | 229 |
| autoencoder / latent compression | 12209 | 133 |
| RNN / LSTM / GRU / recurrent | 8940 | 183 |
| GAN / adversarial / hard negative | 7438 | 151 |
| GNN / graph neural / repo graph | 6541 | 157 |
| CRF / HMM / Bayesian | 1373 | 84 |

The counts include unrelated projects, but they prove the sessions contain enough raw material to reconstruct the model-family map.

## What Is Already Recovered

The current docs and config already recover these ideas conceptually:

- SSM/Mamba for repo-wide compression.
- GNN for repo/call/import/test/dependency graphs.
- encoder/retriever and cross-encoder reranker.
- encoder-decoder for state transitions and repair transforms.
- decoder-only as bounded candidate generator only.
- denoising/diffusion as repair layer.
- linear/tree/MLP heads for gates/rankers/confidence/OOD.
- reward/energy models for patch quality and preference.
- symbolic verifiers as the authority layer.

The current action registry also includes recovered behavior-value labels, HOLD/REJECT controls, evidence labels, graph families, and semantic presentation fields.

## What Was Still Missing Before Stage8621

The architecture existed in prose, but not as a machine-readable registry. In particular:

- `configs/model/agentkernel_100m_seq2seq.json` only described the current 100M seq2seq student and heads.
- There was no config describing where RNN, SSM/Mamba, GNN, denoiser, diffusion, GAN/adversarial, energy/reward, MoE/adapters, or RL/bandit components fit.
- There was no explicit cross-model fusion contract.
- There was no explicit list of unimplemented model-family modules.

Stage8621 adds that missing registry:

```text
configs/software_maintainer/model_family_stack_registry.json
```

## Correct Interpretation

We do have enough session evidence to recreate the full separate-model architecture at the design/schema level.

We do not yet have enough recovered implementation to claim those models exist as working modules.

The correct status is:

```text
architecture/schema: recovered enough
implementation: incomplete
training data for each module: incomplete
fusion between modules: not implemented
authority to run/train: closed
```

## Rebuild Priority

1. Keep the 100M seq2seq as the structured transition and bounded argument student.
2. Rebuild repo graph and symbol/test/import objective builders first.
3. Add GNN/graph encoder only after graph rows are useful and audited.
4. Add SSM/Mamba only after long repo/log stream packets are defined.
5. Add denoising repair only after failed-output rows are cleanly routed.
6. Add energy/reward scoring only after verifier-backed preference pairs exist.
7. Add RL/bandit only after SFT policy and verifiers are stable.
8. Add cross-model fusion after each module emits calibrated signals.

