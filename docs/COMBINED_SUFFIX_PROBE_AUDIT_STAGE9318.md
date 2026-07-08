# Stage9318 Combined Suffix Probe Audit

Safety gate passed: `True`
Quality gate passed: `False`
Exact match rows: `26` / `44`
Target prefix match rate: `0.5909090909090909`
Boundary next-token match rate: `0.9772727272727273`
Contentful generation rate: `0.8181818181818182`
Phrase error counts: `{'patch_ins_fragment': 15, 'verified_patch_contamination': 1, 'pator_fragment': 2, 'constant_to_localizhed': 1}`
The run is safe, but mixing the isolated bridge rows back into the ladder introduced curriculum interference around `patch inside`, `verified patch operator`, and one constant-preserves continuation.
Authority is closed after the audit.
