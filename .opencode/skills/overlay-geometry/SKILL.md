---
name: Overlay geometry
description: Use when changing homographies, board rotation or mirroring, camera or projector coordinate mapping, or overlay placement.
---

# Overlay geometry

## The four spaces

```
camera_px  --H_cam-->  board_mm  --orientation-->  canonical  --H_proj^-1-->  projector_px
```

- `camera_px`: raw camera frame pixels.
- `board_mm`: continuous board coordinates in grid units, `0 .. size-1`.
- `canonical`: integer `(x, y)`, x = column, y = row, y points down (image
  convention). Rotation and mirroring are affine transforms on this space.
- `projector_px`: pixels in the projector's native resolution.

## Conventions

- All math lives in `src/goban_cast/geometry.py`. Nothing else may build a
  homography or rotate indices.
- `Homography.then(other)` applies `self` first. Matrices are stored as
  `dst <- src`.
- Orientation is **clockwise in 90° steps**; `mirror` flips horizontally after
  rotation. Four quarter turns must compose to the identity.
- Points are always `(N, 2)` float arrays. A bare tuple means the space is
  ambiguous: reject it in review.

## Checklist for any change

1. Round-trip test: `display_to_camera(camera_to_display(p)) == p`.
2. Invariant test: four 90° turns = identity; mirror twice = identity.
3. Edge test: index `0` and `size - 1` survive rotation and clamping.
4. Overlay test: a known canonical intersection maps onto the right projector
   pixel for a non-trivial (rotated, mirrored) view.
5. If a new space is added, update `docs/adr/0007-coordinate-spaces.md` first.
