# Testing log

One line per rule or threshold change, with the reason. Newest at the bottom.

| Date | Phase | Change | Why |
| --- | --- | --- | --- |
| 2026-11-07 | 1 | Foundation test suite added (no scoring rules yet) | Baseline: health, errors, request id, pagination, CORS, audit, user model |
| 2026-11-07 | 2 | Auth suite added; thresholds: login 5/min per IP+email, phone code 10 min / 5 attempts / 3 per hour, reset link 1 h, email link 3 days | Values from the brief; 3-day email link chosen (brief silent) |
| 2026-11-07 | 3 | Skill evidence rounds half-up to 2 dp (0.015 → 0.02) instead of Python round() | round() gave 0.01 for 0.015 (float + banker's rounding); half-up matches the sub-score rounding |
| 2026-11-07 | 4 | Notification rules: 3 delivery attempts (30 s, 60 s backoff), SMS ≤ 160 GSM-7 chars, STOP words list | From the brief (9.1, 9.4); STOP synonyms added for common carrier keywords |
| 2026-11-07 | 5 | Match score gives 0 (not 0.5) for required skills with no evidence | Otherwise every candidate gets half credit for every Emerging requirement (D-032) |
| 2026-11-07 | 5 | Profile views: one per recruiter per job seeker per hour | Repeated page loads shouldn't inflate "N recruiters viewed" |
