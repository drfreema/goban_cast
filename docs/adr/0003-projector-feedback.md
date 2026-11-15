# 0003 — Projector feedback: no center marks, time-multiplexed capture

## Context

The projector shines onto the same surface the camera watches, so projected
markings become board content and can be classified as stones. Real stones also
occlude anything drawn at their center.

## Decision

1. Never draw at a stone center; use rings, brackets, arrows, and offset labels.
2. Prefer saturated red/magenta markers and ignore red-dominant pixels when
   classifying stones.
3. Capture against a baseline that either excludes the overlay (projector blanked
   during readout) or subtracts it.
4. Derive projector geometry from camera observations of projected targets, not
   from measured distances.

## Consequences

- Detection code must be told which pixels are "known projection" - the colour
  gate is part of the classifier, not a UI concern.
- Time-multiplexing needs a frame-rate budget and manual camera exposure lock.
- Markers must remain legible at 3 m without a filled center.
