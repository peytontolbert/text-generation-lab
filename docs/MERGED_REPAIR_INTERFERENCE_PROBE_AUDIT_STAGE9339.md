# Stage9339 Merged Repair Interference Probe Audit

Passed: `False`
Safety gate passed: `True`
Quality gate passed: `False`
Exact match rows: `59` / `77`
Target prefix match rate: `0.7662337662337663`
Boundary next-token match rate: `0.8571428571428571`
Contentful generation rate: `0.8181818181818182`
Degenerate repetition rows: `14`
Error counts: `{'keeps_the_repetition': 14, 'pator_fragment': 2, 'associated_lis': 2, 'verified_preserves': 0, 'operatch': 0, 'other': 0}`

Safety held, but the rejoin failed. Phrase-B/operator examples now collapse toward dependency-handle `keeps the` repetition, plus a small file-path `associated lis` error. Decoder CE remains closed.
