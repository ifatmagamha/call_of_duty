The image is a contact sheet of up to six frames sampled uniformly from one short
clinic video; each frame is labeled with its timestamp. Extract one operational fact.
Return QUEUE_COUNT_UPDATED only when the number of people waiting is clearly countable
in a single labeled frame; use that frame's count. Never add counts across frames,
claim to track people, infer dwell time, or treat repeated appearances as distinct
people. Use only visible evidence and the supplied known clinic IDs; use a clinic hint
only when it is valid. If the count is ambiguous, return CLINIC_STATUS_REPORTED with a
concise note. Never invent numbers, recommendations, transfers, or Cypher. Output only
JSON matching the observation contract.
