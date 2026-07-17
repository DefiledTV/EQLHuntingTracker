# EQL Hunting Log

A real-time combat tracker for **EverQuest Legends**. One Python file, no
dependencies. It tails your game log and serves a live dashboard, an OBS
overlay, and an in-game overlay window.

## Features
- Live dashboard (7 columns): current & last combat (encounter-based, AoE
  aware), full kill log with per-kill damage dealt/taken drill-ins, damage &
  healing by skill/spell with critical hits split into their own panels,
  pet damage, combat outcome stats (miss/dodge/parry/block/riposte/absorb,
  damage shields, interrupts), tracked drops with lifetime drop rates,
  and a quest-giver log built from NPC [bracketed] dialogue.
- Lifetime data that never double-counts: per-log read offsets, an
  append-only kill history with full detail, zone stamping, and a one-click
  **Rebuild Data** that archives your old data to a zip and re-scans the log.
- Game overlay: always-on-top, draggable, optional click-through — session
  kills, kills/hr, XP/hr, coin, session time, zone, current & last combat.
- OBS overlay at `/overlay` (transparent browser source).

## Install
1. Install Python 3 (python.org — tick "Add to PATH").
2. Download `eql_tracker_app_v0.2.3.pyw` (or run the installer from Releases).
3. Put it in its own folder (e.g. `C:\Tools\EQLTracker`) and double-click it.
4. Click **Browse...**, pick your `eqlog_<name>_<server>.txt`, and turn on
   `/log` in game. Dashboard opens at http://localhost:8710.

The app remembers your log and resumes automatically every launch. Data files
(`eql_tracker_config.json`, `eql_lifetime_stats.json`,
`eql_kill_history.jsonl`, `eql_quests.json`) live next to the app.

## Optional: single .exe
```
python -m pip install pyinstaller
python -m PyInstaller --onefile --noconsole eql_tracker_app_v0.2.3.pyw
```

See `FEATURES.md` for the full feature list, `GITHUB_GUIDE.md` for publishing, and `INSTALLATION.md` for all setup methods, and `eql_changelog_v0.2.3.md` for full version history.
