[README.md](https://github.com/user-attachments/files/30438991/README.md)
# EQL Tools

A real-time combat tracker for **EverQuest Legends**. It reads your game log
and gives you live DPS, overlays you can stream, a gear planner and a searchable
item database.

This is the **standalone build**: one file, with Python, Tk and the item
database inside it. Nothing to install.

Everything is local: the app binds `127.0.0.1` and makes no outbound calls.

## Run it

1. Put `EQL_Tools_v1.0.20.exe` anywhere you can write to. Your Documents
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
misses, avoidance, heals, pets, and per-member contribution when you're
grouped.

One honest limit worth stating up front: **group numbers are a floor, not a
total.** The game's log only records other players' melee swings and named
spell hits, so a member's real output is always at least what you see and often
more. Mobs killed entirely by your group without you engaging never open a
fight at all, so they won't appear in your kill log either. Your own numbers
are complete; everyone else's are the visible portion.

**Time to Kill** watches named bosses and estimates how much longer the fight
has left. It's an approximation, and an honest one — it learns from the kills
you actually record, so it sharpens the more you fight something and it will
not pretend to know a boss it has never seen.

It also keeps your **loot history**: which mobs drop what, how often, and how
many of a given item you've laid eyes on. Over time that turns "does this thing
even drop here" into a number.

### Overlays — two of them, one built for streaming

Two separate overlays. The first sits over the game itself: a compact,
always-on-top readout of your live numbers, drawn to stay out of your way. The
second is built for **OBS** — capture that window as a source and everything
you see, your viewers see, without exposing your desktop or the rest of the
app.

Both are yours to arrange. Pick exactly which cells appear and which you don't
care about, set the opacity of each row independently, and drag them wherever
they belong on your layout. Hidden cells close the gap rather than leaving
holes. The one thing you can't do is resize them — the layout is fixed by
design so the text stays legible at a glance mid-fight.

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

**1.0.20.** The version history is in the app under Advanced Features →
Release and Troubleshooting.
