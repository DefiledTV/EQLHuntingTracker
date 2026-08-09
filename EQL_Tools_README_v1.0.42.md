# EQL Tools

A real-time combat tracker for **EverQuest Legends**. It reads your game log
and gives you live DPS, overlays you can stream, a gear planner and a searchable
item database.

This is the **standalone build**: one file, with Python, Tk and the item
database inside it. Nothing to install.

Everything is local: the app binds `127.0.0.1` and makes no outbound calls.

## Run it

1. Put `EQL_Tools_v1.0.42.exe` anywhere you can write to. Your Documents
   folder is fine; avoid `Program Files`.
2. Double-click it.
3. Click **Browse...**, pick your `eqlog_<name>_<server>.txt`, and type
   `/log on` in game.

The dashboard opens at http://localhost:8710. The app remembers your log and
resumes on every launch.

**Windows will warn you the first time.** The build is not code-signed, so
SmartScreen shows *"Windows protected your PC"*. Click **More info** →
**Run anyway**. It only happens once. Signing certificates cost a few hundred
dollars a year, which a free hobby tracker is not going to carry.

**First launch takes a few seconds longer** than later ones — it unpacks
itself and copies the item database out next to the exe. After that it starts
normally.

### Where your data goes

A `Data` folder appears next to the exe on first run. Everything the app
records lives there:

```
Data\eql_tracker.db     your kills, drops, play time, AA purchases
Data\eql_items.db       the item database (shipped with the app)
Data\icons\             item artwork
Data\*.json             reference files you are free to edit by hand
```

Nothing is written anywhere else. No registry keys, no AppData, no installer.
To remove the app completely, delete the exe and that folder.

**To upgrade**, replace the exe and keep the `Data` folder. Your history
carries over.

## Features

### Live tracking — the reason the app exists

Real-time DPS from your combat log, solo and in a group, as the fight happens.
Per-fight and per-encounter breakdowns, your damage by skill, criticals,
misses, avoidance, heals, pets, damage shields, and per-member contribution
when you're grouped.

Click any mob in the kill log and you get **everyone who was in that fight** —
what they hit for and what they healed for, folded away until you open them.

**Everyone's spell damage counts now.** Earlier versions only saw other
players' melee swings, which made casters look like they were barely
contributing — one groupmate's damage went up 29× once their spells were
counted. Direct spells, damage-over-time ticks and damage shields are all read
now, so the group numbers are far closer to the truth than they were.

**Group healing is tracked.** Every heal another player casts is in the log,
and the tracker reads all of it: who healed, with what, how much, how often.
The number to watch is healing *per cast*, not the total — a lifetap fires on
every swing for a handful of points, so raw totals put a melee player above the
person actually keeping you alive. Both are shown, side by side.

One honest limit worth stating up front: **group numbers are a floor, not a
total.** The game's log only records other players' melee swings and named
spell hits, so a member's real output is always at least what you see and often
more. Mobs killed entirely by your group without you engaging never open a
fight at all, so they won't appear in your kill log either. Your own numbers
are complete; everyone else's are the visible portion.

**Only players count.** Mobs and pets both used to slip onto the group roster
- they have the same one-word capitalised names players do. A mob gives itself
away by attacking you, or by a player casting at it; a pet gives itself away by
its Master tell. Both are now retracted from the roster and from any fight they
were already credited on, including other players' pets, which announce
themselves the same way.

**Group instances find your party for you.** The game announces someone joining
a group only rarely, which used to leave the group view looking empty. An
instance holds nobody but your own party, so anyone fighting alongside you in
one is picked up automatically. Say `Danger` in game and the tracker asks
whether you're starting a raid or joining one — it can't form the raid, only
expect eight players instead of six and label the fight accordingly.

**Time to Kill** watches named bosses and estimates how much longer the fight
has left. It's an approximation, and an honest one — it learns from the kills
you actually record, so it sharpens the more you fight something and it will
not pretend to know a boss it has never seen.

It also keeps your **loot history**: which mobs drop what, how often, and how
many of a given item you've laid eyes on. Over time that turns "does this thing
even drop here" into a number.

### Overlays — four of them, two built for streaming

Two pairs. The **Combat Overlay** sits over the game itself: a compact,
always-on-top readout of your live numbers, drawn to stay out of your way. The
**OBS Combat Overlay** is the same thing as a browser source — capture that
window in OBS and everything you see, your viewers see, without exposing your
desktop or the rest of the app.

