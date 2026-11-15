# goban_cast — agent instructions

Project-specific rules for coding agents. Global style rules still apply.

## Non-negotiables

- **Coordinate spaces.** Every function that takes pixel or board coordinates must name the space:
  `camera_px`, `board_mm`, `canonical`, `projector_px`. Never pass a bare `(x, y)` between modules.
  All transforms live in `src/goban_cast/geometry.py` and need a round-trip test.
- **Fixtures over intuition.** Any change to detection, thresholds, or warping must come with a recorded
  fixture under `tests/fixtures/` (image + expected state). If no fixture exists for the case you are
  changing, record one first.
- **No hardware assumptions.** Do not hardcode resolutions, device paths, throw distances, wood colors,
  or board sizes. Board size is a parameter; the camera and projector are discovered at runtime.
- **Secrets.** OAuth tokens live in the OS keyring. Never write tokens, `client_secret`, or JWTs to
  config, logs, fixtures, or commits. Sanitize recorded OGS traffic before committing it.
- **License.** GPL-3.0. Vendored code from `goban_irl` keeps its header and attribution.

## Layout

```
src/goban_cast/{capture,vision,rules,overlay,ui,net/ogs}
src/goban_cast/geometry.py   # the only place coordinate math may live
tests/unit/                  # fast, no hardware
tests/fixtures/              # recorded frames + expected board states
docs/adr/                    # decision records; add one for any cross-cutting choice
experiments/                 # throwaway spikes, never imported by the package
```

## Checks before committing

```sh
uv run ruff check .
uv run pytest
```
