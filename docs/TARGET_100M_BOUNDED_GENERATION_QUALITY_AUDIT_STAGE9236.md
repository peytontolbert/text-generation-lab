# Stage9236 Target 100M Bounded Generation Quality Audit Probe

Status: failed correctly.

Stage9236 reran the tiny target-100M bounded decoder CE probe after repairing the generation audit. Stage9235 had shown a misleading contentful rate because the old detector missed repeated subtoken/text loops. The corrected audit marks the current output as non-ready.

## Contract

- Manifest: `runs/local/artifacts/stage9211_repo_local_tiny_cap_adapters/bounded_decoder_tiny_cap_manifest.jsonl`
- Rows: 64
- Splits: {'eval': 16, 'other': 0, 'strict_eval': 16, 'train': 32}
- Losses: decoder CE only, 64 rows
- Authority rows: 0
- Over-cap rows: 0
- Unsafe loss rows: 0
- Probe scale: target_100m
- Max steps: 16
- Generation audit rows/tokens: 16 / 96

Still closed: runtime, Gemma, harness/scoring, source/body emission, final checkpoint export, promotion.

## Loss Signal

- Train loss step 1: 84.999535
- Train loss step 16: 7.893096
- Eval loss: 13.711635
- Strict eval loss: 18.407923

The loss movement proves the target transformer/trainer path runs and logs telemetry, but it does not prove decoder capability.

## Generation Quality

- Generated rows: 16
- Contentful generation rate: 0.0
- Exact match rows: 0
- Target-prefix match rate: 0.0
- Short/junk rate: 0.0
- Internal-token generated rows: 0
- Degenerate repetition rate: 1.0
- Unterminated generation rate: 1.0

Representative output:

```text
train_refamily_refamily_refamily_refamily_refamily_refamily_refamily_refamily_refamily_refamily_refamily_refamily_refamily_refamily_refamily_ref
```

This fails the bounded decoder readiness gate: all audited generations repeat and fail to emit EOS.

## Interpretation

The target 100M path is trainer-ready for tiny bounded measurement, but not decoder-capability-ready. The next work is not widening. The next work is to replace placeholder `target_ref::...` rows with real source-backed bounded argument targets and add EOS/repetition counterexamples.

## Next

1. Build a source-backed bounded decoder target materialization stage.
2. Add EOS-positive and repetition-negative rows to the bounded target package.
3. Run contract-only preflight.
4. Run only another tiny target-100M probe if the preflight passes.
5. Keep runtime/Gemma/harness/source/body/promotion closed.
