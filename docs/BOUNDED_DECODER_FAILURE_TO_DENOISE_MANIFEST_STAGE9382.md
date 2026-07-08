# Stage9382 Bounded Decoder Failure-To-Denoise Manifest

Passed: `True`
Rows: `23`
Repair rows: `12`
EOS calibration rows: `11`
Routes: `{'EOS_CALIBRATION': 11, 'USE_FOR_DENOISE_REPAIR': 12}`
Languages: `{'cpp': 8, 'python': 4, 'rust': 8, 'web_js_ts_html': 3}`

The bounded decoder CE probe remains quality-blocked. These rows route repetition and unterminated failures back into the denoise repair loop, with decoder CE and external authority closed.
