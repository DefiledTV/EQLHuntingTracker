# EQL Hunting Log — Installation

**Requirement (all methods except prebuilt exe):** Python 3 from python.org.
Tick **"Add Python to PATH"** during install.

## Method 1 — GitHub installer (recommended)
1. Download `EQL_Hunting_Log_installer_v0.2.3.py` from the Releases page.
2. Double-click it (or run `python EQL_Hunting_Log_installer_v0.2.3.py`).
3. It creates an **"EQL Hunting Log"** folder next to itself with the app,
   README, and changelog, then offers to launch. Nothing installs
   system-wide; delete the folder to remove everything.

## Method 2 — Just the app file
1. Download `eql_tracker_app_v0.2.3.pyw` and put it in its own folder
   (e.g. `C:\Tools\EQLTracker`). Avoid Downloads and Program Files.
2. Double-click it. The `.pyw` extension launches without a console window.

## Method 3 — Clone or download the repository
`git clone` the repo (or Code → Download ZIP and extract), then double-click
the `.pyw`. Your personal data files are covered by `.gitignore` and never
end up in the repo.

## Method 4 — Build your own .exe
```
python -m pip install pyinstaller
python -m PyInstaller --onefile --noconsole eql_tracker_app_v0.2.3.pyw
```
Your executable lands in `dist\`. Move it to a stable folder — the config
and data files are created next to whichever file you run.

## Method 5 — Google Drive package
If this was pulled from Google Drive, you just need to extract the files,
and in the `dist` folder you will find the executable file. Move it to a
folder of its own and run it.

## First run
1. Launch the app and click **Browse...** to pick your log file, e.g.
   `C:\Users\Public\Daybreak Game Company\Installed Games\EverQuest Legends\Logs\eqlog_<name>_<server>.txt`
2. In game, type `/log on`.
3. The dashboard opens at http://localhost:8710 — the app remembers your log
   and resumes automatically every launch.

## Updating
Drop the new versioned `.pyw` (or exe) into the same folder and delete the
old one. Config, lifetime stats, kill history, and quest data all carry over
untouched — they are found by folder, not by filename.
