# Architecture decision records

Short records of choices that were expensive to make and would be expensive to re-litigate.

| ID | Title | Status |
| --- | --- | --- |
| [0001](0001-gpl-license.md) | GPL-3.0 because the board detector is vendored from goban_irl | accepted |
| [0002](0002-ogs-oauth2-own-client.md) | OGS via official OAuth2 + PKCE and a hand-written WebSocket JSON client | accepted |
| [0003](0003-projector-feedback.md) | Avoid projecting at stone centers and time-multiplex capture | accepted |
| [0004](0004-hardware-agnostic-calibration.md) | Hardware-agnostic behaviour enforced by a calibration wizard | accepted |
| [0005](0005-pyside6-ui.md) | PySide6 for the UI and projector window | accepted |
| [0006](0006-v1-nine-by-nine.md) | v1 is 9×9 only, grids stay parameterized | accepted |
| [0007](0007-coordinate-spaces.md) | One geometry module owns four named coordinate spaces | accepted |
