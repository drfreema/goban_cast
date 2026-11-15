# 0001 — GPL-3.0 license

## Context

`goban_irl` (GPL-3.0) contains the only well-tested, deliberately-simple board
detector for this use case. Reimplementing it from scratch would cost days and
produce a worse detector.

## Decision

Vendor the detection approach and ship `goban_cast` under **GPL-3.0**, keeping
upstream attribution and headers.

## Consequences

- Anybody redistributing `goban_cast` must comply with GPL-3.0.
- No permissive relicense later without replacing the detector.
- Contributions from others are compatible by default.
