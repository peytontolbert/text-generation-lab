# Stage9867 Edit-Localization Label Identity Probe

Passed: `True`
Label map: `{'A': 'K', 'B': 'M', 'C': 'R', 'D': 'T', 'E': 'Z'}`

This stage prepares a label-identity control: the same Stage9866 rows are kept, but the opaque output labels are renamed from A/B/C/D/E to K/M/R/T/Z.

Next: Run Stage9868 on the relabeled edit-localization manifest and inspect whether collapse moves from literal label A to the new first vocabulary label K.

