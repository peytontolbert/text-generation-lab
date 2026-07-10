# Stage9943 Web Weighted Edit Localization Failure Atlas

Passed: `True`
Web rows total: `8`
Web accuracy 100M: `0.25`
Web accuracy Gemma: `0.0`

Materialized a web-specific weighted edit-localization failure atlas that shows the current 100M model only reliably solves symbol-owner rows while missing test-surface, entrypoint, and file-responsibility web cases with low-margin confusion.

Next: Use this atlas to build the next valid web_js_ts_html edit-localization refresh around test-surface, entrypoint-surface, and file-responsibility disambiguation instead of adding more generic web rows.
