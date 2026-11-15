# goban_cast — Project Plan

Play Go on a physical board with a webcam, a projected overlay, and live games on online-go.com (OGS).

- Owner: `drfreema`
- Repo: `https://github.com/drfreema/goban_cast` (public, GPL-3.0)
- Status: plan approved; M0 (bootstrap) and S1 (OGS handshake) executed
- Date: 2026-11-15

---

## 1. Feasibility

**Feasible.** The board-reading half is proven by [`Seth-Rothschild/goban_irl`](https://github.com/Seth-Rothschild/goban_irl), which turns an image plus four board corners into a 19×19 stone state and deliberately ignores Go rules. That library is the starting point for board coordinates, with these known weaknesses we plan to fix: fixed black/white cutoffs, no ambient-light handling, manual corner entry, and an OpenCV pin (`4.5.2`) that no longer builds on current Python.

The genuinely new risk is **the projector sitting inside the camera's field of view**, not the vision itself.

| Piece | v1 risk | Notes |
| --- | --- | --- |
| 9×9 stone detection, overhead, bamboo board | Medium | Bamboo grain reads as black stones, gloss reads as white. Fixed by per-intersection empty-board baselines, saturation gating, stone-shaped blob checks, temporal hysteresis |
| Rotate board in 90° steps | None | Array transform, 4 orientations + optional mirror |
| Overlay on app canvas (no projector yet) | Low | Separate preview window with its own homography |
| Real projector alignment | Medium (hardware-gated) | Camera-assisted auto-alignment rather than measured throw distance |
| OGS play | **Medium-low** | OGS has official OAuth2 + PKCE and a documented raw JSON WebSocket protocol; no third-party client needed |
| Rules / captures / ko / turn | Low | ~250 LOC plus tests; cannot be skipped, the app must referee |

### Resolution math for the chosen setup (1 m overhead, 9×9)

At 1 m with a ~70° lens a 1080p camera sees ≈1.2 m wide. A 9×9 playing area is ≈30 cm, so ≈480 px across the grid, or **≈60 px between lines** — about 4× more than detection needs. Even 720p works. Implication: the camera does not need to be special, which is what makes "camera agnostic" realistic. Keep the board inside the central ~60% of the frame to avoid wide-lens edge distortion, and that framing also leaves room for 19×19 later (≈30 px spacing).

### The one insight to design around

The projection is visible to the camera. Consequences:

1. **Never project at the stone center.** Use rings, corner brackets, arrows, and labels offset from the intersection — also survives occlusion by real stones.
2. **Time-multiplex**: capture while the projector is blank, or detect against a cached baseline with the overlay subtracted.
3. **Color-key the overlay**: saturated red/magenta markers, with detection classifying luminance in Lab and ignoring red-dominant pixels.
4. **Calibrate geometry with the camera, not by eye**: project four targets, detect them, solve the homography.

Coordinate chain, referenced by every module:

```
camera px ──H_cam──> board mm ──orientation──> canonical board coords ──H_proj⁻¹──> projector px
```

Every bug in this project will be a transpose or a sign flip in that chain. One `geometry.py` with round-trip tests is worth more than any single feature.

### Licensing and Python

`goban_irl` is **GPL-3.0**, so vendoring its detector makes `goban_cast` GPL-3.0. Accepted. The repo pins **Python 3.13 via uv** (system Python 3.15 is too new for OpenCV wheels and for pinned socket/auth stacks).

---

## 2. Decisions

| # | Decision |
| --- | --- |
| 1 | Public GitHub repo `drfreema/goban_cast`, GPL-3.0 |
| 2 | Python 3.13 via `uv` |
| 3 | PySide6 (QPainter overlay), not a web UI |
| 4 | OGS integrated **directly at the API** (OAuth2 + PKCE + raw WebSocket JSON), no browser automation, no `ogsapi`, no `gtp2ogs` |
| 5 | v1 is **9×9 only**; grid generation is size-parameterized from the first commit |
| 6 | Camera and projector are **agnostic**: any UVC/V4L2/AVFoundation device, any resolution; any `QScreen` or a plain window; no hardware may be assumed by the code |
| 7 | Redirect URI: try loopback `http://127.0.0.1:8765/callback`; fall back to an https code-paste page if OGS rejects non-https |

Rationale recorded in `docs/adr/`.

---

## 3. Architecture

```
src/goban_cast/
  capture/     frame source, format negotiation, drop-old-frames, FPS/latency metrics
  vision/      corner pick, warp, empty-board baseline, intersection classifier, confidence
  rules/       board state, move apply, captures, ko, pass, resign, undo, SGF export
  geometry.py  homographies, orientation (0/90/180/270), mirroring, coordinate spaces
  overlay/     rendering: opponent ghost, last-move ring, capture rings, turn, clocks, labels
  ui/          PySide6: MainWindow, ProjectorWindow, CalibrationWizard, preview mode
  net/ogs/     oauth.py, socket.py, protocol models, transport abstraction (real | MockOGS)
  app.py       wiring and state machine: calibrate → observe → my turn → opponent → project
```

**Threads:** capture, detection, network; the Qt loop only consumes snapshots. Detection never blocks the UI.

**State machine:** `unconfigured → calibrating → observing → awaiting_opponent → applying_move → game_over`, plus `paused`/`error`. Every transition is logged with the board hash for post-mortems.

**Two operating modes share the pipeline:** `online` (attached to an OGS game, M5) and `referee` (optional M3.5 — both colours are observed locally, no network, no projector).

**Config:** `pydantic-settings` + TOML profiles under `~/.config/goban_cast/profiles/<name>.toml` holding camera/projector geometry, thresholds, board size. OAuth tokens go to the OS keyring, never to config or the repo.

**Overlay contents (v1):** opponent's last move, own last move, capture rings + counts, turn indicator, both clocks, 9×9 coordinate labels, connection/status strip.

**Wayland/Hyprland specifics:** Qt cannot position windows on Wayland, so the projector window does `setScreen(screen)` then `showFullScreen()`; a documented `hyprctl` window rule is the escape hatch. Overlay is rendered into a `QImage` at the screen's native pixel size and blitted 1:1 to avoid fractional-scaling blur. A `systemd-inhibit`-style idle inhibit keeps the projector awake.

---

## 4. Hardware-agnostic calibration wizard

First-class feature, not a README step:

1. pick camera + resolution (list devices, prefer 1080p30, warn on MJPEG-interlaced)
2. pick board size (9 in v1; 13/19 accepted by the grid code)
3. click the four playable corners
4. capture the empty board → per-intersection baselines
5. place one black and one white stone at center and two corners → contrast fit
6. optional chessboard lens calibration, stored per device name+resolution
7. pick projector screen (or `--preview`)
8. project four targets → camera solves `H_proj` automatically
9. save named profile

Bamboo hardening: circular mask ≈0.8 stone diameter per intersection; compare against that intersection's own empty baseline; classify in Lab with a saturation gate; require a stone-shaped blob (morphological open + area/shape test) so grain streaks and specular slivers are rejected; confirm after N stable frames; ignore changes on the opponent's turn. Fixtures recorded under three lighting conditions live in `tests/fixtures/bamboo/`.

---

## 5. OGS integration

### 5.1 Registration (do this first, it is self-service)

Register at <https://online-go.com/oauth2/applications/> (limit: 5 apps per user). Choices for goban_cast:

| Field | Value | Why |
| --- | --- | --- |
| Name | `goban_cast` | Shown on the consent screen |
| Client type | **Public** | Desktop app cannot keep a secret; uses PKCE |
| Authorization grant type | **Authorization code** | Only flow OGS documents for third-party apps |
| Redirect URIs | `http://127.0.0.1:8765/callback` | Loopback listener for the one-shot local HTTP server |
| Algorithm / OIDC fields (if shown) | leave default | We consume plain OAuth2 tokens, not ID tokens |
| Skip authorization (if shown) | **unchecked** | Stay behind user consent |

Scopes requested at authorize time: `read write`. `client_secret` is ignored for a public client; do not store one. If OGS refuses the `http://` loopback URI, register an `https://` page that displays `?code=` for one-time paste and add it to the same app.

### 5.2 Flow

1. `GET /oauth2/authorize/?client_id=…&response_type=code&redirect_uri=…&scope=read+write&state=…&code_challenge=…&code_challenge_method=S256`
2. system browser opens; loopback server captures `code`, validates `state`
3. `POST /oauth2/token/` with `grant_type=authorization_code`, `code`, `redirect_uri`, `client_id`, `code_verifier`
4. store `refresh_token` in the OS keyring; access + refresh tokens both last 30 days, refresh silently on startup
5. `GET /api/v1/ui/config` with `Authorization: Bearer <access_token>`, read `user_jwt`
6. open the OGS WebSocket and send `["authenticate", {jwt: user_jwt, client: "goban_cast", client_version, device_id, user_agent}]`

**Spike S1 (1 day, before any UI work): done 2026-11-15.** The full chain works on the
live server: OAuth2/PKCE with a loopback redirect → bearer token → `/api/v1/ui/config`
returns the real user's `user_jwt` → `wss://online-go.com` accepts `authenticate` and
replies with `{id, username}`. No `client_secret`, no https fallback needed. Details
and reproduction in ADR-0002 and `experiments/ogs_handshake.py`.

### 5.3 Protocol surface (v1)

Outbound: `authenticate`, `net/ping` (every 10 s, drives clock drift), `game/connect {game_id, chat}`, `game/move {game_id, move}`, `game/undo/request|accept|cancel`, `game/chat`, resign as a move (`"resign"`).

Inbound: `game/:id/gamedata` (initial state), `game/:id/move`, `game/:id/clock`, `game/:id/phase` (`play` / `stone removal` / `finished`), `game/:id/error`, `game/:id/undo_requested|accepted|canceled`, `net/pong`, `user/jwt`.

Wire format: client → `[command, data, id?]`; server → `[event, data]` or `[id, data | error]`.

### 5.4 Scope reduction that buys weeks

v1 does **not** create challenges or run automatch. Create the 9×9 challenge on the OGS website, then start the app with `--game <id>`. That removes challenge negotiation, seekgraph, and matchmaking from v1 while keeping the integration fully API-based. Challenge creation via REST is a v2 nicety.

### 5.5 Testability

`MockOGS` replays sanitized recorded sessions (gamedata → opponent move → clock → phase → finish). Everything above the transport is tested in CI with no network and no account. Recordings are captured by `experiments/ogs_handshake.py` with usernames/JWTs scrubbed.

---

## 6. Milestones

| # | Deliverable | Effort | Acceptance |
| --- | --- | --- | --- |
| M0 | Repo, license, CI, ADRs, package skeleton, geometry + tests, opencode agents/skills | 1 d | CI green; `uv run pytest` passes; plan linked from README |
| S1 | OGS OAuth + handshake spike | 1 d | **done** — live server confirms OAuth2/PKCE → `user_jwt` → WebSocket `authenticate` |
| M1 | Capture, corner pick, warp, 9×9 grid, rotation, vendored detector, state dump | 2–3 d | Grid aligned to bamboo board; zero false stones over 5 min idle |
| M2 | Calibration wizard, baselines, bamboo hardening, fixture recorder, confidence UI | 3–5 d | Survives daylight/lamp changes without recalibration; fixtures in CI |
| M3 | Rules, captures, ko, pass, resign, undo, SGF export | 2 d | Referees a full 9×9 game played on the board |
| M3.5 (optional) | **Local referee mode** — see §6.1 | 2–3 d | A full self-play 9×9 game of ≥60 moves exports SGF that loads in Sabaki/OGS review with correct captures; no more than one undo |
| M4 | Overlay rendering, preview window, projector screen selection, camera-assisted auto-align | 3–4 d | Overlay lands on correct intersections in preview; auto-align converges with a stand-in display |
| M5 | OGS client: OAuth, keyring, MockOGS, `--game`, move send/receive, clocks, phase, reconnect | 4–6 d | Complete a live 9×9 game on OGS with no browser |
| M6 | Physical projector validation + packaging (PKGBUILD / `uv tool install`) | 1 wk, hardware | Real game with stones and projection |

Total ≈ **7–9 weeks part-time**, plus 2–3 days if the optional referee milestone is taken. S1 and M5 touch no camera code and can run in a parallel session (see §8).

## 6.1 Optional milestone M3.5 — Local referee mode

**Purpose.** A genuinely useful product before any projector exists: two people play
on the physical board, and the app acts as referee and scorekeeper. It exercises the
whole vision + rules pipeline end to end without OGS, clocks, or projection, so it
de-risks M4/M5 and gives something to use on the board immediately.

**Depends on:** M1, M2 (detection must be trustworthy) and M3 (rules). Everything it
needs already exists by then.

**Scope**

- `goban-cast --referee` (no game id, no projector): both colours are observed on the
  board, moves alternate automatically.
- Confirms each detected move against the rules: legality, captures, ko, suicide,
  and whose turn it is. Illegal or ambiguous detections are refused, not applied.
- Announces captures and rejected moves in the status panel and with a short sound
  cue; the laptop screen shows board, last move, captures, and move count.
- Keyboard undo of the last move (mis-detection recovery), and pass / resign.
- Resume from an SGF file and export the finished game as SGF (`sgfmill`), including
  captures and move numbers.
- Minimal rendering: a text/status panel plus the existing debug grid. It must **not**
  build projector-specific overlay work — that stays in M4.

**Explicitly out of scope:** clocks, OGS, projector alignment, record/analysis,
variations, multiple games at once.

**Acceptance**

1. Play a complete self-play 9×9 game of at least 60 moves with the app refereeing.
2. Captures in the app match the physical board at the end of the game.
3. The exported SGF opens in Sabaki and in OGS review with the correct move list and
   captured stones.
4. At most one undo correction for the whole game under normal room lighting.

**Why it may be worth doing first.** It needs no network account and no hardware
purchase, and it converts the vision work into something you can actually use. If it
slips, M4/M5 are unaffected — it is a detour, not a dependency.

---

## 7. Hardware appendix — what to buy

**Camera (already have one).** Any 1080p UVC webcam is enough. The only feature that matters is **manual exposure and white-balance lock**; verify with `v4l2-ctl -d <dev> --list-ctrls` and prefer a camera exposing `exposure_absolute`/`white_balance_temperature`. 60 fps helps the capture/project time-multiplexing. Note: this machine currently exposes `/dev/video42` as a **v4l2loopback** device ("Windows Camera"), i.e. the real camera is streamed in from elsewhere; confirm the producer's format and whether exposure control survives the loopback.

**Projector.** Markers only need contrast, not color fidelity.

- Native resolution: **1280×800 (WXGA) or 1920×1080**; avoid 800×600. 4:3 XGA (1024×768) works but gives coarse bracket geometry.
- **Throw ratio is the spec that decides whether it works on a board.** For a ~35 cm image at ~0.5–1.2 m you need a short-throw unit (≈0.5–0.8:1). Typical 1.2–1.4:1 office projectors need ~0.5 m for 60 cm and are awkward to mount above a board. Check the vendor's throw-distance table against your mount before buying.
- Brightness: ≥300 ANSI lumens in a dim room; ≥500 if daylight. **Contrast ratio matters more than lumens** for crisp rings on light bamboo.
- Disable keystone/auto-correction and any "auto brightness"/eco mode — we do our own software warp and need stable output.
- 60 Hz at native resolution over HDMI; latency is irrelevant.
- Used business projectors (Epson EB series, BenQ MX/TH) are the best value; a short-throw education model is ideal.
- Mounting: rigid arm/ceiling bracket above the board, offset so the projector is not in the camera's view and its exhaust does not shimmer the air in front of the lens.

---

## 8. OpenCode usage

### 8.1 Agents

| Agent | Mode | Purpose |
| --- | --- | --- |
| `vision` | primary | OpenCV/geometry/calibration. Must add a fixture for any detector change; keeps coordinate spaces named |
| `ogs` | primary | Protocol and auth only. Reads `docs.online-go.com` and `goban` sources; never logs tokens; extends `MockOGS` fixtures |
| `reviewer` | subagent | Read-only diff review: geometry sign errors, edge off-by-ones, fixture coverage, secrets, GPL headers |

Daily loop: **Plan** to sketch → **Build** (or `vision`/`ogs`) to implement → `reviewer` before committing.

### 8.2 Skills

- `calibration` — wizard steps, fixture workflow, validation commands.
- `overlay-geometry` — the four coordinate spaces, homography direction conventions, round-trip test checklist.
- `ogs-protocol` — message shapes, handshake recipe, keyring rule, replay harness.

### 8.3 Worktrees, explained (new-user note)

A git worktree is a second checkout of the same repository: its own directory and branch, sharing one `.git` history. Nothing is duplicated except working files.

In OpenCode:

- `/worktree` (TUI) or `opencode --worktree` starts a **new session in a fresh worktree**. This cannot be combined with `--continue`/`--session`.
- Agent tools `worktree_create`, `worktree_list`, `worktree_remove` manage them; `session_move` moves the current session into a worktree so later turns run there. Worktree paths are whatever `worktree_list` reports — let the tool tell you, don't guess.
- Strategy: `fresh` (default) branches from `origin/<default-branch>` for a clean tree; `head` branches from your local HEAD so unpushed work is present.
- Optional config: directories pulled in via git sparse-checkout (cone mode), and directories **symlinked** from the main checkout to avoid disk bloat (e.g. `node_modules`, `.venv`, model caches). Nothing is symlinked by default.
- `worktree_remove` keeps commits; with `force` it discards modified and untracked files in that worktree.

**When it is worth it here:** only if two sessions edit concurrently. S1/M5 (network) and M1/M2 (vision) touch disjoint files, so a worktree for `ogs` work keeps the vision branch's uncommitted experiments safe. If you work serially, one session plus the `vision`/`ogs` agents is simpler — skip worktrees until you actually need them.

### 8.4 Commands

`/verify` (ruff + pytest + fixture check), `/fixture-check` (headless detection diff over fixtures), `/adr <topic>` (write a decision record).

---

## 9. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Bamboo grain/specular false stones | Per-intersection baselines, saturation gate, blob-shape test, hysteresis, fixtures |
| Projector feedback into detection | Blank-during-capture, red markers, baseline subtraction, detect only near intersections |
| OGS rejects `http://` redirect | https code-paste fallback, redirect URI configurable |
| OGS token chain (`user_jwt`) differs from assumption | 1-day S1 spike before UI work; ADR records the outcome |
| OGS protocol drift | Protocol models isolated in `net/ogs/protocol.py`; recorded fixtures catch changes |
| Hardware flare from the projector | Time-multiplex + short exposure; validate in M6 |
| GPL contamination of a wanted-more-permissive project | Accepted; recorded in ADR-001 |

## 10. Non-goals for v1

19×19 board, challenge creation/automatch, chat UI, AI review, score estimation, multi-board, Windows/macOS packaging, projector keystone correction (we warp in software instead).