The **HoT Overlay** and **OBS HoT Overlay** are the same arrangement for heals
over time: one row per active HoT showing who has it, which spell, who cast it,
the seconds left, and a bar that drains as it runs out. Drag the bottom-right
corner to resize it, double-click that corner to snap back to the default size,
and click any column heading to sort (click again to reverse).

**The countdown is an estimate, and it tells you when it is guessing.** The
game logs every tick of a heal over time but never says how long one lasts, so
the tracker learns each spell's duration from how many ticks it actually runs
for — the tick period itself is a measured six seconds. A `?` next to the
number means that spell has not been seen through to the end three times yet,
so a default is standing in. If a HoT keeps ticking past its estimate the timer
extends rather than sitting at zero while heals are still landing.

**Recasting resets the bar.** The tracker reads the cast line, so refreshing a
HoT before it runs out snaps the timer back to full rather than draining the
old one.

**Each session leads with its own average.** Durations are averaged over the
casts seen since the app started and used from the first completed one, with
your stored history as the fallback for a spell not yet seen that day - so a
rank upgrade shows up straight away instead of being outvoted by months of
older casts.

Durations build up as you play, and **Rebuild Data learns them all at once**
from your existing log — a full replay of a 113 MB log takes about a minute and
came back with fourteen spells, from Ethereal Cleansing at 42 seconds down to
Sacred Echo at 12.

Both combat overlays carry the same layout. A **Solo / Group** switch sits at
the top: solo
shows your own fight, group lists your party with each player's damage rate and
opens any of them to their full breakdown. Damage rates get their own row —
this fight, the last fight, and the whole session side by side — with a second
row doing the same for healing. Either row folds away when you don't want it.

Both are yours to arrange. Pick exactly which cells appear and which you don't
care about, set the opacity of each row independently, and drag them wherever
they belong on your layout. Hidden cells close the gap rather than leaving
holes. The combat overlays are deliberately not resizable — that layout is
fixed so the text stays legible at a glance mid-fight. The HoT overlay is
resizable, because a longer list needs the room.

### Gear & Leveling Planning — build it before you farm it

A full paper doll with every equipment slot, backed by a searchable database of
every item in the game. Click a slot and see only what your race and class can
actually wear in it, sortable by damage, delay, ratio, type or effect. Each
slot tracks its item and its effects separately — focus, click, worn and proc —
so you can plan a piece around what it does, not just what it is.

Ten save slots hold complete builds: gear, level, race, class, and your AA
plan. Name them, save them, load them, export them to a text file to share.

The same window carries an **AA planner**. Track the ranks you intend to buy
and they come out as a numbered purchase list — rank by rank, with what each
one costs and a running total of the ability points you'll need. Buy one in
game and the tracker sees it in your log and quietly crosses it off the plan.

### EQL DB — keep the item database current

The item database ships with the app as a dated snapshot, so everything works
the moment you run it. When the wiki moves ahead of that snapshot, this is how
you catch up.

A control panel exposes the whole pipeline — scrape, build, verify — with every
option laid out and the exact command shown before it runs, so nothing is
hidden behind a button. A full rebuild is a slow, deliberate crawl of the wiki
that takes a few hours; there are targeted options for updating a single
category or backfilling what's missing without starting over.

### External Links

Five community sites worth having a click away, gathered in one menu instead of
scattered across bookmarks.

### Advanced Features

The maintenance drawer. Release notes and a troubleshooting guide that answers
the questions people actually hit. Archive your log to a zip and start it fresh
when it gets unwieldy. Truncate chat channels out of the log without losing
your data. Clear recorded data selectively — drop history, item database, boss
data, or a full reset — behind a confirmation that tells you exactly what
you're about to lose before you lose it.

### Themes

Four palettes, because staring at a tracker for hours should be your choice,
not mine. Pick one that sits comfortably beside your in-game UI, or one that
matches your stream. The dashboards and the OBS overlay follow along.

## Privacy

The app makes no outbound calls. It reads your log file, writes to its own
`Data` folder, and serves its dashboards on `127.0.0.1` — visible to your own
machine only.

The one exception is entirely yours to trigger: the EQL DB scraper fetches
pages from eqlwiki.com, and only while you run it. Item and mob names link to
that wiki, and the External Links menu opens community sites — those load only
if you click them.

Nothing is uploaded. Nothing phones home.

## Troubleshooting and release notes

Both are inside the app, under **Advanced Features** — the full version
history, the security note, and answers to the problems people actually hit
(log location, overlay performance, log size, per-character data).

## Version

**1.0.42.** The version history is in the app under Advanced Features →
Release and Troubleshooting.
