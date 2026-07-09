# Stage9648 Micro-Overfit Failure Audit

Passed: `True`
Train logits rows: `0`
Prefix conflicts: `{'Return the parser symbol': {'train': {'True': 1}, 'strict_eval': {'False': 1}}, 'Choose the verifier route': {'train': {'False': 1}, 'eval': {'True': 1}}, 'Select the dependency action': {'train': {'True': 1}, 'strict_eval': {'False': 1}}, 'Emit the repair surface': {'train': {'False': 1}, 'eval': {'True': 1}}, 'Identify the import binding': {'eval': {'False': 1}, 'strict_eval': {'True': 1}}, 'Pick the localized edit': {'eval': {'False': 1}, 'strict_eval': {'True': 1}}}`
Top wrong pairs: `{'eval::episode_boundary_match::true=>false': 2, 'eval::episode_target_prefix_match::true=>false': 2, 'strict_eval::episode_boundary_match::true=>false': 2, 'strict_eval::episode_boundary_match::false=>true': 2, 'strict_eval::episode_target_prefix_match::true=>false': 2, 'strict_eval::episode_target_prefix_match::false=>true': 2}`

Stage9647 did not prove the comparison operation. The manifest reused prefixes with opposite labels across splits, so the model could key on prefix identity instead of boundary_expected_token_text versus boundary_generated_token_text. Train logits were not emitted, so the recorded train exact proxy is not strong evidence. The next manifest must include same-prefix positive/negative pairs within every split.

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: Build Stage9649 same-prefix boundary/prefix contrast manifest with positive and negative pairs for each prefix inside train/eval/strict.
