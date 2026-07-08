# Stage9451 Episode-Step Denoise Objective Design

Passed: `True`

The episode-step manifest should first train small structured supervision targets: repair outcome, failure type, boundary match, prefix match, and value. It must not reopen decoder CE from these rows.

Next: patch loss-mask/loss-key registry for episode-step supervision, then audit closure.
