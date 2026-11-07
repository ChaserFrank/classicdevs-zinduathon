# Testing log

One line per rule or threshold change, with the reason. Newest at the bottom.

| Date | Phase | Change | Why |
| --- | --- | --- | --- |
| 2026-11-07 | 1 | Foundation test suite added (no scoring rules yet) | Baseline: health, errors, request id, pagination, CORS, audit, user model |
| 2026-11-07 | 2 | Auth suite added; thresholds: login 5/min per IP+email, phone code 10 min / 5 attempts / 3 per hour, reset link 1 h, email link 3 days | Values from the brief; 3-day email link chosen (brief silent) |
