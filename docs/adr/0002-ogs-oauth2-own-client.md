# 0002 — OGS via official OAuth2 + PKCE and a hand-written WebSocket client

## Context

Options considered for playing on online-go.com:

1. **Browser automation** (goban_irl's pyautogui approach): fast to build, no API
   credentials, but fragile against UI changes and needs a visible browser.
2. **`ogsapi`** (third-party Python wrapper): WIP, pins old socket.io versions,
   tracks an API generation OGS has since replaced.
3. **Official OAuth2 + the documented raw WebSocket JSON protocol** (goban's
   `protocol` namespace, Apache-2.0 reference implementation):
   self-service app registration, PKCE for public clients, no dependency on a
   third-party wrapper.
4. **`gtp2ogs`**: officially supported, but it exists to connect *bot* accounts.
   Playing human games through it misrepresents the account to OGS.

## Decision

Option 3. Register a **public** OAuth2 application with a loopback redirect URI,
store the refresh token in the OS keyring, and implement only the ~15 protocol
messages v1 needs. No browser automation, no `ogsapi`, no `gtp2ogs`.

## Consequences

- OGS protocol changes are ours to track; protocol models stay isolated in one
  module and recorded fixtures catch drift.
- We own the auth UX (browser + local callback listener).
- v1 can only *attach* to an existing game id; challenge creation is deferred.

## Spike outcome (S1, 2026-11-15)

Confirmed end to end against the live server with a registered public client:

1. `GET /api/v1/ui/config` **without** a token returns a guest identity and a
   guest `user_jwt`. The same endpoint **with** `Authorization: Bearer
   <access_token>` returns the real user (`{id, username, ...}`) plus that user's
   `user_jwt`. So the REST→JWT step is real, not assumed.
2. PKCE with a 64-byte verifier and `S256` challenge works; the loopback redirect
   `http://127.0.0.1:8765/callback` **is accepted** by OGS for a public client,
   so the https code-paste fallback is not needed.
3. Token exchange needs only `grant_type`, `code`, `redirect_uri`, `client_id`
   and `code_verifier` — no `client_secret`. Response grants
   `scope="read write"`, `expires_in=2592000` (30 days) and a refresh token.
4. `wss://online-go.com` (root path, no `/socket.io/`) accepts
   `["authenticate", {jwt, client, client_version, device_id, user_agent,
   language}]` and replies `[1, {id, username}]`; a failure replies
   `[1, null, {code, message}]`. Message ids are echoed, confirming the request
   correlation model in the docs.

Reproduction: `uv run python experiments/ogs_handshake.py` (needs `OGS_CLIENT_ID`),
or `--guest` for the anonymous path. Tokens are never printed or stored.
