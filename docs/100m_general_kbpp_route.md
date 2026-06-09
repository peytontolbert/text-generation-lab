# 100M General KBPP Route

Scope: general knowledge bits per parameter, not agentic/tool-use specialization.

## Current Answer

We do not yet have a non-experimental route that guarantees a 100M general model beats a modern 7B general model.
We do have a concrete density-bridge map: a 100M model must overcome a `70x` parameter deficit, and our controlled curricula already show large but incomplete KBPP multipliers.

## Density Bridge

- Required multiplier if 7B parameters are fully useful: `70.0`
- Observed reliable 26k vs reliable 523k KBPP ratio: `20.231886729514734`
- Observed raw 16k vs reliable 523k KBPP ratio: `32.06583493892847`
- Observed reliable 26k vs reliable 60k KBPP ratio: `2.3324730556844124`
- Observed raw 16k vs reliable 26k KBPP ratio: `1.5849157010230839`
- Remaining multiplier after observed reliable bridge: `3.459884929954774`
- Remaining multiplier after observed raw bridge: `2.1830088046458074`
- 7B effective-useful-fraction threshold for reliable bridge to suffice: `0.2890269532787819`
- 7B effective-useful-fraction threshold for raw bridge to suffice: `0.4580833562704067`

Interpretation: target design has already produced roughly `20x` reliable density movement in the controlled curriculum and `32x` raw density movement at the 16k anchor. If a 7B baseline's recoverable target knowledge uses less than about `29%` of its parameter budget, the reliable bridge could already be enough in principle; if it uses less than about `46%`, the raw bridge could be enough. Otherwise the remaining multiplier must come from broad factorization, tokenizer overhead reduction, reusable abstractions, and measured redundancy in ordinary 7B training.

## Non-Experimental Route Requirements

- `Define general knowledge bits`: A benchmark that counts recoverable atomic, relational, procedural, and compositional knowledge bits independent of agent/tool behavior.
- `Show broad KBPP scaling`: A 10M/30M/100M/300M ladder where answer-equivalent general KBPP rises predictably and the 100M rung exceeds the measured 7B useful-KBPP baseline.
- `Factorize the corpus`: Training data represented as reusable knowledge units: entities, relations, schemas, exceptions, procedures, causal rules, and compositions, with natural-language paraphrase tied back to those units.
- `Use dense semantic supervision`: Every token budget must carry measured knowledge bits; avoid long low-entropy prose when a factorized card or schema carries the same recoverable knowledge.
- `Preserve anchors while compressing`: Targets must remove irrelevant fields but keep discriminative anchors. Stage579 shows minimal key/member/count cards are too compressed.
- `Train a general model, not a sidecar`: Auxiliary KBPP heads are allowed during training, but the final 100M model must answer through its general model path.
- `Establish a non-experimental go/no-go threshold`: Before the final 100M run, the extrapolated KBPP curve must exceed the 7B measured baseline by a margin, not just tie it.

## Candidate Training Route

- Build a broad factorized knowledge corpus from natural data: facts, relations, definitions, procedures, causal rules, code/API semantics, math identities, and multi-hop compositions.
- Train with mixed objectives: next-token language modeling, masked/fill knowledge reconstruction, relation completion, contradiction/false-claim correction, and composition queries.
- Use compact target design from the successful stages: direct keys, compact false claims, rule/exception keys, composition keys, selected anchors for membership-like structures.
- Avoid failed mechanisms: broad replay without target redesign, learned key hashes mixed into tiny embeddings, and over-compressed membership cards.
- Track KBPP continuously: total verified bits/param, operation/procedure-level bits/param, oracle-vs-single-run composability gap, and reliability thresholds.
- Only scale to the final 100M general run after the smaller ladder predicts the 100M KBPP bridge over the 7B baseline.

## Current Read

- The required 100M-vs-7B bridge is about 70x useful knowledge density if every 7B parameter is equally useful.
- The controlled semantic curriculum already shows roughly 20x reliable density improvement from target design at the 26k-vs-523k anchor, and over 32x raw density at the 16k-vs-523k anchor.
- After the observed reliable bridge, the remaining multiplier to a fully utilized 7B is about 3.46x; after the observed raw bridge, it is about 2.18x.
- Equivalently, the observed reliable bridge would be enough if the measured 7B baseline uses no more than about 28.9% of its parameters for recoverable target knowledge; the raw bridge threshold is about 45.8%.
- The remaining bridge must come from broad general-knowledge factorization, tokenizer/vocabulary overhead reduction, better reusable abstractions, and exploiting redundancy in ordinary 7B token-prediction training.
- The route is not proven, but it is now a concrete density-bridge problem rather than a vague small-model hope.

## Source

- JSON: `runs/local/artifacts/100m_general_kbpp_route_map.json`
- KBPP report: `runs/local/artifacts/knowledge_bits_per_param_report.json`
- Operation report: `runs/local/artifacts/operation_bits_per_param_report.json`
