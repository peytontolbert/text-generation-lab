# Stage8667 Visible Copy Target Remediation

Passed: `True`

- Visible repo-dependency copy rows: `360`
- Unexpected non-copy target rows: `0`
- Recommendation rows: `360`

Decision: Visible target hits are confined to a direct copy field and must be moved from semantic CE to explicit copy-field supervision before training. Stage8665 remains correctly failed until builders apply this remediation.

All authorities remain closed.
