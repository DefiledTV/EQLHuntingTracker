# Installing Python (so EQL Hunting Log can run)

The tracker is a single Python file with no add-ons — the only thing your
PC needs is Python itself. One install, about two minutes, no admin rights
required. These steps are for Windows (10/11); Mac/Linux notes are at the
bottom.

## Windows — the two minute version

1. **Download it.** Go to **https://www.python.org/downloads/** and click
   the big yellow **Download Python 3.x.x** button. (Always python.org —
   skip the Microsoft Store version; it causes the problems in the
   troubleshooting section below.)

2. **Run the installer — and STOP on the first screen.** Before clicking
   anything else, tick the checkbox at the bottom:

   > ☑ **Add python.exe to PATH**

   This one checkbox is the difference between everything working and
   nothing working. Once it's ticked, click **Install Now**. No admin
   prompt is needed for the default per-user install; if Windows asks
   anyway, allow it.

3. **Verify it took.** Open a fresh Command Prompt (press Start, type
   `cmd`, Enter) and run:
   ```
   python --version
   ```
   You should see something like `Python 3.12.6`. If you do, you're done.

4. **Run the tracker.** Double-click `eql_tracker_app_v0.2.3.pyw` (or the
   installer from the Releases page). The `.pyw` extension means it opens
   with no black console window — just the app.

## If something went wrong

**"'python' is not recognized as an internal or external command"**
You missed the PATH checkbox (everyone does once). Two fixes:
- Easiest: run the python.org installer again → **Modify** → Next →
  on "Advanced Options" tick **Add Python to environment variables** →
  Install. Open a *new* Command Prompt and re-verify.
- Or use the launcher that installs regardless of PATH: `py --version`.
  If that works, the tracker will still double-click fine.

**Typing `python` opens the Microsoft Store**
Windows ships a fake `python` that redirects to the Store. Fix: Start →
"Manage app execution aliases" → turn **off** both "python.exe" and
"python3.exe" entries. Then verify again in a new Command Prompt.

**Double-clicking the .pyw does nothing**
Right-click the file → Open with → Choose another app → scroll to
**Python** (pick "Python" / pythonw, not "Python (console)") → tick
"Always use this app". If Python isn't in the list: Browse to
`C:\Users\<you>\AppData\Local\Programs\Python\Python3xx\pythonw.exe`.

**SmartScreen says "Windows protected your PC" on the installer**
That's Windows being cautious about any downloaded program. The
python.org installer is safe — click **More info → Run anyway**. (The
tracker itself never triggers this; it's a plain text script.)

**Do I need to install anything else? pip? packages?**
No. The tracker uses only what ships with Python. `pip` is only needed if
you later choose to build your own .exe (see INSTALLATION.md).

## Mac
Install from python.org (macOS installer) or, if you use Homebrew,
`brew install python`. Then run the tracker from Terminal with
`python3 eql_tracker_app_v0.2.3.pyw`. Note: the app is developed and
tested on Windows; the overlay's click-through option is Windows-only.

## Linux
Python 3 is almost certainly already installed (`python3 --version`).
You may need Tk for the app window: `sudo apt install python3-tk`
(Debian/Ubuntu) or your distro's equivalent. Run with
`python3 eql_tracker_app_v0.2.3.pyw`.

## Uninstalling later
Windows Settings → Apps → Python 3.x → Uninstall. The tracker itself
never installs anything — deleting its folder removes it completely.
