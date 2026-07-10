# Stage9893 Current Margin Locality Signal Label Remap Manifest

Passed: `True`
Target labels: `['M', 'R', 'T', 'Z']`
Removed K from target vocab: `True`

Built a current-frontier control manifest that keeps the locality-signal lift and all row semantics intact while removing K from the target vocabulary, to test whether the remaining failure is dominated by class-token geometry.

Next: Run Stage9894 on the locality-lifted remapped packet and check whether the improved K semantics survive once K is removed from the target vocabulary.

