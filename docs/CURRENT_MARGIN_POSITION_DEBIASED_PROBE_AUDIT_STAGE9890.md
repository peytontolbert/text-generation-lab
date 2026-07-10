# Stage9890 Current Margin Position-Debiased Probe Audit

Passed: `True`
Eval exact: `0.4375`
Strict exact: `0.4375`
Delta vs Stage9886 eval: `0.0`
Delta vs Stage9886 strict: `-0.0625`
Per-cell delta vs Stage9886: `{'c_cpp::current_margin_edit_localization_counterfactual_guard::KEEP_STRUCTURED': 0.0, 'python::current_margin_edit_localization_counterfactual_guard::KEEP_STRUCTURED': 0.0, 'rust::current_margin_edit_localization_counterfactual_guard::KEEP_STRUCTURED': 0.0, 'web_js_ts_html::current_margin_edit_localization_counterfactual_guard::KEEP_STRUCTURED': -0.125}`

The Stage9889 position-debiased rerun is useful as an eval-validity audit, but not as a frontier improvement. Eval exact stays flat, strict exact regresses, and the K-to-R collapse survives unchanged while web weakens.

Next: Keep the position-debiased packet as an eval-validity artifact, but move the next training intervention upstream to evidence or objective changes that directly break the persistent K-to-R collapse.

