# goban_cast

Play Go on a **physical board**: a webcam reads your stones, a projector (or a preview window) marks the opponent's moves and captures, and games can be played live on [online-go.com](https://online-go.com).

> Status: **pre-alpha**. Milestone M0 (bootstrap) is done; the vision, rules, overlay, and OGS client are not implemented yet. See [`docs/plan.md`](docs/plan.md) for the full plan, milestones, and risks.

## Why

Existing board readers make you provide corners and tune thresholds by hand. goban_cast aims to be the opposite: a calibration wizard that works with *any* camera, *any* projector, and *any* board, plus a real OGS integration rather than screen-scraping a browser.

## Design constraints

- **Camera agnostic** — any UVC/V4L2/AVFoundation device, any resolution or framerate.
- **Projector agnostic** — any `QScreen` or a plain window; with no projector at all, the overlay renders in a preview window.
- **Board agnostic** — no hardcoded wood colors or thresholds; everything derives from an empty-board capture.
- **v1 is 9×9 only.** Grid code is size-parameterized, so 13×13 and 19×19 are configuration later.
- **Direct OGS integration** — official OAuth2 + PKCE and the documented WebSocket JSON protocol. No browser automation, no `ogsapi`, no bot accounts.

## Install (development)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13 (uv will fetch it).

```sh
uv sync
uv run goban-cast --version
uv run pytest
```

## Coordinate spaces

Every module agrees on four spaces, in this order:

```
camera px ──H_cam──> board mm ──orientation──> canonical board coords ──H_proj⁻¹──> projector px
```

`goban_cast.geometry` owns the transforms and is covered by round-trip tests. Name the space in every function signature; do not pass bare arrays between modules.

## Roadmap

| Milestone | Scope |
| --- | --- |
| M0 | Repo, CI, ADRs, geometry kernel, opencode setup |
| S1 | OGS OAuth + WebSocket handshake spike |
| M1 | Capture, corner pick, warp, 9×9 grid, rotation, stone state |
| M2 | Calibration wizard, bamboo hardening, fixture regression suite |
| M3 | Rules: captures, ko, pass, resign, undo, SGF export |
| M3.5 *(optional)* | Local referee mode: play both colours on the board, app referees and exports SGF |
| M4 | Overlay + preview window + camera-assisted projector alignment |
| M5 | OGS client: `--game <id>`, moves, clocks, reconnect |
| M6 | Physical projector validation, packaging |

## Credits and license

Board-reading approach and starting coordinates from [`Seth-Rothschild/goban_irl`](https://github.com/Seth-Rothschild/goban_irl) (GPL-3.0). Because that detector is vendored, this project is **GPL-3.0** as well.
