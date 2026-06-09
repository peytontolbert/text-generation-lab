# Stage629-631 Canonical Selector Internalization

Artifact: `runs/local/artifacts/stage629_631_canonical_selector_internalization_summary.json`

## Summary

Stages629-631 test whether the shorter Stage628 canonical selector surface can be learned by continuation instead of used as a schema-only replacement.

- Stage629: 150-step continuation with decoder CE accidentally enabled. Kept as a config control.
- Stage630: 150-step retrieval-only continuation from Stage602 on Stage628 canonical rows.
- Stage631: another 150-step retrieval-only continuation from Stage630.

## Results

| run | exact | answer | exact bits/param | answer bits/param | hard-filter corrections |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stage628 schema-only | `0.9525641025641025` | `0.9653846153846154` | `1.532409132890377` | `1.5530337510988612` | `111` |
| Stage629 decoder-CE control | `0.9538461538461539` | `0.9666666666666667` | `1.5344715947112257` | `1.5550962129197098` | `108` |
| Stage630 retrieval-only | `0.9547008547008548` | `0.9666666666666667` | `1.535846569258458` | `1.5550962129197098` | `106` |
| Stage631 retrieval-only continued | `0.9534188034188035` | `0.9675213675213675` | `1.5337841074376092` | `1.5564711874669422` | `109` |
| Stage626 frontier | `0.967948717948718` | `0.9794871794871794` | `1.5571586747405581` | `1.5757208311281938` | `75` |

## Decision

Rejected as a frontier, but accepted as positive internalization evidence.

The canonical surface can recover a few rows with retrieval-only training:

- Stage630 is the best exact canonical continuation.
- Stage631 is the best answer canonical continuation.

However, both remain far below Stage626. More blind continuation on canonical rows is unlikely to close the gap because the loss improves while `entity_context` stays flat around `0.8402777777777778` answer. The next better route is a two-surface mix or annealing curriculum: preserve the accumulated Stage626 selector scaffolding while gradually teaching the canonical representation, or target `entity_context` with a specific bridge rather than full-surface canonical retraining.
