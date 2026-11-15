# OGS messages used by goban_cast v1

Wire format:

- client to server: `[command, data, id?]`
- server to client: `[event, data]` or `[id, data | {code, message}]`

## Outbound

| Command | Payload | Notes |
| --- | --- | --- |
| `authenticate` | `{jwt, client, client_version, device_id, user_agent}` | `jwt` is `user_jwt` from `GET /api/v1/ui/config` |
| `net/ping` | `{client, drift, latency, ...}` | every 10 s; keeps the socket alive and measures clock drift |
| `game/connect` | `{game_id, chat}` | subscribe to a game's events |
| `game/disconnect` | `{game_id}` | on leaving the game screen |
| `game/move` | `{game_id, move}` | move string; pass and resign are encoded as moves |
| `game/undo/request` | `{game_id, move_number}` | current move number |
| `game/undo/accept` | `{game_id, move_number}` | |
| `game/undo/cancel` | `{game_id}` | |
| `game/chat` | `{game_id, type, message}` | v1: minimal, no chat UI |

## Inbound

| Event | Payload | Use |
| --- | --- | --- |
| `net/pong` | `{client, drift, latency, ...}` | clock correction |
| `game/:id/gamedata` | engine config + game metadata | initial board state, players, clocks, rules |
| `game/:id/move` | `{game_id, move_number, move}` | the move to apply or project |
| `game/:id/clock` | clock state | overlay clocks |
| `game/:id/phase` | `"play" \| "stone removal" \| "finished"` | state machine transitions |
| `game/:id/error` | string | surface to the user, do not retry blindly |
| `game/:id/undo_requested` | undo request | prompt the user |
| `game/:id/undo_accepted` | undo acceptance | roll the board back |
| `game/:id/undo_canceled` | move number | clear the prompt |

## Not in v1

Challenge creation, automatch, seekgraph, chat rendering, AI review, torn-down
reconnect replay beyond a full `game/connect` resync.
