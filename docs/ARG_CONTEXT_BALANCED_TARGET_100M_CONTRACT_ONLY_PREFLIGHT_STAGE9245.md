# Stage9245 Argument/Context-Balanced Target-100M Contract-Only Preflight

Passed: `true`

Stage9245 reran the bounded decoder CE probe contract check against the Stage9244 source-backed manifest. This was a contract-only run: no model execution, no decoder CE training, no final checkpoint export, no runtime, no harness, and no Gemma path.

Key results:

- rows: `64`
- train/eval/strict: `32 / 16 / 16`
- probe scale: `target_100m`
- implementation: `transformer`
- decoder CE loss rows: `64`
- non-decoder loss rows: `0`
- authority rows: `0`
- unsafe loss rows: `0`
- over-cap rows: `0`
- empty target rows: `0`
- model execution attempted: `false`
- generation audit requested: `true`

The Stage9244 package superseded Stage9240 because Stage9240 was language-balanced but still argument/context skewed across splits. Stage9245 proves the cleaner package satisfies the trainer command contract before any tiny execution review is recreated.

Next: create a fresh inactive execution review for Stage9244/9245. Actual execution remains closed unless the user explicitly authorizes one tiny probe.
