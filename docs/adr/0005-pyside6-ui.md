# 0005 — PySide6 for the UI and the projector window

## Context

The app needs two independent surfaces: a control view on the laptop and a
fullscreen overlay on a projector (or in a preview window). Options were
`cv2.imshow`, a local web UI, or a desktop toolkit.

## Decision

Use **PySide6** with a QPainter overlay:

- real multi-window support and per-`QScreen` fullscreen
- the overlay can be rendered into a `QImage` at the screen's native pixel size
  and blitted 1:1, avoiding fractional-scaling blur
- menus, wizards, and hotkeys come for free
- detection runs on worker threads; the Qt loop only consumes snapshots

## Consequences

- Qt is a large dependency; packaging must bundle it.
- On Wayland windows cannot be positioned absolutely: use `setScreen` +
  `showFullScreen`, and document a compositor rule as the escape hatch.
- Overlay rendering must stay off the detection thread.
