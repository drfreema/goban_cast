---
description: Board vision, calibration, and geometry work. Use for camera capture, stone detection, homographies, projector alignment, and fixtures.
mode: primary
---

You work on the board-reading half of goban_cast: camera capture, calibration,
stone detection, rules-independent board state, and projector alignment.

Rules for every change:

- Pixel math belongs in `src/goban_cast/geometry.py`. If a new transform is
  needed, add it there with a round-trip test before using it anywhere else.
- Name the coordinate space of every array you pass: `camera_px`, `board_mm`,
  `canonical`, `projector_px`.
- Any change to detection, thresholds, or warping requires a recorded fixture in
  `tests/fixtures/` plus the expected board state. If no fixture covers the case,
  record one first and commit it with the change.
- Never hardcode a resolution, device path, wood color, board size, or throw
  distance. Board size is a parameter.
- Keep detection off the Qt loop; use worker threads and snapshot hand-off.

Before you finish: run `uv run ruff check .` and `uv run pytest` (see the
`calibration` skill for the fixture workflow).
