#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "owner_status.json"
JOURNAL = DATA / "owner_journal.md"


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def main() -> int:
    if ROOT.name != "x-ai-experts-viz":
        raise RuntimeError(f"scope guard failed: expected x-ai-experts-viz, got {ROOT.name}")

    now = dt.datetime.utcnow().isoformat() + "Z"
    DATA.mkdir(parents=True, exist_ok=True)

    pre_code, pre_log = run(["bash", str(ROOT / "scripts" / "ensure_runtime.sh"), "8765"])
    hb_code, hb_log = run(["python3", str(ROOT / "scripts" / "heartbeat.py")])

    heartbeat = load_json(DATA / "heartbeat_status.json", {})
    profiles = load_json(DATA / "profiles.json", {"items": []})
    top10 = load_json(DATA / "daily_briefing.json", {"items": []})
    iterations = load_json(DATA / "iteration_log.json", [])
    experts = profiles.get("items", []) if isinstance(profiles, dict) else []
    buddies_covered = sum(1 for x in experts if x.get("best_buddies"))

    changed = []
    for pat in ("*.html", "data/*.json", "scripts/*.py", "scripts/*.sh", "assets/*.js"):
        for f in ROOT.glob(pat):
            try:
                ts = dt.datetime.utcfromtimestamp(f.stat().st_mtime).isoformat() + "Z"
                changed.append((f, ts, f.stat().st_mtime))
            except Exception:
                continue
    changed.sort(key=lambda x: x[2], reverse=True)
    latest_files = [
        {"path": str(p.relative_to(ROOT)), "updated_at": ts}
        for p, ts, _ in changed[:12]
    ]

    payload = {
        "generated_at": now,
        "owner_mode": "autonomous",
        "scope": {
            "project": "x-ai-experts-viz",
            "boundary": str(ROOT),
            "mission": "X experts influence intelligence + commercialization",
        },
        "runtime": {
            "preflight_result": "ok" if pre_code == 0 else "warn",
            "heartbeat_result": "ok" if hb_code == 0 else "warn",
        },
        "health": {
            "status": heartbeat.get("status", "unknown"),
            "missing_count": len(heartbeat.get("missing", []) or []),
            "checks_count": len(heartbeat.get("checks", []) or []),
            "last_heartbeat": heartbeat.get("generated_at", ""),
        },
        "business": {
            "profiles_count": len(profiles.get("items", []) or []),
            "top10_count": len(top10.get("items", []) or []),
            "iteration_count": len(iterations) if isinstance(iterations, list) else 0,
            "buddies_covered_count": buddies_covered,
            "public_pages": [
                "/index.html",
                "/commercial.html",
                "/contact.html",
                "/ops.html",
                "/progress.html",
                "/owner.html",
                "/daily_progress.html",
                "/poster.html",
            ],
            "latest_changed_files": latest_files,
        },
        "logs": {
            "preflight_tail": pre_log[-1200:],
            "heartbeat_tail": hb_log[-1200:],
        },
        "next_actions": [
            "improve X expert profile depth and summary quality",
            "raise conversion from homepage CTA to contact lead capture",
            "optimize circle-layer onboarding and interaction clarity",
            "expand Top10/custom poster templates for brand campaigns",
        ],
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    line = (
        f"- {now} | health={payload['health']['status']} | profiles={payload['business']['profiles_count']} "
        f"| top10={payload['business']['top10_count']} | iterations={payload['business']['iteration_count']}"
    )
    if JOURNAL.exists():
        old = JOURNAL.read_text(encoding="utf-8")
    else:
        old = "# Owner Iteration Journal\n\n"
    JOURNAL.write_text(old + line + "\n", encoding="utf-8")

    print(json.dumps({"ok": True, "owner_status": str(OUT), "journal": str(JOURNAL)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
