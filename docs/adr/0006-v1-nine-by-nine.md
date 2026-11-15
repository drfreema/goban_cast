# 0006 — v1 is 9×9 only, grids stay parameterized

## Context

A 9×9 board is the fastest path to a working end-to-end loop: fewer
intersections, more pixels per intersection at 1 m, quicker games for testing,
and a smaller rules test matrix. 19×19 is the eventual target.

## Decision

Ship v1 for 9×9 only, but never hardcode 9: grid generation, rules, SGF export,
and overlay geometry take a board size. 13×13 and 19×19 must be configuration, not
a refactor.

## Consequences

- Test fixtures only need 9×9 in v1, keeping the fixture suite small.
- Coordinate labels and star points are size-dependent and must be derived, not
  tabulated per size.
- Any code path that says "9" outside a test needs a reason.
