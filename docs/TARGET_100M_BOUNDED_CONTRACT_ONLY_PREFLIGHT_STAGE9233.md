# Stage9233 Target 100M Bounded Contract-Only Preflight

Passed: `True`

This stage ran the trainer in `--contract-only` mode against the selected real bounded decoder tiny-cap manifest.

Selected:
- manifest: `runs/local/artifacts/stage9211_repo_local_tiny_cap_adapters/bounded_decoder_tiny_cap_manifest.jsonl`
- model config: `configs/model/agentkernel_100m_seq2seq_recovered_target.json`
- tokenizer: `configs/tokenizer/agentkernel_bpe_1506/tokenizer.json`
- env for future execution: `trellis`

Key results:
- rows: `64` (`32/16/16` train/eval/strict)
- decoder CE rows: `64`
- authority rows: `0`
- over-cap rows: `0`
- unsafe loss rows: `0`
- model execution attempted: `False`

Still closed:
- model execution
- decoder CE training
- runtime
- checkpoint export
- cleanup execution
- Gemma/harness/scoring

Next: If explicitly authorized, run exactly one tiny bounded decoder CE probe under conda env trellis with the same manifest/config/tokenizer/caps; otherwise inspect the contract artifacts and execution command before authorization.
