---
name: Calibration and fixtures
description: Use when changing camera capture, stone detection, thresholds, empty-board baselines, or recording/validating test fixtures.
---

# Calibration and fixtures

## Where things live

- Wizard and profile handling: `src/goban_cast/ui/` and `src/goban_cast/vision/`
- Profiles (user data, never committed): `~/.config/goban_cast/profiles/<name>.toml`
- Fixtures: `tests/fixtures/<setup>/<case>/` with `frame.png` and `expected.json`
- Expected state format: `{"size": 9, "stones": [[x, y, "black" | "white"], ...]}`

## Recording a fixture

1. Reproduce the case on real hardware.
2. Capture the raw frame at the same resolution the app will see (no cropping).
3. Write the expected state by eye, then confirm it in the app's debug view.
4. Store under a descriptive setup name (`bamboo-overhead-lamp`, `bamboo-daylight`).
5. Commit the frame and expected state together with the code change.

Prefer small PNGs. If a frame exceeds ~2 MB, downscale only if the case survives
the downscale; otherwise use a cropped region that still contains the corners.

## Validation

```sh
uv run pytest -m vision
uv run goban-cast --preview <profile>   # interactive check on real hardware
```

A detection change is not done until:

- every fixture still matches its expected state
- at least one fixture covers the new case
- the change works on the real board under the lighting you actually play in
