---
description: Run headless detection over recorded fixtures and report per-fixture diffs
---

Run the vision fixture suite and report differences between detected and expected
board states:

!`uv run pytest -m vision -q`

For each failing fixture, report: the setup name, the intersection that differs,
the expected stone, and the detected value. If no fixtures exist yet, say so and
point at the `calibration` skill instead of inventing results.
