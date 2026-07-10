# Stage9961 Blended Weak-Language Recovery Packet

Passed: `True`
Rows: `48`
Language root counts: `{'c_cpp': 5, 'python': 3, 'rust': 2, 'web_js_ts_html': 6}`
Split counts: `{'eval': 16, 'strict_eval': 16, 'train': 16}`
Reason counts: `{'gemma_advantage_recovery': 15, 'hundred_m_miss_recovery': 27, 'rust_anchor_preserve_winning_pattern': 6}`

Built a blended weak-language recovery packet from the real stage9950/stage9953 same-manifest misses, targeting python, c_cpp, and web_js_ts_html root families while preserving two rust anchor families that already beat Gemma.

Next: Blend this weak-language recovery packet into the next valid 100M edit-localization cycle, then rerun the same-manifest blended comparison to see whether python and c_cpp recover without giving back the web gains.
