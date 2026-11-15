from __future__ import annotations

from goban_cast.app import main


def test_main_returns_zero() -> None:
    assert main([]) == 0


def test_preview_with_game_is_rejected() -> None:
    assert main(["--preview", "living-room", "--game", "12345"]) == 2
