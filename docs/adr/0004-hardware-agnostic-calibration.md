# 0004 — Hardware-agnostic behaviour via a calibration wizard

## Context

The author's rig is one webcam at 1 m over a bamboo 9×9 board with no projector
yet, but the software should work for anyone with any camera, projector, and
board. Hardcoded resolutions, device paths, throw distances, or wood colors would
make that impossible.

## Decision

All hardware knowledge comes from a wizard that measures instead of assumes:

- camera and resolution discovered at runtime; no device paths
- board size is a parameter (9 in v1, code accepts 13/19)
- per-intersection baselines captured from an **empty board**, so no wood color
  is assumed
- optional lens calibration stored per device, never global
- projector geometry solved from camera observations of projected targets, with a
  `--preview` mode that needs no projector at all

## Consequences

- First run is a guided setup, not a config file.
- Every vision change needs recorded fixtures to prove it still works on other
  setups.
- Features that cannot be expressed as a measured parameter (e.g. "assume
  overhead") are rejected.
