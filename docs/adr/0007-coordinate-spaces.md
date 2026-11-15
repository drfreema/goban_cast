# 0007 — One geometry module owns four coordinate spaces

## Context

The project maps pixels between a camera, a physical board, and a projector. Every
one of those hops is a chance for a transpose or a sign flip, and such bugs look
like detector bugs, so they waste days.

## Decision

All coordinate math lives in `src/goban_cast/geometry.py`, which defines exactly
four named spaces:

```
camera_px ──H_cam──> board_mm ──orientation──> canonical ──H_proj^-1──> projector_px
```

- Functions take and return `(N, 2)` float arrays and name the space in the
  parameter or return name.
- Orientation (0/90/180/270) and mirroring are affine transforms, so they compose
  with homographies instead of being special-cased per module.
- The module is numpy-only, so it is testable without OpenCV or hardware.
- Round-trip tests are mandatory for every new transform.

## Consequences

- Vision, overlay, and UI modules never do their own pixel math.
- Adding a space (e.g. lens-corrected camera pixels) means updating this module
  and its tests first.
