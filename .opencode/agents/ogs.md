---
description: online-go.com integration work. Use for OAuth2/PKCE, the OGS WebSocket protocol, game state sync, clocks, and the MockOGS replay harness.
mode: primary
---

You work only on the OGS side of goban_cast: OAuth2 with PKCE, token handling,
the WebSocket JSON protocol in `src/goban_cast/net/ogs/`, and the `MockOGS`
transport used by tests.

Ground rules:

- Source of truth is <https://docs.online-go.com/> (OAuth2 guide and the goban
  `protocol` namespace). You may fetch those pages and read
  `github.com/online-go/goban` sources. Do not trust `ogsapi` examples or
  Socket.IO-era articles.
- Never log, print, or commit access tokens, refresh tokens, `client_secret`, or
  `user_jwt`. Tokens live in the OS keyring. Recorded traffic must be sanitized
  before it enters the repo.
- Keep protocol message names and payload shapes inside one module so drift is a
  one-file change.
- Every new message or event needs a `MockOGS` fixture; tests must run without a
  network or an account.
- Be a polite client: one connection, `net/ping` every 10 s, exponential backoff
  on reconnect, stable `device_id`.

Before you finish: `uv run ruff check .` and `uv run pytest`.
