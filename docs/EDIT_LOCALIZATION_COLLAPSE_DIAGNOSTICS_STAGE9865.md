# Stage9865 Edit-Localization Collapse Diagnostics

Passed: `True`
Fixed alphabetical option order: `True`
Target position singleton by label: `True`
All Stage9864 predictions collapsed to A: `False`
Debiased manifest spreads labels across positions: `True`

This stage turns the Stage9864 collapse into a concrete data hypothesis: the multilingual edit-localization tiny manifest is class-balanced, but it renders options in fixed A/B/C/D/E order, so the output token is also a fixed display position.

Next: Run Stage9866 on the position-debiased edit-localization manifest, then compare whether strict exact rises above 0.25 and whether predictions stop collapsing to label A before changing optimizer or step budgets.

