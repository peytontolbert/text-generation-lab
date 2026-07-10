# Stage10009 Quarantined Blended V2.7 Mix

Passed: `True`
Source blended rows: `404`
Rows removed from active blend: `8`
Rows remaining after quarantine: `396`
Removed language counts: `{'c_cpp': 3, 'python': 5}`
Removed split counts: `{'eval': 3, 'strict_eval': 5}`

Built a quarantined successor to the active blended v2.7 structured mix so unresolved Gemma-advantage edit-localization eval rows stop influencing training or multilingual reporting until human review closes them.

Next: Use this quarantined 396-row successor as the default blended v2.7 training/eval mix until the 22 open Gemma-advantage signoff tasks resolve whether each removed row should be kept, abstention-relabeled, or permanently excluded.
