# mather-code-skill iteration: runtime + quality hardening (2026-03-01)

## Goal
Turn project checks into enforceable gates before publish/startup.

## Changes
1. `scripts/validate_data_integrity.py`
- Added stronger checks:
  - top300/profiles/daily_briefing handle uniqueness.
  - daily_insights latest_share text must exist for each creator.
  - blocked templated generic share prefix.
  - blocked duplicate latest_share_zh across creators.
  - `has_today_tweet=true` requires `today_hottest_tweet_text`.
  - graph links must resolve to known node id/handle.

2. `scripts/preflight_status.sh`
- Added automatic invocation of integrity validator and surfaced pass/fail in preflight output.

3. `scripts/ensure_runtime.sh`
- Fixed false-positive runtime check: now requires both `index.html` and `progress.html` reachable.
- Added stale-port cleanup (`lsof` + kill) before starting fresh server.
- Ensured web server always starts in project root directory.

4. `scripts/mather_optimize.sh` (new)
- One-command workflow:
  - ensure runtime
  - validate integrity
  - print preflight summary

## Verification
Executed:
- `bash ./scripts/mather_optimize.sh 8765`

Result:
- web reachable: OK
- progress page reachable: OK
- data integrity validation: OK
- autopilot pid alive: OK

