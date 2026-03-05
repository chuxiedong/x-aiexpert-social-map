# mather-code-skill Iteration Log (2026-03-01)

## Scope
- Project: x-ai-experts-viz
- Objective: unify interaction semantics between circle map and classic 3D map; improve first-screen overview stability.

## Changes
1. Enhanced depth-sensitive zoom in circle layers map:
- File: /Users/somalia/Desktop/x-ai-experts-viz/data/circle_layers.html
- Added front-view parallax + explode compensation so zoom increases perceived distance between nodes.

2. Aligned circle-map gesture model with 3D controls:
- File: /Users/somalia/Desktop/x-ai-experts-viz/data/circle_layers.html
- Added `Shift + left drag` pan fallback (same semantic as orbit pan).
- Improved two-finger pinch to support simultaneous zoom + pan.

3. Fixed classic 3D default camera to wide overview:
- File: /Users/somalia/Desktop/x-ai-experts-viz/index_pre_1to1_latest_backup.html
- Added orbit-control damping and distance bounds.
- Set initial camera farther away (`z=1750`) and increased `zoomToFit` duration for stable panorama-on-load.

## Verification
- Static validation: JS/HTML syntax intact after patching (no parse errors in edited sections).
- Behavior expectation:
  - Circle map now visually separates nodes more when zooming, even near front view.
  - Circle map supports rotate/pan/zoom interaction parity with 3D page.
  - Classic 3D opens in a global view rather than over-zoomed state.

## Remaining risk
- Runtime visual behavior still depends on real browser render context (touch device + desktop trackpad should be smoke-tested).
