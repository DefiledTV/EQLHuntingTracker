# EQL Hunting Log — Feature List (v0.2.3)

## Dashboards
- Four dashboards: All (everything), Combat, Loot, and Quests — switchable
  from the app or the links under the title.
- Edit Windows button (All view): show/hide any panel; emptied columns
  collapse and the rest recenter automatically.
- Every panel collapsible with per-panel memory; Combat and Loot views
  never word-wrap; source names never wrap anywhere, with parenthetical
  tags merged below the name ("Slash" over "(Melee Crit)").
- Stat bar: session kills, deaths (session/all + death reports with
  killing blow), kills/hr, overall DPS, HPS, XP (session/per-hour),
  coin (session/total), time (session/all-time), time to next level with
  % into level, and time to 50.

## Combat tracking
- Encounter-based Current and Last Combat: overlapping fights merge, AoE
  attributed correctly; zone shown on Last Combat; hit% and avoided% in
  the meta line; per-encounter outcome stats line.
- Damage and Healing by skill/spell with session/total toggles; critical
  hits and heals split into their own panels.
- Outcome tracking both directions: miss, dodge, parry, block, riposte
  (plus riposte hits landed and their damage), magical-skin absorbs, rune
  absorption, damage-shield damage dealt/taken, interrupted casts (yours
  and ones you caused) — summarized in the Other Stats table.
- Pet detection from "Master" tells (tells you / told you / says); pet
  damage panel with damage taken; pet merged as "Pet" into encounters and
  kill drill-ins.

## Kill Log
- Full lifetime kill history with per-kill drill-ins: your damage table,
  their damage to you, damage to your pet, zone under the mob name, and a
  labeled Loot section; session and overall modes, searchable.
- Times in AM/PM (hours and minutes); drill-ins show Month - Day - Time.
- Mob names in drill-ins and item names everywhere link to eqlwiki.com.

## Loot
- Lifetime drop rates per mob with session columns, zone under the mob
  name, per-mob item collapse (click the Item header), and mob summary
  popups (session + overall) from any mob name.
- Tracked Drops and Kills with 5/10/20 limit buttons and search.

## Quests
- Hail tracking; NPCs with [bracketed] dialogue become Possible Quests
  with name and zone; dialogue viewer with follow-ups, bracketed words in
  light blue; finish (checkmark), close (X, with confirmation), and
  return arrows; Closed and Finished panels; everything persists.

## Overlays
- Game Overlay (always-on-top window): kills, kills/hr, XP/hr, coin, DPS,
  session time, to-level, to-50, zone, and Current/Last Combat with
  SOURCE / DMG / ACC / MAX / DPS columns; drag anywhere, right-click to
  close, per-section +/- collapse, optional click-through, position and
  states remembered.
- OBS overlay (/overlay browser source): same elements as the Game
  Overlay, transparent, with its own +/- collapses.

## Data safety
- Per-log read offsets: restart-safe, never double counts.
- Append-only kill history with full combat detail; one-time backfill.
- Rebuild Data: archives your data files to a versioned zip and re-derives
  everything from the log.
- Archive: zips the log to a "Log Archive" folder (name + date stamp) and
  starts it fresh. Truncate: strips selected channel chat (with optional
  backup zip) and repairs the read position.
- Playtime measured from log activity with AFK gaps excluded; level-ups
  and XP progress persist.

## App
- Single file, no dependencies, everything local (see the pinned security
  note under Release and Troubleshooting).
- Versioned releases, changelog, self-extracting installer, GitHub kit.
