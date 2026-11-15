---
name: OGS protocol
description: Use when implementing or debugging OAuth2 login, the OGS WebSocket messages, game state sync, clocks, undo, or the MockOGS replay harness.
---

# OGS protocol

Read `references/messages.md` before touching `src/goban_cast/net/ogs/`.

## Order of operations

1. OAuth2 + PKCE in the system browser; loopback redirect `http://127.0.0.1:8765/callback`.
2. Exchange the code at `POST /oauth2/token/`; store the refresh token in the OS
   keyring (`keyring` package), never on disk.
3. `GET /api/v1/ui/config` with the bearer token; take `user_jwt`.
4. WebSocket `authenticate` with that JWT, plus `client`, `client_version`,
   `device_id`, `user_agent`.
5. `net/ping` every 10 s (`net/pong` carries clock drift; use it for clocks).
6. `game/connect {game_id, chat}` then drive everything from `game/:id/*` events.

## Hard rules

- Tokens never appear in logs, fixtures, exceptions, or config. Sanitize any
  recorded session (usernames, ids, JWTs) before committing it.
- Protocol names and payload models live in one module; no string literals for
  event names anywhere else.
- Tests use `MockOGS` only. CI has no network and no account.
- One connection, exponential backoff, stable `device_id`.

## When the protocol seems wrong

Check the generated docs at `docs.online-go.com/goban/modules/protocol.html` and
the `goban` sources (`src/engine/protocol/*.ts`). If OGS behaviour differs from
the docs, record a sanitized capture, write an ADR, and adapt the models.
