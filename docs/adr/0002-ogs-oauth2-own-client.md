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
