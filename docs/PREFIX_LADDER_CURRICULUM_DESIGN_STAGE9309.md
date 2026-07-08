# Stage9309 Prefix-Ladder Curriculum Design

Stage9308 kept safety closed but failed the multi-token quality gate.

Finding:
- Boundary next-token rank is solved: expected rank 1 on every row.
- Free-run suffix continuation from `model_input.copy_prefix_span` is unstable.
- Observed failures include `keepside` and `operatch` repetition.

Next patch:
- Materialize prefix-ladder variants at 5, 6, 7, and bridge word prefixes.
- Add denoise rows from observed bad free-run output to clean target.
- Keep decoder CE, runtime, Gemma, harness, scoring, checkpoint export, and promotion closed.
