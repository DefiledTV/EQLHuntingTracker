# EQL Hunting Log - Changelog

**Versioning (from v0.2.1 on):** `v0.` means beta. `v0.2` is the second major
beta release. `v0.2.1` is that major beta with a minor revision. Entries below
0.2.1 kept their original 1.x / 2.x labels from before this convention
(read 2.x as 0.2.x, 1.x as 0.1.x).

## 0.2.3 - Quests tab, wiki links, OBS parity, feature list
- Kill Log times are now AM/PM hours and minutes; drill-in popups show
  Month - Day - Time (e.g. "Jul - 14 - 10:05 PM").
- Quests moved off the Loot dashboard (and off the main board) into their
  own Quests dashboard/tab; remaining columns recenter on every view.
- Wiki links: mob names in kill drill-ins and item names across the Kill
  Log, Tracked Drops and Kills, and Drop Rates link to eqlwiki.com pages
  ("+N" suffixes are ignored when linking). Link audit against the live
  wiki (48 mobs verifiable from here): 42% of mobs miss by name - every
  miss is capitalization only (the wiki hosts "A Shin Ghoul Knight" where
  the log says "a shin ghoul knight"), and a miss lands on the wiki's own
  search page for that title. Under the 50% bar, so the feature ships.
  Top 10 misses by your kill volume: a shin ghoul knight (80), a vis
  ghoul knight (63), a greater skeleton (35), a kor ghoul wizard (26),
  a froglok shin knight (21), a deadly black widow (18), a dread bone
  (14), a tsu ghoul wizard (10), a cracked skeleton (9), a shin ghoul
  warrior (8). Items verified overwhelmingly clean, including the
  backtick pages (Torn Page of Magi`kot pg. 3).
- Edit Windows: hiding every panel in a column now collapses the column
  and recenters the rest; reopening restores the layout.
- New Features button on the app: the full feature list in a read-only
  window; FEATURES.md ships in the kit. Troubleshooting updated for the
  Archive/Truncate buttons and the Quests dashboard.
- OBS overlay (/overlay) rebuilt to match the Game Overlay: kills,
  kills/hr, XP/hr, coin, DPS, session, TO LVL, TO 50, zone, and both
  combat sections with SOURCE / DMG / ACC / MAX / DPS columns, hit% and
  avoided%, and +/- collapses.
- App buttons reorganized: Features, Archive, Truncate, and Release and
  Troubleshooting on their own row; Quest Dashboard button added.
- New GITHUB_GUIDE.md: best practices for publishing and releasing.

## 0.2.2 - Log lifecycle, leveling ETAs, playtime
- New app buttons: **Archive** zips the current log into a "Log Archive"
  folder next to the log (name + date stamp), empties the log, and resumes
  tracking fresh. **Truncate** pops a window with a dropdown of channels
  found in your log (General, General1, General2, NewPlayers, ...) plus
  "All channels", offers a backup zip first, then strips those chat lines
  and repairs the read position so nothing double-counts. Both are best
  done with the game closed or after /log off, and both begin a new session
  (same as Stop then Start). All drop, kill, and combat history is
  preserved in the app's data files either way.
- Loot audit of the provided log: all 245 loot lines - including
  "Serrated Bone Dirk +1", "Flowing Black Silk Sash", and its +1 variant -
  parse and credit correctly, mob-attributed via the "from <mob>'s corpse"
  form. If an item seems missing on the dashboard, remember Drop Rates
  defaults to your 5 most recent hunts: search the item or click the mob
  for its full summary. Rebuild Data re-derives everything if in doubt.
- Session time cell now toggles session <-> all time. All-time playtime is
  measured from log activity with AFK gaps over 5 minutes excluded
  (your log: 55h 22m active across a 146h span).
- Time to level and Time to 50: estimated from your XP rate this session,
  falling back to your measured time between recent level-ups when idle.
  Uses the most recent "Welcome to level N!" line (multiclass-aware: the
  latest ding is treated as your active class). Shown on the dashboard
  (with % into level) and on the Game Overlay (TO LVL / TO 50). Validated
  against the full log: level 33 at 74.4%, ~1h 10m to 34 at 21.8%/hr.
- Level-ups, XP-into-level, and playtime persist in the lifetime file; if
  your data predates 0.2.2, estimates appear after your next ding or a
  Rebuild Data.

## 0.2.1 - Overlay rebuilt, release notes, beta versioning
- Game Overlay reverted to the stable v2.0 (0.2.0) construction and rebuilt
  cleanly. Root cause of the stuck-top-left/no-data overlay: a construction
  error in 0.2.0.1 aborted setup before the window was positioned or
  registered. The overlay now positions itself first, binds dragging to
  every element, and shows an error dialog instead of failing silently.
- Re-added on the stable base: DPS in the top bar; +/- collapse toggles for
  Current and Last Combat; hit% and avoided% between damage and DPS for both
  combats; per-source columns SOURCE / DMG / ACC / MAX / DPS, where MAX is
  the largest single hit for that skill.
- New app button "Release and Troubleshooting": a read-only, scrollable
  window with the pinned security note, troubleshooting guide, and the full
  version history.
- New INSTALLATION.md covering GitHub, direct .pyw, source, self-built exe,
  and Google Drive package setups.
- Version convention switched to v0.x beta labeling (see top of file).

## 2.1.1 - Revert overlay focus change
- Reverted v2.1 item 9 (WS_EX_NOACTIVATE on the Game Overlay): it broke
  clicking/dragging the overlay on real hardware. The overlay behaves like
  any normal window again - clicking it focuses it briefly; click back into
  the game to continue. Click-through mode is unaffected and remains the
  best option for keeping the overlay over your play area.

## 2.1 - Quests lifecycle, multi-dashboards, overlay overhaul
- Quests: closing (X) now asks for confirmation and moves the NPC to a new
  "Closed Quests" panel (starts collapsed); a checkmark finishes a quest into
  "Finished Quests" below it; both panels have a return arrow that puts the
  quest back in Possible Quests. [Bracketed] words in quest dialogue render
  light blue. All states persist.
- Three dashboards, launched from the app: All Dashboards (everything, with
  an "Edit Windows" button beside the centered title that toggles any panel's
  visibility), Combat Dashboard (combat panels only), and Loot Dashboard
  (Tracked, Drop Rates, and the three quest panels - quests in their own
  column). Combat and Loot views suppress word wrapping.
- Tracked Drops and Kills: no longer limited to recent hunts - shows the
  first 5 tracked mobs with 5 / 10 / 20 limit buttons under the title
  (search still reaches everything).
- Source names never wrap; parenthetical tags merge and drop below the name
  - "Slash (melee) (Crit)" displays as Slash with "(Melee Crit)" beneath.
- Kill drill-ins end with a labeled Loot section.
- Clicking a mob name in Tracked or Drop Rates opens a summary popup with a
  Current Session section and an Overall section (kills + full item table).
- Game Overlay: DPS added to the top bar; hit% and avoided% sit between
  damage and DPS for both combats; per-source rows are now columns -
  SOURCE / DMG / ACC / MAX / DPS; +/- toggles collapse Current or Last
  Combat individually; clicking or dragging the overlay no longer steals
  focus from the game (WS_EX_NOACTIVATE), so control stays where your
  mouse was.
- New app button: "Gear & Leveling Planning" (placeholder - "You have to
  wait for this feature").

### Overlay latency analysis (v2.1, per request)
Measured causes, largest first:
1. snapshot() - building the full data payload on the UI thread every
   second (~30-40 ms on a 600-kill session, grows with kill count). Shared
   with the dashboard; the unavoidable baseline.
2. Tk label updates - every .config() on an always-on-top, alpha-blended,
   frameless window forces geometry recomputation, even when the text is
   identical. FIXED: all overlay labels now cache their last value and skip
   updates when nothing changed - an idle overlay does zero layout work.
3. Resize thrash - multi-line combat text changing length re-sizes the
   window each tick. Mitigated by fixed-width column formatting; collapsing
   a section (+/-) skips building its text entirely.
4. Compositor cost of the translucent topmost window - minor.
Net effect: idle ticks are near-free; in combat, cost is dominated by the
shared snapshot build.

## 2.0.1 - GitHub packaging (no app changes)
- Self-extracting installer (pure Python, AV-friendly): one file that unpacks
  the app, README, and changelog, then offers to launch.
- Repo kit: README.md and .gitignore (keeps personal stats/history/config
  out of version control).

## 2.0 — Major revision: outcomes, crit panels, quests, 7-wide
- Combat outcome tracking everywhere: misses, dodges, parries, blocks,
  ripostes, absorbs (magical skin + rune points), riposte hits landed (count
  and damage), damage-shield damage dealt/taken, and interrupted casts (yours
  and ones you caused) — shown as an offense/defense table in the new
  "Other Stats" panel, as compact lines under the Damage panels, inside
  Current/Last Combat, and on the Game Overlay.
- Dashboard is now seven columns: 1 Current/Last Combat · 2 Kill Log ·
  3 Damage/Healing · 4 Critical Damage/Critical Healing · 5 Pet Damage +
  Other Stats · 6 Tracked/Drop Rates · 7 Possible Quests. Critical rows moved
  out of the normal Damage/Healing panels into their own; pet crits stay
  merged in the Pet window. Heal crits now parsed ("(Critical)" suffix).
- Last Combat shows its zone above the mob names on the dashboard.
- Quest system: hails are tracked; any NPC whose chat contains [bracketed]
  words is recorded as a possible quest giver with name + zone in the new
  Possible Quests column. Clicking a name shows all captured dialogue and
  follow-ups; the X dismisses an NPC permanently. Everything persists to
  eql_quests.json with no duplicate NPCs or text.
- Pet detection rebuilt to the real grammar: "tells you", "told you", and
  "says" variants all count when the pet addresses you as Master.
- Drop Rates and Tracked Drops show each mob's zone under its name (zones
  stamp on kill; run Rebuild Data once to backfill zones everywhere).
- Both drop panels: click the "Item" header to collapse just that mob's
  item list (remembered per mob).

## 1.8.1 — Versioned file labeling
- The tracker app, the changelog, and the Rebuild Data backup zip now carry
  the version number in their filenames (eql_tracker_app_vX.Y.pyw,
  eql_changelog_vX.Y.md, eql_data_backup_vX.Y_<timestamp>.zip).
- In-app version strings single-sourced from the engine VERSION constant.

## 1.8 — Pets, zones, and this changelog
- Pet detection: any entity whose tell contains ", Master." is registered as
  your pet for the session.
- New "Pet Damage" panel, third in column three: pet damage dealt (by attack
  type) and damage the pet received, with dealt/taken totals.
- Pet damage merges into Current Combat and Last Combat as a row labeled
  "Pet", and counts toward encounter/kill damage totals and DPS.
- Kill Log drill-in shows the Pet row in your damage table, a "Their damage
  to your pet" table, and the zone name below the mob's name.
- Zone tracking via "You have entered <zone>." — every kill is stamped with
  its zone; the Game Overlay shows the current zone above CURRENT COMBAT.
- This changelog created; versioning method adopted going forward.

## 1.7.1 — Data reconciliation (service, no code change)
- Merged two divergent stats generations + kill history by rebuilding one
  authoritative dataset from the full log with the current parser; verified
  both old generations were fully contained (no double counting). Kept the
  user's native-timezone kill history verbatim.

## 1.7 — Overlay elements + Rebuild Data
- Game Overlay rebuilt around: session kills, kills/hr, XP/hr, session coin,
  session time, and dashboard-style Current Combat and Last Combat sections.
- "Rebuild Data" button: archives eql_lifetime_stats.json and
  eql_kill_history.jsonl to a timestamped zip, then re-scans the entire log
  from scratch (tracked mobs preserved).
- Version labeling introduced (v1.7 shown in app, dashboard, and file).

## 1.6.3 — Game Overlay introduced
- Always-on-top, frameless, draggable in-game stats window with optional
  Windows click-through; position remembered; right-click closes.

## 1.6.2 — Layout corrected to four true columns
- Column 1: Current/Last Combat · Column 2: Kill Log (full height) ·
  Column 3: Damage/Healing · Column 4: Tracked/Drop Rates.

## 1.6.1 — Tracked loot collapsible
- In Tracked Drops and Kills, clicking a mob's name folds/unfolds its loot
  table; per-mob state remembered by the browser.

## 1.6 — Full kill history + collapse everywhere
- Kill history moved to append-only eql_kill_history.jsonl with full combat
  detail per kill; no cap. One-time backfill rebuilds history from the
  already-consumed portion of the log without double-counting lifetime stats.
- Overall Kill Log covers all recorded kills, searchable, with click-for-
  detail in both session and overall modes.
- Every panel (Current/Last Combat, Kill Log, Damage, Healing, Tracked,
  Drop Rates) collapsible with per-panel memory.

## 1.5 — Layout, mob tracking, crit split
- Three-wide dashboard layout (superseded in 1.6.2).
- Tracking moved from per-item to per-mob (checkbox next to the mob in Drop
  Rates); Tracked panel shows the whole mob's drops.
- Collapsible Drop Rates panel; Last Combat resets on a new session.
- Kill Log session ⇄ overall toggle (200-kill store; expanded in 1.6).
- Critical hits split into their own "(Crit)" rows across all damage tables.

## 1.4 — Engine v2: named mobs, encounters, tracking, latency
- Parser rebuilt: named mobs (no article), group kills ("has been slain by"),
  corpse coin, party XP, riposte/crit suffixes, thorns/damage shields,
  incoming DoTs and spells. Recovered ~200 missing kills on the test log.
- Current/Last Fight became encounter-based Current/Last Combat: overlapping
  fights group into one combat, AoE damage aggregates correctly.
- XP stat: session ⇄ per-hour (lifetime XP removed).
- Deaths: killing-blow capture, session ⇄ all-time toggle, persisted reports.
- Tracked Drops and Kills panel (session ⇄ overall) with drop-rate checkboxes.
- Log latency line: file size, backlog parse time, batch/snapshot/fetch ms,
  truncation warnings.
- Damage and Healing panels: session ⇄ total toggles (lifetime aggregates).
- Kill Log names clickable: full per-kill damage dealt and taken breakdown.

## 1.3 — Readability and stat toggles
- Numbers with 6+ digits shown in scientific notation.
- Last Fight panel mirroring the skill tables, including per-fight healing.
- Panels renamed "Total Damage/Healing by Skill / Spell" (superseded in 1.4).
- Deaths cell clickable: death report with killer and everything engaged.
- XP and Coin cells toggle session ⇄ lifetime (persisted totals).

## 1.2 — Dashboard search and healing
- Kill Log capped to the last 20 with a mob-name search across the session.
- Drop Rates: item/mob search across the lifetime database; default view
  limited to the 5 most recently hunted mobs.
- Healing by Skill / Spell panel with per-source HPS; HPS in the stat bar.

## 1.1 — Standalone app
- Tkinter control window: Browse for the log once, remembered and
  auto-resumed every launch; live status, mini stats, dashboard/overlay
  buttons, start/stop; port auto-fallback; crash log + headless fallback.
- 1.1.1 (support): PyInstaller not on PATH — use `python -m PyInstaller`.
- 1.1.2 (support): install location guidance; data files live next to the app.

## 1.0 — Initial live tracker
- Real-time log tailing with a localhost dashboard: session stats, live
  current-fight DPS, kill log with per-kill fight time/damage/DPS/loot,
  damage by skill/spell, per-mob drop rates.
- Persistent lifetime drop database with per-file read offsets (restart-safe,
  never double counts); OBS-ready transparent overlay page.
