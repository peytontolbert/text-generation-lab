# Stage9482 Target-Prefix Positive Repair Queue

Passed: `True`
Queue rows: `16`
Existing target-prefix counts: `{'cpp::False': 11, 'cpp::True': 2, 'python::False': 5, 'rust::False': 9, 'rust::True': 19, 'web_js_ts_html::False': 4}`
Queued positives by language: `{'cpp': 4, 'python': 6, 'web_js_ts_html': 6}`
Projected positives by language: `{'cpp': 6, 'python': 6, 'web_js_ts_html': 6}`

Stage9481 failed on a high-confidence CPP positive target-prefix row. Python and web have zero positive target-prefix rows, and CPP has only two. Queue constructs distinct positive target-prefix examples for CPP/Python/web before another probe.

This is a data repair queue only. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
