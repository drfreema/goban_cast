"""Spike S1: prove the OGS auth and WebSocket handshake before building the client.

Two modes:

    uv run python experiments/ogs_handshake.py --guest
        Fetch an anonymous JWT from /api/v1/ui/config, authenticate over the
        WebSocket, and print the identity OGS returns. No account needed.

    OGS_CLIENT_ID=... uv run python experiments/ogs_handshake.py
        Full OAuth2 + PKCE login (loopback redirect), then the same handshake.

Tokens are never printed and are not persisted: the goal is to learn whether the
OAuth access token can be exchanged for a `user_jwt`, and whether that JWT is what
`authenticate` wants. Record the outcome in docs/adr/0002-ogs-oauth2-own-client.md.

This file is a throwaway experiment, not part of the package.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from typing import Any

import httpx
from websockets.sync.client import connect

SITE = "https://online-go.com"
WS_URL = "wss://online-go.com"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"
SCOPE = "read write"
CLIENT_NAME = "goban_cast"
CLIENT_VERSION = "0.1.0-spike"


def ui_config(client: httpx.Client, access_token: str | None = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    response = client.get(f"{SITE}/api/v1/ui/config", headers=headers, timeout=20)
    response.raise_for_status()
    return response.json()


def authenticate(user_jwt: str) -> dict[str, Any]:
    """Connect, authenticate, and return the identity the server reports."""
    payload = {
        "jwt": user_jwt,
        "client": CLIENT_NAME,
        "client_version": CLIENT_VERSION,
        "device_id": "spike-" + hashlib.sha256(b"goban_cast-spike").hexdigest()[:16],
        "user_agent": "goban_cast spike",
        "language": "en",
    }
    with connect(WS_URL, open_timeout=20, close_timeout=5) as socket:
        socket.send(json.dumps(["authenticate", payload, 1]))
        while True:
            raw = socket.recv(timeout=20)
            message = json.loads(raw)
            if isinstance(message, list) and message and message[0] == 1:
                if len(message) >= 3 and message[2]:
                    raise RuntimeError(f"authenticate failed: {message[2]}")
                return message[1] or {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    code: str | None = None
    state: str | None = None
    error: str | None = None
    redirect_path: str = "/callback"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != type(self).redirect_path:
            self.send_response(404)
            self.end_headers()
            return
        query = urllib.parse.parse_qs(parsed.query)
        type(self).code = query.get("code", [None])[0]
        type(self).state = query.get("state", [None])[0]
        type(self).error = query.get("error_description", query.get("error", [None]))[0]
        body = b"<h2>goban_cast</h2><p>You can close this tab and return to the terminal.</p>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:  # keep the spike output readable
        return


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def oauth_login(client_id: str, redirect_uri: str) -> dict[str, Any]:
    parsed_redirect = urllib.parse.urlparse(redirect_uri)
    _CallbackHandler.redirect_path = parsed_redirect.path
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)
    authorize = f"{SITE}/oauth2/authorize/?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SCOPE,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )

    server = http.server.HTTPServer((parsed_redirect.hostname or "127.0.0.1", parsed_redirect.port or 8765), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print("Open this URL and authorize goban_cast:\n\n  " + authorize + "\n", flush=True)
    webbrowser.open(authorize)
    thread.join(timeout=300)
    server.server_close()

    if _CallbackHandler.error:
        raise RuntimeError(f"authorization denied: {_CallbackHandler.error}")
    if not _CallbackHandler.code:
        raise RuntimeError("no authorization code received (timed out?)")
    if _CallbackHandler.state != state:
        raise RuntimeError("state mismatch: possible CSRF, aborting")

    with httpx.Client() as client:
        response = client.post(
            f"{SITE}/oauth2/token/",
            data={
                "grant_type": "authorization_code",
                "code": _CallbackHandler.code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "code_verifier": verifier,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"token exchange failed: {response.status_code} {response.text[:300]}")
        tokens = response.json()

    print("Token exchange OK. Access token received, refresh token received:")
    print(f"  scope={tokens.get('scope')} expires_in={tokens.get('expires_in')}")
    print(f"  refresh_token present: {bool(tokens.get('refresh_token'))}")
    return tokens


def run_guest() -> int:
    with httpx.Client() as client:
        config = ui_config(client)
        identity_hint = config.get("user", {}).get("username")
        user_jwt = config.get("user_jwt")
    if not user_jwt:
        print("FAIL: ui/config did not return user_jwt")
        return 1
    print(f"guest identity from REST: {identity_hint}")
    identity = authenticate(user_jwt)
    print(f"authenticated over WebSocket as: {identity}")
    print("PASS: guest handshake works; the JWT path is correct for anonymous users.")
    return 0


def run_oauth(client_id: str, redirect_uri: str) -> int:
    tokens = oauth_login(client_id, redirect_uri)
    access_token = tokens.get("access_token")
    if not access_token:
        print("FAIL: no access token")
        return 1

    with httpx.Client() as client:
        config = ui_config(client, access_token)
    user = config.get("user") or {}
    user_jwt = config.get("user_jwt")
    print(f"REST identity with bearer token: {user.get('username')} (id={user.get('id')})")
    if user.get("anonymous"):
        print("FAIL: bearer token was treated as anonymous; scope or client type is wrong")
        return 1
    if not user_jwt:
        print("FAIL: authenticated ui/config did not include user_jwt")
        return 1

    identity = authenticate(user_jwt)
    print(f"authenticated over WebSocket as: {identity}")
    if identity.get("id") != user.get("id"):
        print("FAIL: WebSocket identity does not match the REST identity")
        return 1
    print("PASS: OAuth2 -> user_jwt -> WebSocket authenticate works for a real account.")
    print("Record this in docs/adr/0002-ogs-oauth2-own-client.md.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guest", action="store_true", help="anonymous handshake only")
    parser.add_argument(
        "--client-id",
        default=os.environ.get("OGS_CLIENT_ID"),
        help="OAuth2 client id (or set OGS_CLIENT_ID)",
    )
    parser.add_argument(
        "--redirect",
        default=os.environ.get("OGS_REDIRECT_URI", DEFAULT_REDIRECT_URI),
        help="redirect URI exactly as registered on OGS",
    )
    args = parser.parse_args(argv)

    if args.guest:
        return run_guest()
    if not args.client_id:
        print("Set OGS_CLIENT_ID or pass --client-id for the OAuth flow.", file=sys.stderr)
        return 2
    return run_oauth(args.client_id, args.redirect)


if __name__ == "__main__":
    raise SystemExit(main())
