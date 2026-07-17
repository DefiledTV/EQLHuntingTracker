#!/usr/bin/env python3
"""
EQL Hunting Log v0.2.3 - standalone tracker app
-----------------------------------------------
Double-click this file (keep the .pyw extension on Windows for no console).
Pick your EverQuest Legends log once; the app remembers it and auto-resumes.

Dashboards: All / Combat / Loot / Quests at http://localhost:8710
OBS overlay: /overlay - Game overlay: always-on-top window.
Buttons: Features, Archive, Truncate, Release and Troubleshooting,
Rebuild Data, Gear & Leveling Planning (coming soon).

Files created next to this script:
  eql_tracker_config.json  eql_lifetime_stats.json
  eql_kill_history.jsonl   eql_quests.json
"""
import json, os, re, sys, threading, time, webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------- parsing
TS = re.compile(r"^\[(.+?)\] (.*)$")
VERBS = "slash|hit|strike|kick|bash|reave|crush|pierce|punch|backstab|maul|bite|claw|gore|slam|frenzy"
IN_VERBS = "hits|kicks|bashes|slashes|cleaves|crushes|pierces|punches|mauls|bites|claws|gores|slams|smashes|strikes"
SUFFIX = r"( \((?:Critical|Riposte|Riposte Critical|Crippling Blow)\))?"
RE_PROC    = re.compile(r"^You hit (.+?) for (\d+) points of \w+ damage by (.+?)\.%s$" % SUFFIX)
RE_MELEE   = re.compile(r"^You (%s)(?: on)? (.+?) for (\d+) points of damage\.%s$" % (VERBS, SUFFIX))
RE_MISS    = re.compile(r"^You try to (%s)(?: on)? (.+?), but (.+?)!" % VERBS)
RE_DOT     = re.compile(r"^(.+?) has taken (\d+) damage from your (.+?)\.")
RE_NONMELE = re.compile(r"^(.+?) was hit by non-melee for (\d+) points of damage\.")
RE_IN_HIT  = re.compile(r"^(.+?) ((?:%s)|frenzies on) YOU for (\d+)" % IN_VERBS)
RE_IN_TRY  = re.compile(r"^(.+?) tries to \w+ YOU, but (.+?)!")
RE_IN_SPELL= re.compile(r"^(.+?) hit you for (\d+) points of \w+ damage by (.+?)\.")
RE_IN_DS   = re.compile(r"^YOU are \w+ by (.+?)(?:'s (.+?))? for (\d+) points of non-melee damage!")
RE_IN_DOT  = re.compile(r"^You have taken (\d+) damage from (.+?)(?: by (.+?))?\.")
RE_RESIST  = re.compile(r"^You resist (.+?)'s")
RE_SLAIN   = re.compile(r"^You have slain (.+?)!")
RE_OSLAIN  = re.compile(r"^(.+?) has been slain by (.+?)!")
RE_DEAD    = re.compile(r"^You have been slain by (.+?)!")
RE_LOOT    = re.compile(r"^(?:--)?You (?:have )?looted (.+?) from (.+?)'s corpse(.*)$")
RE_LEVEL   = re.compile(r"^You have gained a level! Welcome to level (\d+)!")
RE_SOLD    = re.compile(r"sold it for (.+?)\.?\s*$")
RE_MADE    = re.compile(r"to create (.+?)\s*$")
RE_COINLOOT= re.compile(r"^You receive (.+?) from the corpse\.")
RE_HEAL    = re.compile(r"^You healed (\S+?)(?: over time)? for (\d+)(?: \(\d+\))? hit points by (.+?)\.( \((?:Critical|Riposte Critical)\))?")
RE_XP      = re.compile(r"^You gain (?:party )?experience! \(([\d.]+)%\)")
RE_ANY_HIT = re.compile(r"^(.+?) ((?:%s)|frenzies on) (.+?) for (\d+) points of damage\." % IN_VERBS)
RE_PET     = re.compile(r"^(\S+) (?:tells you|told you|says),? '[^']*\bMaster\b")
RE_HAIL    = re.compile(r"^You say, 'Hail,? (.+?)'")
RE_NPCSAY  = re.compile(r"^(.+?) says?, '(.*)'\s*$")
RE_INT_ME  = re.compile(r"^Your (.+?) spell is interrupted\.")
RE_INT_THM = re.compile(r"^(.+?)'s (.+?) spell is interrupted\.")
RE_RUNE    = re.compile(r"^You gain a rune for (\d+) points of absorption")
RE_ZONE    = re.compile(r"^You have entered (.+?)\.$")
VERB_BASE  = {"hits": "Hit", "kicks": "Kick", "bashes": "Bash", "slashes": "Slash",
              "cleaves": "Cleave", "crushes": "Crush", "pierces": "Pierce",
              "punches": "Punch", "mauls": "Maul", "bites": "Bite", "claws": "Claw",
              "gores": "Gore", "slams": "Slam", "smashes": "Smash",
              "strikes": "Strike", "frenzies on": "Frenzy"}
COIN       = re.compile(r"(\d+) (platinum|gold|silver|copper)")
COIN_VAL   = {"platinum": 1000, "gold": 100, "silver": 10, "copper": 1}
QTY        = re.compile(r"^(\d+) (.+)$")
VERSION    = "0.2.3"
ENC_GAP    = 12          # seconds of silence that ends an encounter
STALE      = 20          # current-combat freshness window

def norm(name):
    return re.sub(r"^(?:an?|the) ", "", name.strip(), flags=re.I).lower()

def coin_str(copper):
    p, r = divmod(int(copper), 1000); g, r = divmod(r, 100); s, c = divmod(r, 10)
    out = " ".join("%d%s" % (v, u) for v, u in ((p, "p"), (g, "g"), (s, "s"), (c, "c")) if v)
    return out or "0c"

def item_norm(raw):
    raw = raw.strip()
    m = QTY.match(raw)
    qty = 1
    if m:
        qty, raw = int(m.group(1)), m.group(2)
    return re.sub(r"^an? ", "", raw, flags=re.I), qty

def _bag():
    return {"dmg": 0, "hits": 0, "miss": 0, "max": 0, "crits": 0}

def _hbag():
    return {"amt": 0, "count": 0, "max": 0}

def _add_hit(bag, dmg, crit=False):
    bag["dmg"] += dmg; bag["hits"] += 1
    bag["max"] = max(bag["max"], dmg); bag["crits"] += bool(crit)

def _add_heal(bag, amt):
    bag["amt"] += amt; bag["count"] += 1; bag["max"] = max(bag["max"], amt)

def build_skill_rows(sk, span):
    tot = sum(v["dmg"] for v in sk.values()) or 1
    rows = []
    for src2, v in sorted(sk.items(), key=lambda x: -x[1]["dmg"]):
        att = v["hits"] + v["miss"]
        rows.append({"name": src2, "dmg": v["dmg"],
                     "pct": round(100 * v["dmg"] / tot, 1),
                     "hits": v["hits"], "miss": v["miss"],
                     "acc": round(100 * v["hits"] / att) if att else None,
                     "avg": round(v["dmg"] / v["hits"], 1) if v["hits"] else 0,
                     "max": v["max"], "crits": v["crits"],
                     "dps": round(v["dmg"] / span, 1)})
    return rows

def build_heal_rows(hs, span):
    tot = sum(v["amt"] for v in hs.values()) or 1
    return [{"name": src2, "amt": v["amt"],
             "pct": round(100 * v["amt"] / tot, 1), "count": v["count"],
             "avg": round(v["amt"] / v["count"], 1) if v["count"] else 0,
             "max": v["max"], "hps": round(v["amt"] / span, 1)}
            for src2, v in sorted(hs.items(), key=lambda x: -x[1]["amt"])]

def build_in_rows(fin):
    return [{"name": lbl, "dmg": v["dmg"], "hits": v["hits"],
             "avg": round(v["dmg"] / v["hits"], 1) if v["hits"] else 0,
             "max": v["max"]}
            for lbl, v in sorted(fin.items(), key=lambda x: -x[1]["dmg"])]

# ---------------------------------------------------------------- tracker
class Tracker:
    def __init__(self, lifetime_path, log_path, no_persist=False):
        self.lock = threading.Lock()
        self.no_persist = no_persist
        self.lifetime_path = lifetime_path
        self.log_path = os.path.abspath(log_path)
        self.history_path = os.path.join(os.path.dirname(lifetime_path) or ".",
                                         "eql_kill_history.jsonl")
        self.history = []
        self._hist_unwritten = []
        self.lifetime = {"mobs": {}, "file_offsets": {}}
        if os.path.exists(lifetime_path):
            try:
                with open(lifetime_path, encoding="utf-8") as f:
                    self.lifetime.update(json.load(f))
            except Exception:
                pass
        self.lifetime.setdefault("totals", {})
        self.lifetime["totals"].setdefault("coin", 0)
        self.lifetime["totals"].setdefault("deaths", 0)
        self.lifetime.setdefault("skills", {})
        self.lifetime.setdefault("heals", {})
        self.lifetime.setdefault("deaths_log", [])
        self.lifetime.setdefault("tracked", [])
        self.lifetime["tracked"] = list(dict.fromkeys(
            [t[0] if isinstance(t, list) else t for t in self.lifetime["tracked"]]))
        self.lifetime.setdefault("history_built", {})
        if not no_persist:
            legacy = self.lifetime.pop("kill_log", None)
            if legacy and not os.path.exists(self.history_path):
                try:
                    with open(self.history_path, "w", encoding="utf-8") as f:
                        for r in legacy:
                            r.setdefault("src", os.path.basename(self.log_path))
                            r.setdefault("ts", 0); r.setdefault("detail", None)
                            f.write(json.dumps(r) + "\n")
                except Exception:
                    pass
            if os.path.exists(self.history_path):
                try:
                    with open(self.history_path, encoding="utf-8") as f:
                        for ln in f:
                            ln = ln.strip()
                            if ln:
                                self.history.append(json.loads(ln))
                    self.history.sort(key=lambda r: r.get("ts", 0))
                except Exception:
                    pass
        self.lifetime.setdefault("combat_s", 0)
        self.lifetime.setdefault("play_s", 0)
        self.lifetime.setdefault("level", None)
        self.lifetime.setdefault("level_ups", [])
        self.lifetime.setdefault("xp_into", 0.0)
        self.quests_path = os.path.join(os.path.dirname(lifetime_path) or ".",
                                        "eql_quests.json")
        self.quests = {"npcs": {}, "dismissed": []}
        if not no_persist and os.path.exists(self.quests_path):
            try:
                with open(self.quests_path, encoding="utf-8") as f:
                    self.quests.update(json.load(f))
            except Exception:
                pass
        self.combat_base = float(self.lifetime.get("combat_s", 0))
        self.perf = {"backlog_s": None, "log_mb": 0.0,
                     "batch_ms": 0, "batch_lines": 0}
        self.reset_session()

    def reset_session(self):
        self.fights = []            # every fight, chronological
        self.open_f = {}            # norm name -> open fight
        self.last_closed = {}       # norm name -> last closed fight (loot attach)
        self.skills = {}            # session outgoing by source
        self.heals = {}             # session healing by source
        self.kills = 0
        self.deaths = 0
        self.xp = 0.0
        self.coin = 0
        self.kill_times = []
        self.first_ts = None
        self.last_ts = None
        self.session_drops = {}     # mob key -> {"kills", "items": {item: {"drops","qty"}}}
        self.mob_last_kill = {}
        self.death_log = []
        self.pets = set()
        self.pet_skills = {}
        self.pet_taken = {}
        self.current_zone = ""
        self.stats = {}             # outcome counters (miss/dodge/parry/...)
        self.last_hail = None       # (name_lower, ts)
        self.active_s = 0.0         # gap-capped play seconds this session
        self._act_last = None
        self.play_base = self.lifetime.get("play_s", 0) if hasattr(self, "lifetime") else 0
        self.cur_enc = None
        self.last_enc = None
        self.last_in_hit = None     # {"name","label","dmg","ts"} for killing-blow capture
        self.current_offset = None

    # ---- encounters -------------------------------------------------
    def _new_enc(self, ts):
        return {"start": ts, "end": ts, "fights": [], "heals": {},
                "stats": {}, "zone": self.current_zone, "result": None}

    def _close_enc(self, result=None):
        enc = self.cur_enc
        if enc is None:
            return
        for f in list(enc["fights"]):
            if f["result"] is None:
                f["result"] = "expired"
                self.open_f.pop(f["key"], None)
        if result:
            enc["result"] = result
        elif all(f["result"] in ("slain", "slain (group)") for f in enc["fights"]):
            enc["result"] = "cleared"
        else:
            enc["result"] = "partial"
        self.last_enc = enc
        self.cur_enc = None

    def _touch_enc(self, ts):
        if self.cur_enc and ts - self.cur_enc["end"] > ENC_GAP:
            self._close_enc()
        if self.cur_enc is None:
            self.cur_enc = self._new_enc(ts)
        self.cur_enc["end"] = max(self.cur_enc["end"], ts)
        return self.cur_enc

    # ---- fights -----------------------------------------------------
    def _fight(self, name, ts):
        k = norm(name)
        f = self.open_f.get(k)
        if f is None:
            f = {"name": name.strip(), "key": k, "start": ts, "end": ts,
                 "dmg": 0, "taken": 0, "skills": {}, "in": {}, "in_miss": 0,
                 "pet_in": {}, "zone": self.current_zone,
                 "loot": [], "loot_names": set(), "result": None, "killer": ""}
            self.open_f[k] = f
            self.fights.append(f)
        f["end"] = max(f["end"], ts)
        enc = self._touch_enc(ts)
        if not f.get("_enc") is enc:
            if f not in enc["fights"]:
                enc["fights"].append(f)
            f["_enc"] = enc
        return f

    def _skill(self, store, src):
        return store.setdefault(src, _bag())

    def _out_dmg(self, target, dmg, src, ts, crit=False):
        if crit:
            src = src + " (Crit)"
        f = self._fight(target, ts)
        f["dmg"] += dmg
        _add_hit(self._skill(f["skills"], src), dmg, crit)
        _add_hit(self._skill(self.skills, src), dmg, crit)
        if not self.no_persist:
            _add_hit(self._skill(self.lifetime["skills"], src), dmg, crit)

    def _in_dmg(self, attacker, dmg, label, ts):
        f = self._fight(attacker, ts)
        f["taken"] += dmg
        bag = f["in"].setdefault(label, {"dmg": 0, "hits": 0, "max": 0})
        bag["dmg"] += dmg; bag["hits"] += 1; bag["max"] = max(bag["max"], dmg)
        self.last_in_hit = {"name": f["name"], "label": label, "dmg": dmg, "ts": ts}

    def _bump(self, key, n=1, ts=None):
        self.stats[key] = self.stats.get(key, 0) + n
        enc = self.cur_enc
        if enc is not None and ts is not None and ts - enc["end"] <= ENC_GAP:
            enc["stats"][key] = enc["stats"].get(key, 0) + n

    def save_quests(self):
        if self.no_persist:
            return
        try:
            tmp = self.quests_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.quests, f, indent=1)
            os.replace(tmp, self.quests_path)
        except Exception as e:
            print("WARN: quest save failed: %r" % e, file=sys.stderr)

    def _quest_add(self, name, text):
        key = norm(name) + "|" + self.current_zone.lower()
        if key in self.quests["dismissed"]:
            return
        rec = self.quests["npcs"].setdefault(
            key, {"name": name.strip(), "zone": self.current_zone,
                  "texts": [], "state": "open"})
        rec.setdefault("state", "open")
        if text not in rec["texts"]:
            rec["texts"].append(text)
            rec["texts"] = rec["texts"][:60]
            self.save_quests()

    def quest_set_state(self, key, state):
        with self.lock:
            rec = self.quests["npcs"].get(key)
            if rec is not None and state in ("open", "closed", "done"):
                rec["state"] = state
                self.save_quests()

    def _mob_life(self, key, create=True):
        if create:
            return self.lifetime["mobs"].setdefault(key, {"kills": 0, "drops": {}})
        return self.lifetime["mobs"].get(key, {"kills": 0, "drops": {}})

    def _mob_sess(self, key):
        return self.session_drops.setdefault(key, {"kills": 0, "items": {}})

    def _record_kill(self, name, ts, killer=""):
        k = norm(name)
        f = self.open_f.pop(k, None)
        if f is None:
            f = self._fight(name, ts)
            self.open_f.pop(k, None)
        f["result"] = "slain" if not killer else "slain (group)"
        f["killer"] = killer
        f["end"] = ts
        self.last_closed[k] = f
        d = max(1, int(f["end"] - f["start"]))
        rec = {"ts": ts, "src": os.path.basename(self.log_path),
               "name": f["name"],
               "time": datetime.fromtimestamp(ts).strftime("%b %d %H:%M:%S"),
               "dur": d, "dmg": f["dmg"], "taken": f["taken"],
               "dps": round(f["dmg"] / d, 1), "killer": killer, "loot": [],
               "zone": f.get("zone", ""),
               "detail": {"skills": build_skill_rows(f["skills"], d),
                          "incoming": build_in_rows(f["in"]),
                          "pet_in": build_in_rows(f["pet_in"]),
                          "in_miss": f["in_miss"]}}
        f["_liferec"] = rec
        self.history.append(rec)
        self._hist_unwritten.append(rec)
        self.kills += 1
        self.kill_times.append(ts)
        self.mob_last_kill[k] = ts
        if not self.no_persist:
            ml = self._mob_life(k)
            ml["kills"] += 1
            if f.get("zone"):
                ml["zone"] = f["zone"]
        self._mob_sess(k)["kills"] += 1
        enc = self.cur_enc
        if enc and all(x["result"] is not None for x in enc["fights"]):
            self._close_enc()
        self.save_lifetime()

    # ---- feed one log line -------------------------------------------
    def feed(self, raw):
        m = TS.match(raw.strip())
        if not m:
            return
        try:
            ts = datetime.strptime(m.group(1), "%a %b %d %H:%M:%S %Y").timestamp()
        except ValueError:
            return
        line = m.group(2)
        with self.lock:
            if self.first_ts is None:
                self.first_ts = ts
            self.last_ts = ts
            if self._act_last is not None:
                gap = ts - self._act_last
                if 0 < gap <= 300:
                    self.active_s += gap
            self._act_last = ts

            p = RE_PROC.match(line)
            if p:
                self._out_dmg(p.group(1), int(p.group(2)), p.group(3), ts,
                              crit="Critical" in (p.group(4) or "")); return
            p = RE_MELEE.match(line)
            if p:
                sfx = p.group(4) or ""
                if "Riposte" in sfx:
                    self._bump("riposte_hits", 1, ts)
                    self._bump("riposte_dmg", int(p.group(3)), ts)
                self._out_dmg(p.group(2), int(p.group(3)),
                              p.group(1).capitalize() + " (melee)", ts,
                              crit="Critical" in sfx); return
            p = RE_MISS.match(line)
            if p:
                msrc = p.group(1).capitalize() + " (melee)"
                self._skill(self.skills, msrc)["miss"] += 1
                if not self.no_persist:
                    self._skill(self.lifetime["skills"], msrc)["miss"] += 1
                f = self._fight(p.group(2), ts)
                self._skill(f["skills"], msrc)["miss"] += 1
                out = p.group(3)
                if out.startswith("miss"): self._bump("o_miss", 1, ts)
                elif "dodge" in out: self._bump("o_dodge", 1, ts)
                elif "parr" in out: self._bump("o_parry", 1, ts)
                elif "block" in out: self._bump("o_block", 1, ts)
                elif "ripost" in out: self._bump("o_riposte", 1, ts)
                elif "absorb" in out: self._bump("o_absorb", 1, ts)
                return
            p = RE_DOT.match(line)
            if p:
                self._out_dmg(p.group(1), int(p.group(2)), p.group(3) + " (DoT)", ts); return
            p = RE_NONMELE.match(line)
            if p:
                self._bump("ds_dealt", int(p.group(2)), ts)
                self._out_dmg(p.group(1), int(p.group(2)), "Damage Shield", ts); return
            p = RE_IN_HIT.match(line)
            if p:
                verb = p.group(2).replace("frenzies on", "frenzy")
                self._in_dmg(p.group(1), int(p.group(3)),
                             verb.rstrip("s").capitalize() + " (melee)", ts); return
            p = RE_IN_SPELL.match(line)
            if p:
                self._in_dmg(p.group(1), int(p.group(2)), p.group(3), ts); return
            p = RE_IN_DS.match(line)
            if p:
                label = (p.group(2) or "damage shield").strip()
                self._bump("ds_taken", int(p.group(3)), ts)
                self._in_dmg(p.group(1), int(p.group(3)), label.capitalize() + " (DS)", ts); return
            p = RE_IN_DOT.match(line)
            if p:
                dmg, spell, att = int(p.group(1)), p.group(2), p.group(3)
                if att:
                    self._in_dmg(att, dmg, spell + " (DoT)", ts)
                elif self.open_f:
                    fx = max(self.open_f.values(), key=lambda x: x["end"])
                    self._in_dmg(fx["name"], dmg, spell + " (DoT)", ts)
                return
            p = RE_IN_TRY.match(line)
            if p:
                f = self._fight(p.group(1), ts); f["in_miss"] += 1
                out = p.group(2)
                if "YOU dodge" in out: self._bump("d_dodge", 1, ts)
                elif "YOU parry" in out: self._bump("d_parry", 1, ts)
                elif "YOU block" in out: self._bump("d_block", 1, ts)
                elif "YOU riposte" in out: self._bump("d_riposte", 1, ts)
                elif "magical skin" in out: self._bump("d_absorb", 1, ts)
                else: self._bump("d_miss", 1, ts)
                return
            p = RE_RESIST.match(line)
            if p:
                self._fight(p.group(1), ts); return
            p = RE_DEAD.match(line)
            if p:
                self.deaths += 1
                engaged = sorted(self.open_f.values(), key=lambda x: -x["end"])
                kh = self.last_in_hit
                rec = {"time": datetime.fromtimestamp(ts).strftime("%b %d %H:%M:%S"),
                       "killer": p.group(1),
                       "killing_hit": (kh if kh and ts - kh["ts"] <= 4 else None),
                       "taken": sum(f2["taken"] for f2 in engaged),
                       "engaged": [{"name": f2["name"], "taken": f2["taken"],
                                    "dur": max(1, int(f2["end"] - f2["start"]))}
                                   for f2 in engaged]}
                if rec["killing_hit"]:
                    rec["killing_hit"] = {x: rec["killing_hit"][x]
                                          for x in ("name", "label", "dmg")}
                self.death_log.append(rec)
                if not self.no_persist:
                    self.lifetime["deaths_log"].append(rec)
                    self.lifetime["deaths_log"] = self.lifetime["deaths_log"][-200:]
                    self.lifetime["totals"]["deaths"] += 1
                for f in self.open_f.values():
                    f["result"] = "player died"; f["end"] = ts
                self.open_f.clear()
                self._close_enc(result="died")
                self.save_lifetime()
                return
            p = RE_SLAIN.match(line)
            if p:
                self._record_kill(p.group(1), ts); return
            p = RE_OSLAIN.match(line)
            if p:
                victim, killer = p.group(1), p.group(2)
                if norm(victim) in self.open_f:      # a mob our group was fighting
                    self._record_kill(victim, ts, killer=killer)
                return
            p = RE_LOOT.match(line)
            if p:
                item_raw, corpse, rest = p.group(1), p.group(2), p.group(3)
                if item_raw.startswith("a "):
                    item_raw = item_raw[2:]
                elif item_raw.startswith("an "):
                    item_raw = item_raw[3:]
                item, qty = item_norm(item_raw)
                sold = RE_SOLD.search(rest); made = RE_MADE.search(rest)
                if sold:
                    for amt, denom in COIN.findall(sold.group(1)):
                        v = int(amt) * COIN_VAL[denom]
                        self.coin += v
                        if not self.no_persist:
                            self.lifetime["totals"]["coin"] += v
                k = norm(corpse)
                f = self.last_closed.get(k)
                label = item + (" x%d" % qty if qty > 1 else "")
                if made:
                    label += " -> " + made.group(1)
                first_of_kill = True
                if f is not None:
                    f["loot"].append(label)
                    if f.get("_liferec") is not None:
                        f["_liferec"]["loot"].append(label)
                    first_of_kill = item not in f["loot_names"]
                    f["loot_names"].add(item)
                stores = [self._mob_sess(k)["items"]]
                if not self.no_persist:
                    stores.append(self._mob_life(k)["drops"])
                for store in stores:
                    d = store.setdefault(item, {"drops": 0, "qty": 0})
                    if first_of_kill:
                        d["drops"] += 1
                    d["qty"] += qty
                self.save_lifetime()
                return
            p = RE_COINLOOT.match(line)
            if p:
                for amt, denom in COIN.findall(p.group(1)):
                    v = int(amt) * COIN_VAL[denom]
                    self.coin += v
                    if not self.no_persist:
                        self.lifetime["totals"]["coin"] += v
                return
            p = RE_HEAL.match(line)
            if p:
                amt, hsrc = int(p.group(2)), p.group(3)
                if p.group(4):
                    hsrc = hsrc + " (Crit)"
                _add_heal(self.heals.setdefault(hsrc, _hbag()), amt)
                if not self.no_persist:
                    _add_heal(self.lifetime["heals"].setdefault(hsrc, _hbag()), amt)
                if self.cur_enc and ts - self.cur_enc["end"] <= ENC_GAP:
                    _add_heal(self.cur_enc["heals"].setdefault(hsrc, _hbag()), amt)
                return
            p = RE_XP.match(line)
            if p:
                v = float(p.group(1))
                self.xp += v
                if not self.no_persist:
                    self.lifetime["xp_into"] = self.lifetime.get("xp_into", 0.0) + v
                return
            p = RE_LEVEL.match(line)
            if p:
                lvl = int(p.group(1))
                self.lifetime["level"] = lvl
                ups = self.lifetime["level_ups"]
                ups.append([ts, lvl])
                del ups[:-50]
                self.lifetime["xp_into"] = 0.0
                return
            p = RE_HAIL.match(line)
            if p:
                self.last_hail = (norm(p.group(1)), ts)
                return
            p = RE_INT_ME.match(line)
            if p:
                self._bump("int_mine", 1, ts); return
            p = RE_INT_THM.match(line)
            if p:
                self._bump("int_them", 1, ts); return
            p = RE_RUNE.match(line)
            if p:
                self._bump("rune_pts", int(p.group(1)), ts)
                self._bump("rune_hits", 1, ts); return
            p = RE_PET.match(line)
            if p:
                self.pets.add(norm(p.group(1)))
                return
            p = RE_NPCSAY.match(line)
            if p and norm(p.group(1)) not in self.pets:
                speaker, text = p.group(1), p.group(2)
                key = norm(speaker) + "|" + self.current_zone.lower()
                hailed = self.last_hail and self.last_hail[0] == norm(speaker) \
                    and ts - self.last_hail[1] <= 30
                if "[" in text and "]" in text:
                    self._quest_add(speaker, text)
                elif key in self.quests["npcs"] and (hailed or True):
                    self._quest_add(speaker, text)
                return
            p = RE_ZONE.match(line)
            if p:
                self.current_zone = p.group(1).strip()
                return
            p = RE_ANY_HIT.match(line)      # pets and group members
            if p:
                att, verb, tgt, dmg = p.group(1), p.group(2), p.group(3), int(p.group(4))
                an, tn = norm(att), norm(tgt)
                vlabel = VERB_BASE.get(verb, verb.capitalize()) + " (melee)"
                if an in self.pets:            # our pet attacking: merge as "Pet"
                    f = self._fight(tgt, ts)
                    f["dmg"] += dmg
                    _add_hit(self._skill(f["skills"], "Pet"), dmg)
                    _add_hit(self._skill(self.pet_skills, vlabel), dmg)
                elif tn in self.pets:          # something hitting our pet
                    f = self._fight(att, ts)
                    for store in (f["pet_in"], self.pet_taken):
                        b = store.setdefault(vlabel, {"dmg": 0, "hits": 0, "max": 0})
                        b["dmg"] += dmg; b["hits"] += 1; b["max"] = max(b["max"], dmg)
                else:                          # other group members: extend windows only
                    for nm in (att, tgt):
                        f = self.open_f.get(norm(nm))
                        if f:
                            f["end"] = max(f["end"], ts)
                            self._touch_enc(ts)
                return

    # ---- persistence -------------------------------------------------
    def _active_union(self):
        ivs = sorted((f["start"], f["end"]) for f in self.fights)
        merged = []
        for a, b in ivs:
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        return sum(max(1, b - a) for a, b in merged) or 1

    def flush_history(self, force=False):
        if self.no_persist:
            return
        cutoff = (self.last_ts or 0) - 5
        out, keep = [], []
        for r in self._hist_unwritten:
            (out if (force or r["ts"] <= cutoff) else keep).append(r)
        if out:
            try:
                with open(self.history_path, "a", encoding="utf-8") as f:
                    for r in out:
                        f.write(json.dumps(r) + "\n")
            except Exception as e:
                print("WARN: history write failed: %r" % e, file=sys.stderr)
                keep = out + keep
        self._hist_unwritten = keep

    def rewrite_history(self):
        if self.no_persist:
            return
        try:
            tmp = self.history_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for r in self.history:
                    f.write(json.dumps(r) + "\n")
            os.replace(tmp, self.history_path)
            self._hist_unwritten = []
        except Exception as e:
            print("WARN: history rewrite failed: %r" % e, file=sys.stderr)

    def save_lifetime(self, offset=None):
        if self.no_persist:
            return
        self.lifetime["play_s"] = int(self.play_base + self.active_s)
        self.flush_history()
        if offset is None:
            offset = self.current_offset
        if offset is not None:
            self.lifetime["file_offsets"][self.log_path] = offset
        self.lifetime["combat_s"] = round(self.combat_base +
                                          (self._active_union() if self.fights else 0), 1)
        tmp = self.lifetime_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.lifetime, f)
            os.replace(tmp, self.lifetime_path)
        except Exception as e:
            print("WARN: could not save lifetime stats: %r" % e, file=sys.stderr)

    def set_tracked(self, mob, on):
        with self.lock:
            k = norm(mob)
            lst = [t for t in self.lifetime["tracked"] if t != k]
            if on:
                lst.append(k)
            self.lifetime["tracked"] = lst[:100]
            self.save_lifetime()

    # ---- snapshot ------------------------------------------------------
    def snapshot(self, following, kill_q="", item_q=""):
        with self.lock:
            now = time.time() if following else (self.last_ts or time.time())
            dur = lambda f: max(1, int(f["end"] - f["start"]))
            active = self._active_union() if self.fights else 1
            total_dmg = sum(f["dmg"] for f in self.fights)
            life_span = max(1.0, float(self.lifetime.get("combat_s") or 1))

            skill_rows = build_skill_rows
            heal_rows = build_heal_rows
            in_rows = lambda f: build_in_rows(f["in"])
            split_crit = lambda rows: ([r for r in rows if "(Crit)" not in r["name"]],
                                       [r for r in rows if "(Crit)" in r["name"]])
            def _unused_skill_rows(sk, span):
                tot = sum(v["dmg"] for v in sk.values()) or 1
                rows = []
                for src, v in sorted(sk.items(), key=lambda x: -x[1]["dmg"]):
                    att = v["hits"] + v["miss"]
                    rows.append({"name": src, "dmg": v["dmg"],
                                 "pct": round(100 * v["dmg"] / tot, 1),
                                 "hits": v["hits"], "miss": v["miss"],
                                 "acc": round(100 * v["hits"] / att) if att else None,
                                 "avg": round(v["dmg"] / v["hits"], 1) if v["hits"] else 0,
                                 "max": v["max"], "crits": v["crits"],
                                 "dps": round(v["dmg"] / span, 1)})
                return rows

            def heal_rows(hs, span):
                return [{"name": src, "amt": v["amt"],
                         "pct": round(100 * v["amt"] / (sum(x["amt"] for x in hs.values()) or 1), 1),
                         "count": v["count"],
                         "avg": round(v["amt"] / v["count"], 1) if v["count"] else 0,
                         "max": v["max"], "hps": round(v["amt"] / span, 1)}
                        for src, v in sorted(hs.items(), key=lambda x: -x[1]["amt"])]

            def in_rows(f):
                return [{"name": lbl, "dmg": v["dmg"], "hits": v["hits"],
                         "avg": round(v["dmg"] / v["hits"], 1) if v["hits"] else 0,
                         "max": v["max"]}
                        for lbl, v in sorted(f["in"].items(), key=lambda x: -x[1]["dmg"])]

            def enc_view(enc, live):
                if not enc or not enc["fights"]:
                    return None
                d = max(1, int(enc["end"] - enc["start"]))
                dmg = sum(f["dmg"] for f in enc["fights"])
                taken = sum(f["taken"] for f in enc["fights"])
                sk = {}
                for f in enc["fights"]:
                    for src, v in f["skills"].items():
                        b = sk.setdefault(src, _bag())
                        for kx in b:
                            b[kx] += v[kx] if kx != "max" else 0
                        b["max"] = max(b["max"], v["max"])
                names = {}
                for f in enc["fights"]:
                    names[f["name"]] = names.get(f["name"], 0) + 1
                heal_amt = sum(h["amt"] for h in enc["heals"].values())
                st = enc.get("stats", {})
                out_hits = sum(v["hits"] for v in sk.values())
                out_av = sum(st.get(x, 0) for x in
                             ("o_miss", "o_dodge", "o_parry", "o_block",
                              "o_riposte", "o_absorb"))
                in_hits = sum(b["hits"] for f in enc["fights"]
                              for b in f["in"].values())
                in_av = sum(st.get(x, 0) for x in
                            ("d_miss", "d_dodge", "d_parry", "d_block",
                             "d_riposte", "d_absorb"))
                acc = round(100 * out_hits / max(1, out_hits + out_av))
                avoid = round(100 * in_av / max(1, in_hits + in_av))
                res = enc["result"]
                if res is None:
                    res = "ongoing" if live else (
                        "cleared" if all(f["result"] in ("slain", "slain (group)")
                                         for f in enc["fights"]) else "partial")
                return {"mobs": [{"name": n, "count": c} for n, c in names.items()],
                        "n": len(enc["fights"]), "dur": d, "dmg": dmg, "taken": taken,
                        "zone": enc.get("zone", ""), "stats": enc.get("stats", {}),
                        "acc": acc, "avoid": avoid,
                        "dps": round(dmg / d, 1), "result": res,
                        "skills": skill_rows(sk, d),
                        "heals": heal_rows(enc["heals"], d),
                        "heal_total": {"amt": heal_amt, "hps": round(heal_amt / d, 1)},
                        "killed": [{"name": f["name"], "dmg": f["dmg"], "dur": dur(f),
                                    "killer": f["killer"]}
                                   for f in enc["fights"]
                                   if f["result"] in ("slain", "slain (group)")]}

            cur = None
            if self.cur_enc and now - self.cur_enc["end"] <= STALE:
                cur = enc_view(self.cur_enc, True)
            last_cand = self.last_enc
            if self.cur_enc and not cur:
                if not last_cand or self.cur_enc["end"] >= last_cand["end"]:
                    last_cand = self.cur_enc
            last = enc_view(last_cand, False)

            closed = [f for f in self.fights if f["result"] in ("slain", "slain (group)")]
            kq = kill_q.strip().lower()
            kills_out = []
            for i, f in enumerate(closed, 1):
                if kq and kq not in f["name"].lower():
                    continue
                d = dur(f)
                kills_out.append({"n": i, "name": f["name"],
                                  "time": datetime.fromtimestamp(f["end"]).strftime("%I:%M %p"),
                                  "time_full": datetime.fromtimestamp(f["end"]).strftime("%b - %d - %I:%M %p"),
                                  "dur": d, "dmg": f["dmg"], "taken": f["taken"],
                                  "dps": round(f["dmg"] / d, 1),
                                  "killer": f["killer"], "zone": f.get("zone", ""),
                                  "loot": f["loot"] or ["-"],
                                  "detail": {"skills": skill_rows(f["skills"], d),
                                             "incoming": in_rows(f),
                                             "pet_in": build_in_rows(f["pet_in"]),
                                             "in_miss": f["in_miss"]}})
            kills_out.reverse()
            kills_out = kills_out[:20]
            kills_all = []
            for i, r in enumerate(self.history, 1):
                if kq and kq not in r["name"].lower():
                    continue
                kills_all.append(dict(r, time=datetime.fromtimestamp(r["ts"]).strftime("%I:%M %p"), time_full=datetime.fromtimestamp(r["ts"]).strftime("%b - %d - %I:%M %p"), n=i))
            kills_all.reverse()
            kills_all = kills_all[:20]
            hist_total = len(self.history)

            tracked_set = set(self.lifetime["tracked"])
            recency = sorted(self.mob_last_kill, key=lambda x: -self.mob_last_kill[x])[:5]
            if not recency:
                recency = [k for k, _v in sorted(self.lifetime["mobs"].items(),
                                                 key=lambda x: -x[1]["kills"])[:5]]
            rec_set = set(recency)

            def item_stats(k, item):
                life = self._mob_life(k, create=False)
                sess = self.session_drops.get(k, {"kills": 0, "items": {}})
                ld = life["drops"].get(item, {"drops": 0, "qty": 0})
                sd = sess["items"].get(item, {"drops": 0, "qty": 0})
                return ({"kills": sess["kills"], "drops": sd["drops"], "qty": sd["qty"],
                         "pct": round(100 * sd["drops"] / max(1, sess["kills"]), 1) if sess["kills"] else 0},
                        {"kills": life["kills"], "drops": ld["drops"], "qty": ld["qty"],
                         "pct": round(100 * ld["drops"] / max(1, life["kills"]), 1) if life["kills"] else 0})

            tracked_out = []
            for k in self.lifetime["tracked"]:
                life = self._mob_life(k, create=False)
                sess = self.session_drops.get(k, {"kills": 0, "items": {}})
                names = set(life["drops"]) | set(sess["items"])
                items = []
                for name in names:
                    s, l = item_stats(k, name)
                    items.append({"name": name, "sess": s, "life": l})
                items.sort(key=lambda x: -x["life"]["pct"])
                tracked_out.append({"key": k, "mob": k.title(), "recent": k in rec_set,
                                    "zone": life.get("zone", ""),
                                    "sess_kills": sess["kills"], "life_kills": life["kills"],
                                    "items": items})

            drops_out = []
            iq = item_q.strip().lower()
            if iq:
                keys = [k for k in self.lifetime["mobs"]
                        if iq in k or any(iq in n.lower()
                                          for n in self.lifetime["mobs"][k]["drops"])]
                keys.sort(key=lambda x: -self.lifetime["mobs"][x]["kills"])
                keys = keys[:10]
            else:
                keys = recency
            for k in keys:
                sess = self.session_drops.get(k, {"kills": 0, "items": {}})
                life = self._mob_life(k, create=False)
                names = set(life["drops"]) | set(sess["items"])
                items = []
                for name in names:
                    s, l = item_stats(k, name)
                    items.append({"name": name, "session": s["drops"], "session_qty": s["qty"],
                                  "life_drops": l["drops"], "life_qty": l["qty"],
                                  "pct": l["pct"]})
                items.sort(key=lambda x: -x["pct"])
                if iq and iq not in k:
                    items = [i for i in items if iq in i["name"].lower()]
                    if not items:
                        continue
                drops_out.append({"mob": k.title(), "key": k, "tracked": k in tracked_set,
                                  "zone": life.get("zone", ""),
                                  "session_kills": sess["kills"],
                                  "lifetime_kills": life["kills"], "items": items})

            hour_ago = now - 3600
            recent_k = len([t for t in self.kill_times if t >= hour_ago])
            span = min(now - (self.first_ts or now), 3600) or 1
            kph = round(recent_k / (span / 3600), 1) if span >= 60 else recent_k * 60
            elapsed = int((self.last_ts or now) - (self.first_ts or now))
            xp_hr = round(self.xp / max(elapsed, 60) * 3600, 2)
            lvl = self.lifetime.get("level")
            prog = (self.lifetime.get("xp_into") or 0.0) % 100.0
            ups = self.lifetime.get("level_ups") or []
            gaps = [b[0] - a[0] for a, b in zip(ups, ups[1:])
                    if b[1] == a[1] + 1 and 0 < b[0] - a[0] < 3 * 86400]
            avg_gap = (sum(gaps[-5:]) / len(gaps[-5:])) if gaps else None
            to_lvl = to_50 = None
            if lvl is not None:
                if xp_hr and xp_hr > 0:
                    per_lvl = 100.0 / xp_hr * 3600
                elif avg_gap:
                    per_lvl = avg_gap
                else:
                    per_lvl = None
                if per_lvl:
                    to_lvl = int(per_lvl * (100.0 - prog) / 100.0)
                    to_50 = 0 if lvl >= 50 else int(
                        to_lvl + per_lvl * max(0, 50 - lvl - 1))
            leveling = {"level": lvl, "prog": round(prog, 1),
                        "to_lvl_s": to_lvl, "to_50_s": to_50}
            total_heal = sum(h["amt"] for h in self.heals.values())
            life_heal = sum(h["amt"] for h in self.lifetime["heals"].values())
            perf = dict(self.perf)
            try:
                perf["log_mb"] = round(os.path.getsize(self.log_path) / 1048576, 1)
            except OSError:
                pass

            return {"session": {"kills": self.kills, "deaths": self.deaths,
                                "xp": round(self.xp, 2), "xp_hr": xp_hr,
                                "coin": coin_str(self.coin), "kph": kph,
                                "elapsed": elapsed, "total_dmg": total_dmg,
                                "active": int(active),
                                "dps": round(total_dmg / active, 1)},
                    "deaths_all": self.lifetime["totals"]["deaths"],
                    "death_log": self.death_log,
                    "death_log_all": self.lifetime["deaths_log"],
                    "current_combat": cur, "last_combat": last,
                    "kills": kills_out, "kills_all": kills_all,
                    "hist_total": hist_total,
                    "skills": split_crit(skill_rows(self.skills, active))[0],
                    "skills_crit": split_crit(skill_rows(self.skills, active))[1],
                    "skills_total": split_crit(skill_rows(self.lifetime["skills"], life_span))[0],
                    "skills_total_crit": split_crit(skill_rows(self.lifetime["skills"], life_span))[1],
                    "heals": split_crit(heal_rows(self.heals, active))[0],
                    "heals_crit": split_crit(heal_rows(self.heals, active))[1],
                    "heals_total": split_crit(heal_rows(self.lifetime["heals"], life_span))[0],
                    "heals_total_crit": split_crit(heal_rows(self.lifetime["heals"], life_span))[1],
                    "heal_total": {"amt": total_heal, "hps": round(total_heal / active, 1)},
                    "heal_total_all": {"amt": life_heal,
                                       "hps": round(life_heal / life_span, 1)},
                    "tracked": tracked_out,
                    "totals": {"coin": coin_str(self.lifetime["totals"]["coin"]),
                               "play_s": int(self.play_base + self.active_s)},
                    "leveling": leveling,
                    "drops": drops_out, "perf": perf, "following": following,
                    "zone": self.current_zone,
                    "stats": dict(self.stats),
                    "quests": [dict(v, key=k, state=v.get("state", "open"))
                               for k, v in self.quests["npcs"].items()],
                    "pet": {"skills": build_skill_rows(self.pet_skills, active),
                            "taken": build_in_rows(self.pet_taken),
                            "dmg": sum(v["dmg"] for v in self.pet_skills.values()),
                            "taken_total": sum(v["dmg"] for v in self.pet_taken.values())},
                    "version": VERSION,
                    "log": os.path.basename(self.log_path)}

# ---------------------------------------------------------------- tail
class Tailer(threading.Thread):
    def __init__(self, tracker, path, tail_only=False):
        super().__init__(daemon=True)
        self.t, self.path, self.tail_only = tracker, path, tail_only
        self.following = False
        self.stop_evt = threading.Event()

    def run(self):
        try:
            self._run()
        finally:
            self.t.save_lifetime()

    def _run(self):
        offset = self.t.lifetime["file_offsets"].get(self.t.log_path, 0)
        srcname = os.path.basename(self.t.log_path)
        if (offset > 0 and not self.tail_only
                and not self.t.lifetime["history_built"].get(self.t.log_path)):
            # one-time backfill: rebuild kill history from the already-consumed
            # part of the log without touching lifetime aggregates
            self.t.perf["history"] = "building"
            t0 = time.time()
            ht = Tracker(self.t.lifetime_path, self.t.log_path, no_persist=True)
            try:
                done = 0
                with open(self.path, "rb") as f:
                    rem = b""
                    while done < offset and not self.stop_evt.is_set():
                        chunk = f.read(min(262144, offset - done))
                        if not chunk:
                            break
                        done += len(chunk)
                        rem += chunk
                        if b"\n" in rem:
                            *lines, rem = rem.split(b"\n")
                            for ln in lines:
                                ht.feed(ln.decode("latin-1", "replace"))
                with self.t.lock:
                    keep = [r for r in self.t.history if r.get("src") != srcname]
                    self.t.history = sorted(keep + ht.history,
                                            key=lambda r: r.get("ts", 0))
                    self.t.lifetime["history_built"][self.t.log_path] = True
                self.t.rewrite_history()
                self.t.perf["history"] = "rebuilt %d kills in %.1fs" % (
                    len(ht.history), time.time() - t0)
            except Exception as e:
                self.t.perf["history"] = "backfill failed: %r" % e
        else:
            self.t.lifetime["history_built"][self.t.log_path] = True
        buf = b""
        fh = None
        last_save = time.time()
        t0 = time.time()
        while not self.stop_evt.is_set():
            try:
                if fh is None:
                    fh = open(self.path, "rb")
                    size = os.path.getsize(self.path)
                    if self.tail_only:
                        offset = size
                    elif offset > size:
                        offset = 0
                    fh.seek(offset)
                chunk = fh.read(65536)
                if chunk:
                    buf += chunk
                    offset += len(chunk)
                    if b"\n" in buf:
                        *lines, buf = buf.split(b"\n")
                        self.t.current_offset = offset - len(buf)
                        tb = time.perf_counter()
                        for ln in lines:
                            self.t.feed(ln.decode("latin-1", "replace"))
                        if self.following:
                            self.t.perf["batch_ms"] = round(
                                (time.perf_counter() - tb) * 1000, 1)
                            self.t.perf["batch_lines"] = len(lines)
                else:
                    if not self.following:
                        self.following = True
                        self.t.perf["backlog_s"] = round(time.time() - t0, 2)
                        self.t.save_lifetime()
                        last_save = time.time()
                    if os.path.getsize(self.path) < offset:
                        fh.close(); fh = None; offset = 0
                        continue
                    if time.time() - last_save > 10:
                        self.t.save_lifetime(offset)
                        last_save = time.time()
                    self.stop_evt.wait(0.5)
            except FileNotFoundError:
                self.following = True
                self.stop_evt.wait(2)
            except Exception:
                self.stop_evt.wait(1)

# ---------------------------------------------------------------- web ui
def _page(view):
    cls = "" if view == "all" else " class='nowrap'"
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>EQL Hunting Log</title><style>" + CSS + "</style></head>"
            "<body" + cls + ">" + dash_body(view) + "<script>" + JS + "</script></body></html>")

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&display=swap');
:root{--bg:#0d1017;--panel:#151a24;--edge:#2a3242;--gold:#c9a85c;--goldD:#8a7440;
--red:#b03a3a;--tx:#d8d4c8;--dim:#8891a0;--grn:#6fae6f}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 50% -10%,#1a2130 0%,var(--bg) 60%);
color:var(--tx);font:14px/1.45 'Segoe UI',system-ui,sans-serif;padding:16px}
.disp{font-family:'Cinzel',Georgia,serif;letter-spacing:.06em}
h1{font-size:24px;color:var(--gold);text-align:center;margin:0}
.sub{text-align:center;color:var(--goldD);font-size:11px;text-transform:uppercase;letter-spacing:.1em}
.rule{height:1px;background:linear-gradient(90deg,transparent,var(--goldD),transparent);max-width:420px;margin:10px auto 16px}
.statbar{display:flex;flex-wrap:wrap;gap:8px;max-width:2400px;margin:0 auto 6px}
.stat{flex:1;min-width:100px;background:var(--panel);border:1px solid var(--edge);border-radius:6px;padding:8px 6px;text-align:center}
.stat[data-click]{cursor:pointer}.stat[data-click]:hover{border-color:var(--goldD)}
.stat .v{font-family:'Cinzel',Georgia,serif;font-size:19px}.stat .l{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.08em;margin-top:2px}
.stat .hint{font-size:8px;color:var(--goldD);letter-spacing:.06em}
.perfline{max-width:2400px;margin:0 auto 12px;font-size:11px;color:#5a6272;text-align:center}
.perfline .warn{color:var(--gold)}.perfline .bad{color:#d06a4a}
.grid{display:grid;grid-template-columns:repeat(7,1fr);gap:12px;max-width:2400px;margin:0 auto;align-items:start}
@media(max-width:1900px){.grid{grid-template-columns:repeat(4,1fr)}}
@media(max-width:1250px){.grid{grid-template-columns:1fr 1fr}}
@media(max-width:700px){.grid{grid-template-columns:1fr}}
.itog{cursor:pointer}.itog:hover{color:var(--gold)}
.statsline{font-size:11px;color:var(--dim);margin-top:6px;line-height:1.6}
body.nowrap td,body.nowrap th{white-space:nowrap}
td.src{white-space:nowrap}
.srcsub{font-size:10px;color:var(--dim);line-height:1.2}
.qbracket{color:#7ec8e3}
.wl{color:inherit;text-decoration:underline dotted;text-underline-offset:2px}
.wl:hover{color:var(--gold)}
.grid .panel{margin-bottom:14px}
.panel{background:var(--panel);border:1px solid var(--edge);border-radius:8px;padding:12px 14px}
.panel h2{font-family:'Cinzel',Georgia,serif;font-size:13px;color:var(--gold);margin:0 0 8px;letter-spacing:.08em;text-transform:uppercase}
.panel h2 .tgl{font-size:9px;color:var(--goldD);cursor:pointer;letter-spacing:.05em}
.panel h2 .tgl:hover{color:var(--gold)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{color:var(--dim);text-align:left;font-weight:600;padding:3px 6px;border-bottom:1px solid var(--edge);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
td{padding:4px 6px;border-bottom:1px solid #1d2431;vertical-align:top}
td.r,th.r{text-align:right}.gold{color:var(--gold)}.dim{color:var(--dim)}.grn{color:var(--grn)}.red{color:#d06a4a}
.bar{height:6px;background:#232b3a;border-radius:3px;overflow:hidden;margin-top:3px}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--red),#d06a4a)}
.idle{color:var(--dim);font-style:italic;padding:10px 0}
.search{width:100%;background:#0f141d;border:1px solid var(--edge);border-radius:6px;color:var(--tx);padding:7px 10px;font-size:13px;margin-bottom:8px;outline:none}
.search:focus{border-color:var(--goldD)}.search::placeholder{color:#5a6272}
.mobname{border-bottom:1px dotted var(--goldD);cursor:pointer}.mobname:hover{color:var(--gold)}
input[type=checkbox]{accent-color:#c9a85c;cursor:pointer}
.mtag{font-size:10px;color:var(--dim)}
#modal{display:none;position:fixed;inset:0;background:rgba(5,7,11,.72);z-index:60;align-items:center;justify-content:center;padding:16px}
#modal .panel{max-width:560px;width:100%;max-height:82vh;overflow-y:auto;position:relative}
#mclose{position:absolute;top:8px;right:12px;background:none;border:none;color:var(--dim);font-size:18px;cursor:pointer}
#mclose:hover{color:var(--gold)}
.mbtn{background:var(--panel);border:1px solid var(--edge);color:var(--dim);border-radius:5px;padding:3px 10px;font-size:11px;cursor:pointer}
.mbtn.on{color:var(--gold);border-color:var(--goldD)}
.foot{max-width:2400px;margin:14px auto 0;color:#5a6272;font-size:11px;text-align:center}
.chev{color:var(--goldD);font-size:11px;margin-left:2px}
.phead{cursor:pointer;user-select:none}
.trklabel{font-size:10px;color:var(--dim);cursor:pointer;white-space:nowrap}
"""

def _panel(key, title, inner, tgl_id=None, note=""):
    t = "<span class='tgl' id='%s'></span> " % tgl_id if tgl_id else ""
    return ("<div class='panel' data-pk='%s'><h2 class='phead' data-p='%s'>%s %s"
            "<span class='chev'>&#9662;</span>%s</h2>"
            "<div class='pwrap' data-w='%s'>%s</div></div>"
            % (key, key, title, t, note, key, inner))

PANELS = {
 "cur":  _panel("cur", "Current Combat", "<div id='cur' class='idle'>Waiting for combat...</div>"),
 "last": _panel("last", "Last Combat", "<div id='lastc' class='idle'>Waiting for combat...</div>"),
 "kill": _panel("kill", "Kill Log", "<input class='search' id='kq' placeholder='Search mob name...'><div id='kills'></div>", "hkill"),
 "dmg":  _panel("dmg", "Damage by Skill / Spell", "<div id='skills'></div><div class='statsline' id='dstats'></div>", "hdmg"),
 "heal": _panel("heal", "Healing by Skill / Spell", "<div id='heals'></div>", "hheal"),
 "cdmg": _panel("cdmg", "Critical Damage by Skill / Spell", "<div id='cskills'></div><div class='statsline' id='cdstats'></div>", "hcdmg"),
 "cheal": _panel("cheal", "Critical Healing by Skill / Spell", "<div id='cheals'></div>", "hcheal"),
 "pet":  _panel("pet", "Pet Damage", "<div id='pet'></div>"),
 "ostats": _panel("ostats", "Other Stats", "<div id='ostats'></div>"),
 "trk":  _panel("trk", "Tracked Drops and Kills",
                "<div id='trkn' style='margin-bottom:6px'></div>"
                "<input class='search' id='tq' placeholder='Search tracked mobs or items...'><div id='trk'></div>", "htrk"),
 "drops": _panel("drops", "Drop Rates", "<input class='search' id='iq' placeholder='Search item or mob...'><div id='drops'></div>"),
 "quests": _panel("quests", "Possible Quests", "<div id='quests'></div>"),
 "qclosed": _panel("qclosed", "Closed Quests", "<div id='qclosed'></div>"),
 "qdone": _panel("qdone", "Finished Quests", "<div id='qdone'></div>"),
}
LAYOUTS = {
 "all": [["cur", "last"], ["kill"], ["dmg", "heal"], ["cdmg", "cheal"],
         ["pet", "ostats"], ["trk", "drops"]],
 "combat": [["cur", "last"], ["kill"], ["dmg", "heal"], ["cdmg", "cheal"],
            ["pet", "ostats"]],
 "loot": [["trk"], ["drops"]],
 "quests": [["quests"], ["qclosed", "qdone"]],
}

def dash_body(view):
    cols = LAYOUTS.get(view, LAYOUTS["all"])
    grid = "".join("<div>" + "".join(PANELS[p] for p in col) + "</div>"
                   for col in cols)
    n = len(cols)
    edit = ("<button id='editwin' class='mbtn' style='position:absolute;right:0;top:6px'>"
            "Edit Windows</button>" if view == "all" else "")
    links = " &middot; ".join(
        ("<b>%s</b>" if v == view else "<a href='%s' style='color:var(--goldD)'>%s</a>")
        % ((l,) if v == view else (u, l))
        for v, u, l in (("all", "/", "All"), ("combat", "/combat", "Combat"),
                        ("loot", "/loot", "Loot"), ("quests", "/quests", "Quests")))
    return ("<div style='position:relative;max-width:2400px;margin:0 auto'>"
            "<div class='sub disp'>EverQuest Legends</div>"
            "<h1 class='disp'>Hunting Log</h1>"
            "<div class='sub' style='margin-top:2px'>" + links + "</div>" + edit +
            "</div><div class='rule'></div>"
            "<div class='statbar' id='stats'></div>"
            "<div class='perfline' id='perf'></div>"
            "<div class='grid' id='grid' style='grid-template-columns:repeat(%d,1fr)'>" % n
            + grid + "</div>"
            "<div class='foot' id='foot'></div>"
            "<div id='modal'><div class='panel'><button id='mclose'>&times;</button>"
            "<h2 id='mtitle'></h2><div id='mbody'></div></div></div>"
            "<script>var VIEW='%s';</script>" % view)


JS = r"""
var kq='',iq='',tq='',deb=null,timer=null,killS=[],killA=[],D=null;
var dmgMode=false,healMode=false,trkMode=false,xpMode=false,coinMode=false,deathMode=false,killMode=false,sessMode=false;
var trkN=parseInt(localStorage.getItem('eql_trkN')||'5');
var DEFC={qclosed:1,qdone:1};
function E(id){return document.getElementById(id);}
function setH(id,h){var el=E(id);if(el)el.innerHTML=h;}
function on(id,ev,fn){var el=E(id);if(el)el.addEventListener(ev,fn);}
function fmt(s){var m=Math.floor(s/60),h=Math.floor(m/60);return h?h+'h '+m%60+'m':m+'m '+s%60+'s';}
function esc(x){return String(x).replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function fnum(x){if(typeof x==='number'&&isFinite(x)&&Math.abs(x)>=1e5){return x.toExponential(2).replace('e+','e');}return x;}
function fe(x){return esc(fnum(x));}
function srcName(n){var m=String(n).match(/^([^(]+?)\s*((?:\([^)]*\)\s*)+)$/);
 if(!m)return {b:n,s:''};
 var subs=(m[2].match(/\(([^)]*)\)/g)||[]).map(function(x){return x.slice(1,-1);})
  .map(function(x){return x==='melee'?'Melee':x;});
 return {b:m[1].trim(),s:'('+subs.join(' ')+')'};}
function srcCell(n){var p=srcName(n);
 return "<td class='src'>"+esc(p.b)+(p.s?"<div class='srcsub'>"+esc(p.s)+"</div>":"")+"</td>";}
function wikiURL(n){n=String(n).replace(/\s*->.*$/,'').replace(/\s+x\d+$/,'').replace(/\s\+\d+$/,'');
 n=n.trim();n=n.charAt(0).toUpperCase()+n.slice(1);
 return 'https://eqlwiki.com/index.php/'+encodeURIComponent(n.replace(/ /g,'_'));}
function wl(label,name){return "<a class='wl' target='_blank' rel='noopener' href='"+wikiURL(name||label)+"'>"+esc(label)+"</a>";}
function lootLinks(arr){return arr.map(function(x){return x==='-'?'-':wl(x,x);}).join('<br>');}
function fmtQuest(t){return esc(t).replace(/\[([^\]]*)\]/g,"<span class='qbracket'>[$1]</span>");}
function hook(id,fn){var el=E(id);if(!el)return;
 el.addEventListener('input',function(){fn(el.value);clearTimeout(deb);deb=setTimeout(refresh,250);});}
function openModal(title,html){setH('mtitle',title);setH('mbody',html);E('modal').style.display='flex';}
function dmgTable(rows){if(!rows||!rows.length)return "<div class='idle'>No damage recorded.</div>";
 return "<table><tr><th>Source</th><th class='r'>Dmg</th><th class='r'>%</th><th class='r'>Hits</th><th class='r'>Acc</th><th class='r'>Avg</th><th class='r'>Max</th><th class='r'>DPS</th></tr>"
 +rows.map(function(x){return "<tr>"+srcCell(x.name)+"<td class='r'>"+fe(x.dmg)+"</td><td class='r gold'>"+x.pct
  +"</td><td class='r'>"+fe(x.hits)+(x.miss?"<span class='dim'>/"+fe(x.hits+x.miss)+"</span>":"")
  +"</td><td class='r'>"+(x.acc==null?'-':x.acc+'%')+"</td><td class='r'>"+fe(x.avg)+"</td><td class='r'>"+fe(x.max)
  +"</td><td class='r'>"+fe(x.dps)+"</td></tr>";}).join('')+"</table>";}
function healTable(rows){if(!rows||!rows.length)return "<div class='idle'>No healing recorded.</div>";
 return "<table><tr><th>Source</th><th class='r'>Healed</th><th class='r'>%</th><th class='r'>Count</th><th class='r'>Avg</th><th class='r'>Max</th><th class='r'>HPS</th></tr>"
 +rows.map(function(x){return "<tr>"+srcCell(x.name)+"<td class='r grn'>"+fe(x.amt)+"</td><td class='r gold'>"+x.pct
  +"</td><td class='r'>"+fe(x.count)+"</td><td class='r'>"+fe(x.avg)+"</td><td class='r'>"+fe(x.max)
  +"</td><td class='r'>"+fe(x.hps)+"</td></tr>";}).join('')+"</table>";}
function inTable(rows,miss){var t=(rows&&rows.length)?
 "<table><tr><th>Their attack</th><th class='r'>Dmg</th><th class='r'>Hits</th><th class='r'>Avg</th><th class='r'>Max</th></tr>"
 +rows.map(function(x){return "<tr>"+srcCell(x.name)+"<td class='r red'>"+fe(x.dmg)+"</td><td class='r'>"+fe(x.hits)
  +"</td><td class='r'>"+fe(x.avg)+"</td><td class='r'>"+fe(x.max)+"</td></tr>";}).join('')+"</table>"
 :"<div class='idle'>They never touched you.</div>";
 if(miss)t+="<div class='dim' style='font-size:11px;margin-top:3px'>Missed you "+fe(miss)+" times</div>";
 return t;}
function statsLine(s){if(!s)return'';var seg=[];
 function pair(l,a,b){if((a||0)+(b||0))seg.push(l+" <span class='gold'>"+fnum(a||0)+"</span>/<span class='red'>"+fnum(b||0)+"</span>");}
 pair('miss',s.o_miss,s.d_miss);pair('dodge',s.o_dodge,s.d_dodge);pair('parry',s.o_parry,s.d_parry);
 pair('block',s.o_block,s.d_block);pair('riposte',s.o_riposte,s.d_riposte);
 if(s.riposte_hits)seg.push("rip hits <span class='gold'>"+fnum(s.riposte_hits)+"</span> ("+fnum(s.riposte_dmg||0)+" dmg)");
 pair('DS dmg',s.ds_dealt,s.ds_taken);pair('interrupted',s.int_them,s.int_mine);
 pair('absorbed',s.o_absorb,s.d_absorb);
 if(s.rune_pts)seg.push("rune <span class='grn'>"+fnum(s.rune_pts)+"</span> pts");
 return seg.length?seg.join(' &middot; ')+" <span style='font-size:9px'>(you attacking / against you)</span>":'';}
function encHtml(e,live){
 var mobs=e.mobs.map(function(m){return esc(m.name)+(m.count>1?" &times;"+m.count:"");}).join(', ');
 var badge=e.result==='ongoing'?"":e.result==='cleared'?" <span class='grn'>cleared</span>"
  :e.result==='died'?" <span class='red'>you died</span>":" <span class='dim'>"+esc(e.result)+"</span>";
 var h=(!live&&e.zone?"<div class='gold' style='font-size:11px'>"+esc(e.zone)+"</div>":"")
  +"<div style='font-size:15px;font-weight:600'>"+mobs+badge+"</div>"
  +"<div class='dim' style='font-size:12px;margin:2px 0 8px'>"+e.n+" mob"+(e.n>1?"s":"")+" &middot; "+e.dur+"s &middot; "
  +fe(e.dmg)+" dealt &middot; "+fe(e.taken)+" taken &middot; hit "+e.acc+"% &middot; avoided "+e.avoid+"% &middot; <span class='gold'>"+fe(e.dps)+" DPS</span>"
  +(e.heal_total.amt?" &middot; <span class='grn'>"+fe(e.heal_total.amt)+" healed &middot; "+fe(e.heal_total.hps)+" HPS</span>":"")+"</div>"
  +dmgTable(e.skills);
 if(e.heals.length)h+="<div class='dim' style='font-size:11px;margin:8px 0 2px;text-transform:uppercase;letter-spacing:.05em'>Healing this combat</div>"+healTable(e.heals);
 if(!live&&e.killed.length)h+="<div class='dim' style='font-size:11px;margin:8px 0 2px;text-transform:uppercase;letter-spacing:.05em'>Killed</div>"
  +"<div style='font-size:12px'>"+e.killed.map(function(x){return esc(x.name)+" <span class='dim'>("+fe(x.dmg)+" dmg, "+x.dur+"s"+(x.killer?", by "+esc(x.killer):"")+")</span>";}).join('<br>')+"</div>";
 var sl=statsLine(e.stats);
 if(sl)h+="<div class='statsline'>"+sl+"</div>";
 return h;}
function showDeaths(){
 var list=deathMode?(D.death_log_all||[]):(D.death_log||[]);
 var tg="<div style='margin-bottom:8px'><button class='mbtn"+(deathMode?"":" on")+"' onclick='deathMode=false;showDeaths()'>This session</button> "
  +"<button class='mbtn"+(deathMode?" on":"")+"' onclick='deathMode=true;showDeaths()'>All time</button></div>";
 var body=list.length?list.slice().reverse().map(function(x){
  return "<div style='margin-bottom:12px'><b class='red'>Slain by "+esc(x.killer)+"</b> <span class='dim'>"+esc(x.time)+"</span>"
   +(x.killing_hit?"<div style='font-size:12px;margin-top:2px'>Killing blow: <span class='red'>"+esc(x.killing_hit.label)+"</span> for "+fe(x.killing_hit.dmg)+" by "+esc(x.killing_hit.name)+"</div>":"")
   +"<div class='dim' style='font-size:12px;margin-top:2px'>Took "+fe(x.taken)+" damage in the final fight</div>"
   +(x.engaged&&x.engaged.length?"<div style='font-size:12px;margin-top:3px'>"+x.engaged.map(function(m){
     return esc(m.name)+" <span class='dim'>("+fe(m.taken)+" dmg to you over "+m.dur+"s)</span>";}).join('<br>')+"</div>":"")
   +"</div>";}).join(''):"<div class='idle'>No deaths"+(deathMode?" on record":" this session")+". Fly safe.</div>";
 openModal("Death Report",tg+body);}
function showKill(mode,i){var k=(mode==='a'?killA:killS)[i];if(!k)return;
 var head=(k.zone?"<div class='dim' style='font-size:11px;margin:-4px 0 6px'>"+esc(k.zone)+"</div>":"")
  +"<div class='dim' style='font-size:12px;margin-bottom:8px'>"+k.dur+"s &middot; "+fe(k.dmg)+" dealt &middot; "+fe(k.taken)
  +" taken &middot; <span class='gold'>"+fe(k.dps)+" DPS</span>"+(k.killer?" &middot; killing blow by "+esc(k.killer):"")+"</div>";
 var body=k.detail?
  "<div class='dim' style='font-size:11px;margin:6px 0 2px;text-transform:uppercase;letter-spacing:.05em'>Your damage to them</div>"
  +dmgTable(k.detail.skills)
  +"<div class='dim' style='font-size:11px;margin:10px 0 2px;text-transform:uppercase;letter-spacing:.05em'>Their damage to you</div>"
  +inTable(k.detail.incoming,k.detail.in_miss)
  +((k.detail.pet_in&&k.detail.pet_in.length)?"<div class='dim' style='font-size:11px;margin:10px 0 2px;text-transform:uppercase;letter-spacing:.05em'>Their damage to your pet</div>"+inTable(k.detail.pet_in,0):"")
  :"<div class='idle'>No detailed breakdown was recorded for this kill.</div>";
 body+="<div class='dim' style='font-size:11px;margin:10px 0 2px;text-transform:uppercase;letter-spacing:.05em'>Loot</div>"
  +"<div style='font-size:13px'>"+((k.loot&&k.loot.length&&k.loot[0]!=='-')?lootLinks(k.loot):"<span class='dim'>nothing</span>")+"</div>";
 openModal(wl(k.name,k.name)+" <span class='dim' style='font-size:11px'>"+esc(k.time_full||k.time)+"</span>",head+body);}
function mobSummary(name,zone,sk,lk,items){
 function tbl(mode,kills){return "<div class='dim' style='font-size:11px;margin:8px 0 2px;text-transform:uppercase;letter-spacing:.05em'>"
  +(mode==='s'?'Current session':'Overall')+" &middot; "+fe(kills)+" kills</div>"
  +(items.length?"<table><tr><th>Item</th><th class='r'>Drops</th><th class='r'>Qty</th><th class='r'>Drop %</th></tr>"
   +items.map(function(i){var v=mode==='s'?i.s:i.l;
    return "<tr><td>"+wl(i.name,i.name)+"</td><td class='r'>"+fe(v.drops)+"</td><td class='r dim'>"+fe(v.qty)
     +"</td><td class='r grn'>"+v.pct+"%</td></tr>";}).join('')+"</table>"
   :"<div class='idle'>No drops recorded.</div>");}
 openModal(esc(name)+(zone?" <span class='dim' style='font-size:11px'>"+esc(zone)+"</span>":""),
  tbl('s',sk)+tbl('l',lk));}
function questRow(q,qi){
 var btns="";
 if(q.state==='open')btns="<span class='mobname qact grn' data-key='"+esc(q.key)+"' data-st='done' title='finish'>&#10003;</span> "
   +"<span class='mobname qact' data-key='"+esc(q.key)+"' data-st='closed' data-confirm='1' title='close'>&times;</span>";
 else btns="<span class='mobname qact gold' data-key='"+esc(q.key)+"' data-st='open' title='return to possible'>&#8617;</span>";
 return "<div style='margin-bottom:10px'><span class='mobname qname' data-qi='"+qi+"'>"+esc(q.name)
  +"</span> <span style='float:right'>"+btns+"</span>"
  +"<div class='dim' style='font-size:11px'>"+esc(q.zone||'unknown zone')+" &middot; "+q.texts.length+" line"+(q.texts.length>1?"s":"")+"</div></div>";}
var PANEL_LABELS={cur:'Current Combat',last:'Last Combat',kill:'Kill Log',dmg:'Damage',heal:'Healing',
 cdmg:'Critical Damage',cheal:'Critical Healing',pet:'Pet Damage',ostats:'Other Stats',
 trk:'Tracked Drops and Kills',drops:'Drop Rates'};
function applyHidden(){document.querySelectorAll('[data-pk]').forEach(function(p){
 p.style.display=localStorage.getItem('eql_hide_'+p.getAttribute('data-pk'))==='1'?'none':'';});
 var g=E('grid');if(!g)return;var vis=0;
 Array.prototype.forEach.call(g.children,function(col){
  var any=false;col.querySelectorAll('[data-pk]').forEach(function(p){if(p.style.display!=='none')any=true;});
  col.style.display=any?'':'none';if(any)vis++;});
 if(vis)g.style.gridTemplateColumns='repeat('+vis+',1fr)';}
function applyCollapse(){document.querySelectorAll('.phead').forEach(function(h){
 var p=h.getAttribute('data-p');
 var ls=localStorage.getItem('eql_c_'+p);
 var open=ls===null?!DEFC[p]:ls!=='1';
 var w=document.querySelector(".pwrap[data-w='"+p+"']");
 if(w)w.style.display=open?'':'none';
 var ch=h.querySelector('.chev');
 if(ch)ch.innerHTML=open?'&#9662;':'&#9656;';});}
async function refresh(){
 clearTimeout(timer);
 try{
  var t0=performance.now();
  var d=await (await fetch('/data?kill_q='+encodeURIComponent(kq)+'&item_q='+encodeURIComponent(iq))).json();
  var fetchMs=Math.round(performance.now()-t0);
  D=d;killS=d.kills;killA=d.kills_all||[];
  var s=d.session,ht=d.heal_total||{amt:0,hps:0};
  var st=[
   ['','Session kills',fnum(s.kills),''],
   ['deaths','Deaths',deathMode?d.deaths_all:s.deaths,(deathMode?'all':'session')+' &middot; view'],
   ['','Kills / hr',fnum(s.kph),''],
   ['','Overall DPS',fnum(s.dps),''],
   ['','HPS',fnum(ht.hps),''],
   ['xp','XP',xpMode?(s.xp_hr+'%/hr'):(s.xp+'%'),(xpMode?'per hour':'session')+' &#8645;'],
   ['coin','Coin',coinMode?d.totals.coin:s.coin,(coinMode?'total':'session')+' &#8645;'],
   ['sess','Time',sessMode?fmt((d.totals&&d.totals.play_s)||0):fmt(s.elapsed),(sessMode?'all time':'session')+' &#8645;'],
   ['','To level '+((d.leveling&&d.leveling.level!=null)?(d.leveling.level+1):'?'),
    (d.leveling&&d.leveling.to_lvl_s!=null)?fmt(d.leveling.to_lvl_s):'-',
    (d.leveling&&d.leveling.level!=null)?(d.leveling.prog+'% in'):''],
   ['','To 50',(d.leveling&&d.leveling.to_50_s!=null)?fmt(d.leveling.to_50_s):'-','estimate']];
  setH('stats',st.map(function(x){
   return "<div class='stat'"+(x[0]?" data-click data-key='"+x[0]+"'":"")+"><div class='v'>"+x[2]
    +"</div><div class='l'>"+x[1]+(x[3]?" <span class='hint'>"+x[3]+"</span>":"")+"</div></div>";}).join(''));
  var p=d.perf||{},mb=p.log_mb||0;
  var warn=mb>200?"<span class='bad'>log is very large - truncate it soon</span>":mb>50?"<span class='warn'>log growing large - consider truncating</span>":"";
  setH('perf',"Log "+mb+" MB"
   +(p.backlog_s!=null?" &middot; backlog parse "+p.backlog_s+"s":"")
   +(p.history?" &middot; history: "+esc(p.history):"")
   +(p.batch_lines?" &middot; last batch "+p.batch_lines+" lines / "+p.batch_ms+" ms":"")
   +(p.snapshot_ms!=null?" &middot; snapshot "+p.snapshot_ms+" ms":"")
   +" &middot; fetch "+fetchMs+" ms"+(warn?" &middot; "+warn:""));
  var cur=E('cur');
  if(cur){if(d.current_combat){cur.className='';cur.innerHTML=encHtml(d.current_combat,true);}
   else{cur.className='idle';cur.textContent=d.following?'Waiting for combat...':'Log parsed - not live';}}
  var lc=E('lastc');
  if(lc){if(d.last_combat){lc.className='';lc.innerHTML=encHtml(d.last_combat,false);}
   else{lc.className='idle';lc.textContent='Waiting for combat...';}}
  if(E('hkill')){E('hkill').textContent=(killMode?'(overall)':'(session)')+' \u21c5';
   var kl=killMode?killA:killS;
   var kmsg=kq?('No kills match \"'+esc(kq)+'\".'):(killMode?'No kills on record yet.':'No kills yet this session.');
   setH('kills',kl.length?
    "<table><tr><th>#</th><th>Mob</th><th>Time</th><th class='r'>Fight</th><th class='r'>Dmg</th><th class='r'>DPS</th><th>Loot</th></tr>"
    +kl.map(function(k,i){return "<tr><td class='dim'>"+k.n+"</td><td><span class='mobname' data-m='"+(killMode?'a':'s')+"' data-i='"+i+"'>"+esc(k.name)+"</span>"
      +(k.killer?"<div class='mtag'>by "+esc(k.killer)+"</div>":"")+"</td><td class='dim'>"+esc(k.time)
      +"</td><td class='r'>"+k.dur+"s</td><td class='r'>"+fe(k.dmg)+"</td><td class='r gold'>"+fe(k.dps)
      +"</td><td>"+((k.loot&&k.loot.length)?lootLinks(k.loot):'-')+"</td></tr>";}).join('')+"</table>"
    +(kl.length>=20?"<div class='dim' style='font-size:11px;margin-top:4px'>Showing last 20"+(kq?' matches':'')+(killMode?' of '+fe(d.hist_total||0)+' recorded kills':' kills')+"</div>":"")
    :"<div class='idle'>"+kmsg+"</div>");}
  if(E('hdmg')){E('hdmg').textContent=(dmgMode?'(total)':'(session)')+' \u21c5';
   setH('skills',dmgTable(dmgMode?d.skills_total:d.skills));
   setH('dstats',statsLine(d.stats));}
  if(E('hcdmg')){E('hcdmg').textContent=(dmgMode?'(total)':'(session)')+' \u21c5';
   setH('cskills',dmgTable(dmgMode?d.skills_total_crit:d.skills_crit));
   setH('cdstats',statsLine(d.stats));}
  if(E('hheal')){E('hheal').textContent=(healMode?'(total)':'(session)')+' \u21c5';
   var hh=healMode?(d.heal_total_all||{amt:0,hps:0}):ht;
   setH('heals',"<div class='dim' style='font-size:12px;margin-bottom:6px'>Total healed <span class='grn'>"+fe(hh.amt)+"</span> &middot; "+fe(hh.hps)+" HPS</div>"
    +healTable(healMode?d.heals_total:d.heals));}
  if(E('hcheal')){E('hcheal').textContent=(healMode?'(total)':'(session)')+' \u21c5';
   setH('cheals',healTable(healMode?d.heals_total_crit:d.heals_crit));}
  var pt=d.pet||{skills:[],taken:[],dmg:0,taken_total:0};
  setH('pet',(pt.skills.length||pt.taken.length)?
   "<div class='dim' style='font-size:12px;margin-bottom:6px'>Dealt <span class='gold'>"+fe(pt.dmg)+"</span> &middot; Taken <span class='red'>"+fe(pt.taken_total)+"</span></div>"
   +(pt.skills.length?dmgTable(pt.skills):"")
   +(pt.taken.length?"<div class='dim' style='font-size:11px;margin:8px 0 2px;text-transform:uppercase;letter-spacing:.05em'>Damage taken by pet</div>"+inTable(pt.taken,0):"")
   :"<div class='idle'>No pet activity this session.</div>");
  var os=d.stats||{};
  function orow(l,a,b){return "<tr><td>"+l+"</td><td class='r gold'>"+fnum(a||0)+"</td><td class='r red'>"+fnum(b||0)+"</td></tr>";}
  setH('ostats',"<table><tr><th>Outcome</th><th class='r'>You attacking</th><th class='r'>Against you</th></tr>"
   +orow('Miss',os.o_miss,os.d_miss)+orow('Dodge',os.o_dodge,os.d_dodge)
   +orow('Parry',os.o_parry,os.d_parry)+orow('Block',os.o_block,os.d_block)
   +orow('Riposte',os.o_riposte,os.d_riposte)+orow('Absorbed (skin)',os.o_absorb,os.d_absorb)
   +orow('Damage shield dmg',os.ds_dealt,os.ds_taken)
   +orow('Interrupted casts',os.int_them,os.int_mine)+"</table>"
   +"<div class='statsline'>Riposte hits landed: <span class='gold'>"+fnum(os.riposte_hits||0)
   +"</span> ("+fnum(os.riposte_dmg||0)+" dmg) &middot; Rune absorbed: <span class='grn'>"
   +fnum(os.rune_pts||0)+"</span> pts over "+fnum(os.rune_hits||0)+" runes</div>");
  if(E('trk')){E('htrk').textContent=(trkMode?'(overall)':'(session)')+' \u21c5';
   setH('trkn',[5,10,20].map(function(n){return "<button class='mbtn tnb"+(trkN===n?" on":"")+"' data-n='"+n+"'>"+n+"</button>";}).join(' '));
   var all=(d.tracked||[]);
   var tl=tq?all.filter(function(t){var hay=(t.mob+' '+t.items.map(function(i){return i.name;}).join(' ')).toLowerCase();
     return hay.indexOf(tq.toLowerCase())>=0;}):all.slice(0,trkN);
   setH('trk',all.length?
    (tl.length?tl.map(function(t,ti){
      var open=localStorage.getItem('eql_tc_'+t.key)!=='1';
      return "<div style='margin-bottom:10px'><b class='mobname msum' data-src='t' data-i='"+all.indexOf(t)+"'>"+esc(t.mob)
       +"</b> <span class='dim'>"+fe(trkMode?t.life_kills:t.sess_kills)+" kills"
       +(trkMode?' overall':' this session')+"</span> <span class='mobname untrack' data-mob='"+esc(t.key)+"' style='float:right'>&times;</span>"
       +(t.zone?"<div class='dim' style='font-size:10px'>"+esc(t.zone)+"</div>":"")
       +(t.items.length?"<table><tr><th class='itog' data-k='tc_"+esc(t.key)+"'>Item "+(open?"&#9662;":"&#9656;")+"</th><th class='r'>Drops</th><th class='r'>Qty</th><th class='r'>Drop %</th></tr>"
        +(open?t.items.map(function(i){var v=trkMode?i.life:i.sess;
         return "<tr><td>"+wl(i.name,i.name)+"</td><td class='r'>"+fe(v.drops)+"</td><td class='r dim'>"+fe(v.qty)
          +"</td><td class='r grn'>"+v.pct+"%</td></tr>";}).join(''):"")+"</table>"
        :"<div class='idle' style='padding:4px 0'>No drops recorded yet.</div>")+"</div>";}).join('')
     +(tq?"":"<div class='dim' style='font-size:11px'>Showing first "+Math.min(trkN,all.length)+" of "+all.length+" tracked - search to see all</div>")
    :"<div class='idle'>"+(tq?'No tracked mobs match.':'Nothing tracked yet.')+"</div>")
    :"<div class='idle'>Nothing tracked yet - tick the checkbox next to a mob in Drop Rates.</div>");}
  if(E('drops')){var dmsg=iq?('No drops match \"'+esc(iq)+'\".'):'No drops recorded yet.';
   setH('drops',d.drops.length?
    d.drops.map(function(m,mi){var dopen=localStorage.getItem('eql_dc_'+m.key)!=='1';
      return "<div style='margin-bottom:10px'><b class='mobname msum' data-src='d' data-i='"+mi+"'>"+esc(m.mob)+"</b> <span class='dim'>"
      +fe(m.session_kills)+" kills this session &middot; "+fe(m.lifetime_kills)+" lifetime</span>"
      +" <label class='trklabel'><input type='checkbox' data-mob='"+esc(m.key)+"'"+(m.tracked?" checked":"")+"> track</label>"
      +(m.zone?"<div class='dim' style='font-size:10px'>"+esc(m.zone)+"</div>":"")
      +"<table><tr><th class='itog' data-k='dc_"+esc(m.key)+"'>Item "+(dopen?"&#9662;":"&#9656;")+"</th><th class='r'>Session</th><th class='r'>Lifetime</th><th class='r'>Drop %</th></tr>"
      +(dopen?m.items.map(function(i){return "<tr><td>"+wl(i.name,i.name)+"</td><td class='r'>"+fe(i.session)
        +"</td><td class='r dim'>"+fe(i.life_drops)+"/"+fe(m.lifetime_kills)+"</td><td class='r grn'>"+i.pct+"%</td></tr>";}).join(''):"")
      +"</table></div>";}).join('')
    +(iq?"":"<div class='dim' style='font-size:11px'>Showing your 5 most recent hunts - search to see any mob or item</div>")
    :"<div class='idle'>"+dmsg+"</div>");}
  var qs=D.quests||[];
  function qpanel(id,state,empty){if(!E(id))return;
   var rows=[];qs.forEach(function(q,qi){if((q.state||'open')===state)rows.push(questRow(q,qi));});
   setH(id,rows.length?rows.join(''):"<div class='idle'>"+empty+"</div>");}
  qpanel('quests','open',"No quest givers spotted yet. Hail NPCs - bracketed [words] mark a possible quest.");
  qpanel('qclosed','closed',"No closed quests.");
  qpanel('qdone','done',"No finished quests.");
  setH('foot','v'+(d.version||'')+' - '+(d.following?'LIVE - tailing ':'Parsed ')+d.log
   +' - overlay for OBS at /overlay - lifetime data in eql_lifetime_stats.json, kill history in eql_kill_history.jsonl');
 }catch(e){}
 timer=setTimeout(refresh,1000);
}
hook('kq',function(v){kq=v;});
hook('iq',function(v){iq=v;});
on('tq','input',function(){tq=this.value;clearTimeout(deb);deb=setTimeout(refresh,150);});
on('stats','click',function(e){
 var c=e.target.closest('[data-key]');if(!c)return;
 var k=c.getAttribute('data-key');
 if(k==='deaths'){showDeaths();}
 else if(k==='xp'){xpMode=!xpMode;refresh();}
 else if(k==='coin'){coinMode=!coinMode;refresh();}
 else if(k==='sess'){sessMode=!sessMode;refresh();}});
on('hdmg','click',function(){dmgMode=!dmgMode;refresh();});
on('hcdmg','click',function(){dmgMode=!dmgMode;refresh();});
on('hheal','click',function(){healMode=!healMode;refresh();});
on('hcheal','click',function(){healMode=!healMode;refresh();});
on('htrk','click',function(){trkMode=!trkMode;refresh();});
on('hkill','click',function(){killMode=!killMode;refresh();});
on('trkn','click',function(e){var b=e.target.closest('.tnb');if(!b)return;
 trkN=parseInt(b.getAttribute('data-n'));localStorage.setItem('eql_trkN',trkN);refresh();});
on('grid','click',function(e){
 var h=e.target.closest('.phead');if(!h)return;
 if(e.target.closest('.tgl'))return;
 var p=h.getAttribute('data-p');
 var ls=localStorage.getItem('eql_c_'+p);
 var open=ls===null?!DEFC[p]:ls!=='1';
 localStorage.setItem('eql_c_'+p,open?'1':'0');
 applyCollapse();});
on('kills','click',function(e){
 var c=e.target.closest('.mobname');if(c&&c.hasAttribute('data-i'))showKill(c.getAttribute('data-m'),parseInt(c.getAttribute('data-i')));});
function msumHandler(e){var c=e.target.closest('.msum');if(!c)return;
 var i=parseInt(c.getAttribute('data-i'));
 if(c.getAttribute('data-src')==='t'){var t=(D.tracked||[])[i];if(!t)return;
  mobSummary(t.mob,t.zone,t.sess_kills,t.life_kills,
   t.items.map(function(x){return {name:x.name,s:x.sess,l:x.life};}));}
 else{var m=(D.drops||[])[i];if(!m)return;
  mobSummary(m.mob,m.zone,m.session_kills,m.lifetime_kills,
   m.items.map(function(x){return {name:x.name,
    s:{drops:x.session,qty:x.session_qty,pct:m.session_kills?Math.round(1000*x.session/m.session_kills)/10:0},
    l:{drops:x.life_drops,qty:x.life_qty,pct:x.pct}};}));}}
function itogHandler(e){var c=e.target.closest('.itog');if(!c)return;
 var k='eql_'+c.getAttribute('data-k');
 localStorage.setItem(k,localStorage.getItem(k)==='1'?'0':'1');refresh();}
on('drops','click',function(e){itogHandler(e);msumHandler(e);});
on('trk','click',function(e){
 var u=e.target.closest('.untrack');
 if(u){fetch('/track?mob='+encodeURIComponent(u.getAttribute('data-mob'))+'&on=0').then(refresh);return;}
 itogHandler(e);msumHandler(e);});
on('drops','change',function(e){
 var c=e.target;if(c.type!=='checkbox')return;
 fetch('/track?mob='+encodeURIComponent(c.getAttribute('data-mob'))+'&on='+(c.checked?1:0)).then(refresh);});
function questsHandler(e){
 var a=e.target.closest('.qact');
 if(a){var stt=a.getAttribute('data-st');
  if(a.getAttribute('data-confirm')&&!confirm('Close this quest? It will move to Closed Quests.'))return;
  fetch('/quest_state?key='+encodeURIComponent(a.getAttribute('data-key'))+'&state='+stt).then(refresh);return;}
 var n=e.target.closest('.qname');
 if(n){var q=(D.quests||[])[parseInt(n.getAttribute('data-qi'))];if(!q)return;
  openModal(esc(q.name)+" <span class='dim' style='font-size:11px'>"+esc(q.zone||'')+"</span>",
   q.texts.map(function(t){return "<p style='font-size:13px;margin:6px 0'>"+fmtQuest(t)+"</p>";}).join('')
   ||"<div class='idle'>No dialogue captured.</div>");}}
on('quests','click',questsHandler);
on('qclosed','click',questsHandler);
on('qdone','click',questsHandler);
on('editwin','click',function(){
 openModal('Edit Windows',"<div class='dim' style='font-size:12px;margin-bottom:8px'>Untick a window to hide it on this dashboard.</div>"
  +Object.keys(PANEL_LABELS).map(function(k){
   var vis=localStorage.getItem('eql_hide_'+k)!=='1';
   return "<label style='display:block;font-size:13px;margin:4px 0'><input type='checkbox' class='ewbox' data-pk='"+k+"'"+(vis?" checked":"")+"> "+PANEL_LABELS[k]+"</label>";}).join(''));});
on('mbody','change',function(e){var c=e.target;
 if(!c.classList||!c.classList.contains('ewbox'))return;
 localStorage.setItem('eql_hide_'+c.getAttribute('data-pk'),c.checked?'0':'1');
 applyHidden();});
on('mclose','click',function(){E('modal').style.display='none';});
on('modal','click',function(e){if(e.target.id==='modal')E('modal').style.display='none';});
if(VIEW!=='all'){}
applyHidden();
applyCollapse();
refresh();
"""

OVERLAY = r"""<!doctype html><html><head><meta charset='utf-8'><title>EQL Overlay</title>
<style>
body{margin:0;background:transparent;font-family:'Segoe UI',sans-serif;color:#e8e2d5;
 text-shadow:0 1px 3px rgba(0,0,0,.9);overflow:hidden}
.wrap{display:inline-block;padding:10px 16px;background:rgba(13,16,23,.55);border-radius:8px}
.row{display:flex;gap:18px}
.cell .v{font-family:Georgia,serif;font-size:24px;font-weight:700;color:#d4af37;line-height:1}
.cell .l{font-size:9px;color:#8a93a5;text-transform:uppercase;letter-spacing:.08em;margin-top:2px}
.zone{color:#d4af37;font-weight:600;font-size:13px;margin-top:6px}
.sh{font-size:9px;color:#8a6f2f;text-transform:uppercase;letter-spacing:.08em;margin-top:8px}
.tog{color:#d4af37;cursor:pointer;font-size:13px;font-weight:700;margin-left:6px}
.cmb{font-family:Consolas,monospace;font-size:12px;white-space:pre;color:#e8e2d5}
.dim{color:#8a93a5}
</style></head><body><div class='wrap'>
<div class='row' id='cells'></div>
<div class='zone' id='zone'></div>
<div class='sh'>CURRENT COMBAT<span class='tog' id='tcur'></span></div>
<div class='cmb' id='cur'></div>
<div class='sh'>LAST COMBAT<span class='tog' id='tlast'></span></div>
<div class='cmb' id='last'></div>
</div>
<script>
function esc(x){return String(x).replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function fn(x){if(typeof x==='number'&&isFinite(x)&&Math.abs(x)>=1e5)return x.toExponential(2).replace('e+','e');return x;}
function fmt(s){var m=Math.floor(s/60),h=Math.floor(m/60);return h?h+'h '+m%60+'m':m+'m '+s%60+'s';}
function one(n){var m=String(n).match(/^([^(]+?)\s*((?:\([^)]*\)\s*)+)$/);
 if(!m)return String(n);
 var p=(m[2].match(/\(([^)]*)\)/g)||[]).map(function(x){return x.slice(1,-1);})
  .map(function(x){return x==='melee'?'Melee':x;});
 return m[1].trim()+' ('+p.join(' ')+')';}
function pad(s,w){s=String(s);return s.length>=w?s.slice(0,w):s+Array(w-s.length+1).join(' ');}
function rpad(s,w){s=String(s);return s.length>=w?s:Array(w-s.length+1).join(' ')+s;}
var col={cur:localStorage.getItem('eqlo_cur')==='1',last:localStorage.getItem('eqlo_last')==='1'};
function tglr(){document.getElementById('tcur').textContent=col.cur?'+':'\u2212';
 document.getElementById('tlast').textContent=col.last?'+':'\u2212';
 document.getElementById('cur').style.display=col.cur?'none':'';
 document.getElementById('last').style.display=col.last?'none':'';}
document.getElementById('tcur').onclick=function(){col.cur=!col.cur;localStorage.setItem('eqlo_cur',col.cur?'1':'0');tglr();};
document.getElementById('tlast').onclick=function(){col.last=!col.last;localStorage.setItem('eqlo_last',col.last?'1':'0');tglr();};
tglr();
function encText(e,live){
 if(!e)return "<span class='dim'>Waiting for combat...</span>";
 var mobs=e.mobs.map(function(m){return esc(m.name)+(m.count>1?' x'+m.count:'');}).join(', ');
 var badge=e.result==='ongoing'?'':e.result==='cleared'?'  [cleared]':e.result==='died'?'  [YOU DIED]':'  ['+esc(e.result)+']';
 var out=[(!live&&e.zone?'['+esc(e.zone)+']\n':'')+mobs+badge,
  e.dur+'s - '+fn(e.dmg)+' dealt - '+fn(e.taken)+' taken - hit '+e.acc+'% - avoided '+e.avoid+'% - '+fn(e.dps)+' DPS'];
 if(e.skills&&e.skills.length){
  out.push(' '+pad('SOURCE',24)+' '+rpad('DMG',7)+' '+rpad('ACC',5)+' '+rpad('MAX',8)+' '+rpad('DPS',8));
  e.skills.slice(0,6).forEach(function(r){
   out.push(' '+pad(one(r.name),24)+' '+rpad(fn(r.dmg),7)+' '+rpad(r.acc==null?'-':r.acc+'%',5)
    +' '+rpad(fn(r.max),8)+' '+rpad(fn(r.dps),8));});
  if(e.skills.length>6)out.push(' ... '+(e.skills.length-6)+' more sources');}
 if(!live&&e.killed&&e.killed.length)
  out.push(' killed: '+e.killed.slice(0,4).map(function(x){return esc(x.name);}).join(', ')
   +(e.killed.length>4?' +'+(e.killed.length-4)+' more':''));
 return out.join('\n');}
async function tick(){
 try{
  var d=await (await fetch('/data')).json();
  var s=d.session,lv=d.leveling||{};
  var cells=[['KILLS',fn(s.kills)],['KILLS/HR',fn(s.kph)],['XP/HR',s.xp_hr+'%'],
   ['COIN (SESSION)',s.coin],['DPS',fn(s.dps)],['SESSION',fmt(s.elapsed)],
   ['TO LVL',lv.to_lvl_s!=null?fmt(lv.to_lvl_s):'-'],['TO 50',lv.to_50_s!=null?fmt(lv.to_50_s):'-']];
  document.getElementById('cells').innerHTML=cells.map(function(c){
   return "<div class='cell'><div class='v'>"+c[1]+"</div><div class='l'>"+c[0]+"</div></div>";}).join('');
  document.getElementById('zone').textContent=d.zone||'';
  if(!col.cur)document.getElementById('cur').innerHTML=encText(d.current_combat,true);
  if(!col.last)document.getElementById('last').innerHTML=encText(d.last_combat,false);
 }catch(e){}
 setTimeout(tick,1000);}
tick();
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    tracker = None
    tailer = None
    def log_message(self, *a): pass
    def _send(self, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        q = lambda k: qs.get(k, [""])[0]
        if u.path == "/data":
            t0 = time.perf_counter()
            snap = self.tracker.snapshot(self.tailer.following,
                                         kill_q=q("kill_q"), item_q=q("item_q"))
            snap["perf"]["snapshot_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            self._send(json.dumps(snap), "application/json")
        elif u.path == "/track":
            self.tracker.set_tracked(q("mob"), q("on") == "1")
            self._send('{"ok":true}', "application/json")
        elif u.path == "/quest_state":
            self.tracker.quest_set_state(q("key"), q("state"))
            self._send('{"ok":true}', "application/json")
        elif u.path == "/overlay":
            self._send(OVERLAY)
        elif u.path == "/combat":
            self._send(_page("combat"))
        elif u.path == "/loot":
            self._send(_page("loot"))
        elif u.path == "/quests":
            self._send(_page("quests"))
        else:
            self._send(_page("all"))


RELEASE_NOTES = [
 ("h", "SECURITY CONCERNS"),
 ("", "This note stays pinned at the top so it is always the first thing you "
      "read: this app does not currently make any calls outside of your "
      "computer. The dashboard and overlays are private and local "
      "(127.0.0.1 only). The one exception is optional setup tooling - if "
      "you choose to build an .exe, pip fetches PyInstaller for you; the "
      "tracker itself needs nothing installed and phones nowhere. Item and "
      "mob names on the dashboard link to eqlwiki.com, but those pages only "
      "load if you click them. The app is meant to be fully stand-alone. A "
      "future version may offer uploading drop data, and those builds will "
      "be clearly labeled - something like \"Stand Alone\" and "
      "\"Stand Alone with DB logging\"."),
 ("h", "TROUBLESHOOTING"),
 ("b", "1. Turn logging on"),
 ("", "The parser reads the game's log file, so type /log on in game. Turn "
      "it off any time with /log off. Default location on Windows 11:\n"
      "C:\\Users\\Public\\Daybreak Game Company\\Installed Games\\"
      "EverQuest Legends\\Logs"),
 ("b", "2. Overlay feels sluggish when the game is unfocused"),
 ("", "Adjust your background FPS in the Alt+O options. That keeps the game "
      "from dropping to very low FPS while you interact with the overlay."),
 ("b", "3. Log size and latency"),
 ("", "The dashboard shows the log size - orange at 50 MB, red at 200 MB. "
      "Log management is now built in: the Archive button zips the log into "
      "a Log Archive folder (name + date stamp) and starts it fresh, and "
      "Truncate strips a chat channel out of the log (with an optional "
      "backup zip first). Either way the app's data files retain your drop "
      "rates, kill counts, and recorded combat breakdowns; only re-scanning "
      "the removed text is lost. Both are best done with the game closed or "
      "after /log off."),
 ("b", "4. Keep the log small (optional)"),
 ("", "General and Newplayers chat are written to the log. You can /leave "
      "general and /leave newplayers with a macro, or just use the Truncate "
      "button now and then. Splitting channel chat into its own files - so "
      "you could keep a chat history - may come in a future update."),
 ("b", "5. Sessions"),
 ("", "The first time you target your log file, the app loads its entire "
      "history. Clicking Stop then Start begins a new session, and Archive, "
      "Truncate, and Rebuild Data do the same (lifetime data always carries "
      "forward)."),
 ("b", "6. Four dashboards"),
 ("", "All has everything, with an Edit Windows button at the top right to "
      "pick exactly which panels you see - hidden columns recenter the "
      "rest. Combat, Loot, and Quests are premade views with special rules "
      "like no word wrapping. The Features button on the app lists "
      "everything the tracker does."),
 ("b", "7. Resolution"),
 ("", "This was designed under 4K resolution; it has not been tested at "
      "1080p or 1440p."),
 ("h", "VERSION HISTORY"),
 ("", """# EQL Hunting Log - Changelog

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
"""),
]

FEATURES = [
 ('', ''),
 ('h', 'DASHBOARDS'),
 ('', '- Four dashboards: All (everything), Combat, Loot, and Quests — switchable'),
 ('', '  from the app or the links under the title.'),
 ('', '- Edit Windows button (All view): show/hide any panel; emptied columns'),
 ('', '  collapse and the rest recenter automatically.'),
 ('', '- Every panel collapsible with per-panel memory; Combat and Loot views'),
 ('', '  never word-wrap; source names never wrap anywhere, with parenthetical'),
 ('', '  tags merged below the name ("Slash" over "(Melee Crit)").'),
 ('', '- Stat bar: session kills, deaths (session/all + death reports with'),
 ('', '  killing blow), kills/hr, overall DPS, HPS, XP (session/per-hour),'),
 ('', '  coin (session/total), time (session/all-time), time to next level with'),
 ('', '  % into level, and time to 50.'),
 ('', ''),
 ('h', 'COMBAT TRACKING'),
 ('', '- Encounter-based Current and Last Combat: overlapping fights merge, AoE'),
 ('', '  attributed correctly; zone shown on Last Combat; hit% and avoided% in'),
 ('', '  the meta line; per-encounter outcome stats line.'),
 ('', '- Damage and Healing by skill/spell with session/total toggles; critical'),
 ('', '  hits and heals split into their own panels.'),
 ('', '- Outcome tracking both directions: miss, dodge, parry, block, riposte'),
 ('', '  (plus riposte hits landed and their damage), magical-skin absorbs, rune'),
 ('', '  absorption, damage-shield damage dealt/taken, interrupted casts (yours'),
 ('', '  and ones you caused) — summarized in the Other Stats table.'),
 ('', '- Pet detection from "Master" tells (tells you / told you / says); pet'),
 ('', '  damage panel with damage taken; pet merged as "Pet" into encounters and'),
 ('', '  kill drill-ins.'),
 ('', ''),
 ('h', 'KILL LOG'),
 ('', '- Full lifetime kill history with per-kill drill-ins: your damage table,'),
 ('', '  their damage to you, damage to your pet, zone under the mob name, and a'),
 ('', '  labeled Loot section; session and overall modes, searchable.'),
 ('', '- Times in AM/PM (hours and minutes); drill-ins show Month - Day - Time.'),
 ('', '- Mob names in drill-ins and item names everywhere link to eqlwiki.com.'),
 ('', ''),
 ('h', 'LOOT'),
 ('', '- Lifetime drop rates per mob with session columns, zone under the mob'),
 ('', '  name, per-mob item collapse (click the Item header), and mob summary'),
 ('', '  popups (session + overall) from any mob name.'),
 ('', '- Tracked Drops and Kills with 5/10/20 limit buttons and search.'),
 ('', ''),
 ('h', 'QUESTS'),
 ('', '- Hail tracking; NPCs with [bracketed] dialogue become Possible Quests'),
 ('', '  with name and zone; dialogue viewer with follow-ups, bracketed words in'),
 ('', '  light blue; finish (checkmark), close (X, with confirmation), and'),
 ('', '  return arrows; Closed and Finished panels; everything persists.'),
 ('', ''),
 ('h', 'OVERLAYS'),
 ('', '- Game Overlay (always-on-top window): kills, kills/hr, XP/hr, coin, DPS,'),
 ('', '  session time, to-level, to-50, zone, and Current/Last Combat with'),
 ('', '  SOURCE / DMG / ACC / MAX / DPS columns; drag anywhere, right-click to'),
 ('', '  close, per-section +/- collapse, optional click-through, position and'),
 ('', '  states remembered.'),
 ('', '- OBS overlay (/overlay browser source): same elements as the Game'),
 ('', '  Overlay, transparent, with its own +/- collapses.'),
 ('', ''),
 ('h', 'DATA SAFETY'),
 ('', '- Per-log read offsets: restart-safe, never double counts.'),
 ('', '- Append-only kill history with full combat detail; one-time backfill.'),
 ('', '- Rebuild Data: archives your data files to a versioned zip and re-derives'),
 ('', '  everything from the log.'),
 ('', '- Archive: zips the log to a "Log Archive" folder (name + date stamp) and'),
 ('', '  starts it fresh. Truncate: strips selected channel chat (with optional'),
 ('', '  backup zip) and repairs the read position.'),
 ('', '- Playtime measured from log activity with AFK gaps excluded; level-ups'),
 ('', '  and XP progress persist.'),
 ('', ''),
 ('h', 'APP'),
 ('', '- Single file, no dependencies, everything local (see the pinned security'),
 ('', '  note under Release and Troubleshooting).'),
 ('', '- Versioned releases, changelog, self-extracting installer, GitHub kit.'),
 ('', ''),
]

# ---------------------------------------------------------------- app core
def app_dir():
    if getattr(sys, "frozen", False):                 # PyInstaller exe
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

class AppCore:
    """Owns config, the HTTP server, and the active tracker/tailer pair."""
    def __init__(self):
        base = app_dir()
        self.cfg_path = os.path.join(base, "eql_tracker_config.json")
        self.stats_path = os.path.join(base, "eql_lifetime_stats.json")
        self.cfg = {"log_path": "", "port": 8710, "open_dashboard_on_start": True}
        if os.path.exists(self.cfg_path):
            try:
                with open(self.cfg_path, encoding="utf-8") as f:
                    self.cfg.update(json.load(f))
            except Exception:
                pass
        self.tracker = None
        self.tailer = None
        self.srv = None
        self.port = None
        self.error = None

    def save_cfg(self):
        try:
            with open(self.cfg_path, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2)
        except Exception as e:
            self.error = "Could not save config: %r" % e

    def ensure_server(self):
        if self.srv:
            return True
        base_port = int(self.cfg.get("port", 8710))
        for p in range(base_port, base_port + 10):
            try:
                self.srv = ThreadingHTTPServer(("127.0.0.1", p), Handler)
                self.port = p
                threading.Thread(target=self.srv.serve_forever, daemon=True).start()
                return True
            except OSError:
                continue
        self.error = "No free port between %d and %d." % (base_port, base_port + 9)
        return False

    def start(self, log_path):
        log_path = os.path.abspath(log_path)
        if not os.path.exists(log_path):
            self.error = "Log file not found: %s" % log_path
            return False
        if not self.ensure_server():
            return False
        self.stop_tail()
        self.tracker = Tracker(self.stats_path, log_path)
        self.tailer = Tailer(self.tracker, log_path)
        Handler.tracker, Handler.tailer = self.tracker, self.tailer
        self.tailer.start()
        self.cfg["log_path"] = log_path
        self.save_cfg()
        self.error = None
        return True

    def stop_tail(self):
        if self.tailer:
            self.tailer.stop_evt.set()
            self.tailer.join(timeout=3)
        self.tailer = None

    def running(self):
        return self.tailer is not None and self.tailer.is_alive()

    def url(self, path=""):
        return "http://localhost:%d%s" % (self.port or self.cfg.get("port", 8710), path)

    def status(self):
        if self.error:
            return ("error", self.error)
        if not self.running():
            return ("stopped", "Not tracking. Pick a log file to begin.")
        name = os.path.basename(self.cfg["log_path"])
        if self.tailer.following:
            return ("live", "LIVE - tailing %s" % name)
        return ("busy", "Reading backlog from %s ..." % name)

    def rebuild_data(self):
        """Archive stats+history to a zip, wipe them, re-scan the whole log."""
        import zipfile
        self.stop_tail()
        if self.tracker:
            self.tracker.save_lifetime()
            self.tracker.flush_history(force=True)
        base = app_dir()
        hist = os.path.join(base, "eql_kill_history.jsonl")
        tracked = []
        try:
            if os.path.exists(self.stats_path):
                with open(self.stats_path, encoding="utf-8") as f:
                    tracked = json.load(f).get("tracked", [])
        except Exception:
            pass
        zname = "eql_data_backup_v%s_%s.zip" % (VERSION, time.strftime("%Y%m%d_%H%M%S"))
        zpath = os.path.join(base, zname)
        try:
            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
                for p in (self.stats_path, hist):
                    if os.path.exists(p):
                        z.write(p, os.path.basename(p))
            for p in (self.stats_path, hist):
                if os.path.exists(p):
                    os.remove(p)
        except Exception as e:
            self.error = "Backup failed: %r" % e
            return False, None
        if tracked:
            try:
                with open(self.stats_path, "w", encoding="utf-8") as f:
                    json.dump({"tracked": tracked}, f)
            except Exception:
                pass
        ok = self.start(self.cfg.get("log_path", ""))
        return ok, zname

    def _archive_dir(self):
        d = os.path.join(os.path.dirname(self.cfg.get("log_path", "")) or ".",
                         "Log Archive")
        os.makedirs(d, exist_ok=True)
        return d

    def scan_channels(self):
        import re
        path = self.cfg.get("log_path")
        if not path or not os.path.exists(path):
            return {}
        rx = re.compile(rb"(?:tells|told) (\w+?):\d")
        found = {}
        try:
            with open(path, "rb") as f:
                for line in f:
                    m = rx.search(line)
                    if m:
                        n = m.group(1).decode("utf-8", "replace")
                        found[n] = found.get(n, 0) + 1
        except Exception:
            pass
        return found

    def archive_log(self):
        """Zip the log into Log Archive, empty it, reset the read offset."""
        import zipfile
        path = self.cfg.get("log_path")
        self.stop_tail()
        if self.tracker:
            self.tracker.save_lifetime()
        base = os.path.splitext(os.path.basename(path))[0]
        zname = "%s_%s.zip" % (base, time.strftime("%Y%m%d_%H%M%S"))
        try:
            with zipfile.ZipFile(os.path.join(self._archive_dir(), zname),
                                 "w", zipfile.ZIP_DEFLATED) as z:
                z.write(path, os.path.basename(path))
            with open(path, "w"):
                pass
        except Exception as e:
            self.error = "Archive failed: %r" % e
            self.start(path)
            return False, str(e)
        if self.tracker:
            self.tracker.save_lifetime(offset=0)
        ok = self.start(path)
        return ok, zname

    def truncate_channels(self, names, backup=True):
        """Strip selected channel chat from the log; fix the read offset."""
        import re, zipfile
        path = self.cfg.get("log_path")
        self.stop_tail()
        if self.tracker:
            self.tracker.save_lifetime()
        old_off = 0
        if self.tracker:
            old_off = int(self.tracker.current_offset or 0)
        zname = None
        tmp = path + ".tmp"
        try:
            if backup:
                base = os.path.splitext(os.path.basename(path))[0]
                zname = "%s_%s.zip" % (base, time.strftime("%Y%m%d_%H%M%S"))
                with zipfile.ZipFile(os.path.join(self._archive_dir(), zname),
                                     "w", zipfile.ZIP_DEFLATED) as z:
                    z.write(path, os.path.basename(path))
            rx = re.compile((r"(?:tells|told) (?:%s):\d"
                             % "|".join(re.escape(n) for n in names)).encode())
            removed = removed_before = pos = 0
            with open(path, "rb") as fin, open(tmp, "wb") as fout:
                for line in fin:
                    n = len(line)
                    if rx.search(line):
                        removed += n
                        if pos < old_off:
                            removed_before += n
                    else:
                        fout.write(line)
                    pos += n
            os.replace(tmp, path)
        except Exception as e:
            self.error = "Truncate failed: %r" % e
            try:
                os.remove(tmp)
            except Exception:
                pass
            self.start(path)
            return False, str(e), 0
        new_off = max(0, old_off - removed_before)
        if self.tracker:
            self.tracker.save_lifetime(offset=new_off)
        ok = self.start(path)
        return ok, zname, removed

    def shutdown(self):
        self.stop_tail()
        if self.tracker:
            self.tracker.save_lifetime()
            self.tracker.flush_history(force=True)

# ---------------------------------------------------------------- tk ui
def py_f(x):
    try:
        if abs(float(x)) >= 1e5:
            m, e = ("%.2e" % float(x)).split("e")
            return m + "e" + str(int(e))
    except Exception:
        pass
    return str(x)

def srcname_one(n):
    import re as _re
    m = _re.match(r"^([^(]+?)\s*((?:\([^)]*\)\s*)+)$", str(n))
    if not m:
        return str(n)
    parts = [x if x != "melee" else "Melee"
             for x in _re.findall(r"\(([^)]*)\)", m.group(2))]
    return "%s (%s)" % (m.group(1).strip(), " ".join(parts))

def enc_text(e, live):
    mobs = ", ".join(m["name"] + (" x%d" % m["count"] if m["count"] > 1 else "")
                     for m in e["mobs"])
    badge = {"ongoing": "", "cleared": "  [cleared]",
             "died": "  [YOU DIED]"}.get(e["result"], "  [%s]" % e["result"])
    meta = "%ss - %s dealt - %s taken - hit %s%% - avoided %s%% - %s DPS" % (
        e["dur"], py_f(e["dmg"]), py_f(e["taken"]),
        e.get("acc", 0), e.get("avoid", 0), py_f(e["dps"]))
    if e["heal_total"]["amt"]:
        meta += " - %s healed (%s HPS)" % (py_f(e["heal_total"]["amt"]),
                                           py_f(e["heal_total"]["hps"]))
    lines = []
    if not live and e.get("zone"):
        lines.append("[%s]" % e["zone"])
    lines += [mobs + badge, meta]
    if e["skills"]:
        lines.append(" %-24s %7s %5s %8s %8s" % ("SOURCE", "DMG", "ACC", "MAX", "DPS"))
    for r in e["skills"][:6]:
        lines.append(" %-24s %7s %5s %8s %8s" % (
            srcname_one(r["name"])[:24], py_f(r["dmg"]),
            "-" if r["acc"] is None else "%d%%" % r["acc"],
            py_f(r["max"]), py_f(r["dps"])))
    if len(e["skills"]) > 6:
        lines.append(" ... %d more sources" % (len(e["skills"]) - 6))
    if e["heals"]:
        lines.append(" heals: " + ", ".join("%s %s" % (h["name"], py_f(h["amt"]))
                                            for h in e["heals"][:3]))
    if not live and e.get("killed"):
        ks = e["killed"]
        lines.append(" killed: " + ", ".join(k["name"] for k in ks[:4])
                     + (" +%d more" % (len(ks) - 4) if len(ks) > 4 else ""))
    st = e.get("stats") or {}
    seg = []
    for lbl, a, b in (("miss", "o_miss", "d_miss"), ("ddg", "o_dodge", "d_dodge"),
                      ("par", "o_parry", "d_parry"), ("blk", "o_block", "d_block"),
                      ("rip", "o_riposte", "d_riposte"), ("abs", "o_absorb", "d_absorb"),
                      ("DS", "ds_dealt", "ds_taken"), ("int", "int_them", "int_mine")):
        if st.get(a) or st.get(b):
            seg.append("%s %s/%s" % (lbl, py_f(st.get(a, 0)), py_f(st.get(b, 0))))
    if st.get("riposte_hits"):
        seg.append("rip hits %s" % py_f(st["riposte_hits"]))
    if st.get("rune_pts"):
        seg.append("rune %s" % py_f(st["rune_pts"]))
    if seg:
        lines.append(" " + " - ".join(seg))
    return "\n".join(lines)

def fmt_elapsed(s):
    m, sec = divmod(int(s), 60)
    h, m = divmod(m, 60)
    return "%dh %02dm" % (h, m) if h else "%dm %02ds" % (m, sec)

def run_gui(core):
    import tkinter as tk
    from tkinter import filedialog, messagebox

    BG, PANEL, EDGE = "#0d1017", "#151a24", "#2a3242"
    GOLD, GOLD_D, TX, DIM = "#c9a85c", "#8a7440", "#d8d4c8", "#8891a0"
    GRN, RED = "#6fae6f", "#d06a4a"

    root = tk.Tk()
    root.title("EQL Hunting Log")
    root.configure(bg=BG)
    root.geometry("640x320")
    root.minsize(560, 300)

    def lbl(parent, **kw):
        kw.setdefault("bg", parent["bg"]); kw.setdefault("fg", TX)
        return tk.Label(parent, **kw)

    def btn(parent, text, cmd, accent=False):
        b = tk.Button(parent, text=text, command=cmd, relief="flat", cursor="hand2",
                      bg=PANEL, fg=GOLD if accent else TX,
                      activebackground=EDGE, activeforeground=GOLD,
                      highlightthickness=1, highlightbackground=GOLD_D if accent else EDGE,
                      padx=12, pady=5, font=("Segoe UI", 9))
        return b

    # header
    head = tk.Frame(root, bg=BG); head.pack(fill="x", pady=(14, 4))
    lbl(head, text="EVERQUEST LEGENDS", fg=GOLD_D, font=("Georgia", 8)).pack()
    lbl(head, text="Hunting Log", fg=GOLD, font=("Georgia", 18, "bold")).pack()

    # log picker row
    pick = tk.Frame(root, bg=BG); pick.pack(fill="x", padx=16, pady=(10, 4))
    path_var = tk.StringVar(value=core.cfg.get("log_path") or "No log selected")
    entry = tk.Entry(pick, textvariable=path_var, state="readonly", relief="flat",
                     readonlybackground=PANEL, fg=DIM, font=("Segoe UI", 9),
                     highlightthickness=1, highlightbackground=EDGE)
    entry.pack(side="left", fill="x", expand=True, ipady=5)

    def browse():
        init = os.path.dirname(core.cfg.get("log_path") or "") or None
        p = filedialog.askopenfilename(
            title="Select your EQL log file", initialdir=init,
            filetypes=[("EQ log files", "eqlog_*.txt"), ("Text files", "*.txt"),
                       ("Log files", "*.log"), ("All files", "*.*")])
        if p:
            if core.start(p):
                path_var.set(p)
            elif core.error:
                messagebox.showerror("EQL Hunting Log", core.error)

    tk.Frame(pick, bg=BG, width=8).pack(side="left")
    btn(pick, "Browse...", browse, accent=True).pack(side="left")

    # status + mini stats
    status_row = tk.Frame(root, bg=BG); status_row.pack(fill="x", padx=16, pady=(8, 2))
    dot = tk.Canvas(status_row, width=10, height=10, bg=BG, highlightthickness=0)
    dot_id = dot.create_oval(2, 2, 9, 9, fill=DIM, outline="")
    dot.pack(side="left", pady=2)
    status_lbl = lbl(status_row, text="", fg=DIM, font=("Segoe UI", 9), anchor="w")
    status_lbl.pack(side="left", padx=(6, 0))

    stats = tk.Frame(root, bg=PANEL, highlightthickness=1, highlightbackground=EDGE)
    stats.pack(fill="x", padx=16, pady=(8, 4), ipady=6)
    cells = {}
    for i, (key, label) in enumerate([("kills", "KILLS"), ("dps", "DPS"),
                                      ("kph", "KILLS/HR"), ("deaths", "DEATHS"),
                                      ("elapsed", "SESSION")]):
        c = tk.Frame(stats, bg=PANEL); c.grid(row=0, column=i, sticky="nsew")
        stats.grid_columnconfigure(i, weight=1)
        v = lbl(c, text="-", fg=TX, font=("Georgia", 14, "bold")); v.pack()
        lbl(c, text=label, fg=DIM, font=("Segoe UI", 7)).pack()
        cells[key] = v

    # action buttons
    actions = tk.Frame(root, bg=BG); actions.pack(fill="x", padx=16, pady=(10, 4))
    btn(actions, "All Dashboards", lambda: webbrowser.open(core.url("/")), accent=True)\
        .pack(side="left")
    tk.Frame(actions, bg=BG, width=6).pack(side="left")
    btn(actions, "Combat Dashboard", lambda: webbrowser.open(core.url("/combat"))).pack(side="left")
    tk.Frame(actions, bg=BG, width=6).pack(side="left")
    btn(actions, "Loot Dashboard", lambda: webbrowser.open(core.url("/loot"))).pack(side="left")
    tk.Frame(actions, bg=BG, width=6).pack(side="left")
    btn(actions, "Quest Dashboard", lambda: webbrowser.open(core.url("/quests"))).pack(side="left")
    tk.Frame(actions, bg=BG, width=6).pack(side="left")
    btn(actions, "OBS Overlay", lambda: webbrowser.open(core.url("/overlay"))).pack(side="left")
    def show_text_window(title, parts):
        win = tk.Toplevel(root)
        win.title(title)
        win.configure(bg=BG)
        win.geometry("760x560")
        frame = tk.Frame(win, bg=BG); frame.pack(fill="both", expand=True, padx=10, pady=10)
        sb = tk.Scrollbar(frame)
        sb.pack(side="right", fill="y")
        txt = tk.Text(frame, bg=PANEL, fg=TX, insertbackground=TX, wrap="word",
                      relief="flat", font=("Segoe UI", 10), padx=12, pady=10,
                      yscrollcommand=sb.set)
        txt.pack(fill="both", expand=True)
        sb.config(command=txt.yview)
        txt.tag_configure("h", foreground=GOLD, font=("Georgia", 12, "bold"),
                          spacing1=10, spacing3=4)
        txt.tag_configure("b", foreground=GOLD_D, font=("Segoe UI", 10, "bold"))
        for part in parts:
            txt.insert("end", part[1] + "\n", part[0])
        txt.config(state="disabled")

    def show_release_notes():
        show_text_window("Release and Troubleshooting", RELEASE_NOTES)

    def show_features():
        show_text_window("Features", FEATURES)

    actions2 = tk.Frame(root, bg=BG); actions2.pack(fill="x", padx=16, pady=(6, 4))
    btn(actions2, "Gear & Leveling Planning",
        lambda: messagebox.showinfo("Gear & Leveling Planning",
                                    "You have to wait for this feature")).pack(side="left")

    overlay = {"win": None, "labels": {}, "drag": [0, 0]}
    ct_var = tk.BooleanVar(value=bool(core.cfg.get("overlay_clickthrough", False)))

    def apply_clickthrough():
        w = overlay["win"]
        core.cfg["overlay_clickthrough"] = bool(ct_var.get())
        core.save_cfg()
        if w is None or sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(w.winfo_id()) or w.winfo_id()
            GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT = -20, 0x80000, 0x20
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if ct_var.get():
                style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
            else:
                style &= ~WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

    def close_overlay():
        w = overlay["win"]
        if w is not None:
            try:
                core.cfg["overlay_pos"] = [w.winfo_x(), w.winfo_y()]
                core.save_cfg()
                w.destroy()
            except Exception:
                pass
        overlay["win"] = None
        overlay["labels"] = {}
        overlay_btn.config(text="Game Overlay")

    def toggle_overlay():
        if overlay["win"] is not None:
            close_overlay()
            return
        try:
            _build_overlay()
        except Exception:
            import traceback
            err = traceback.format_exc()
            if overlay["win"] is not None:
                try: overlay["win"].destroy()
                except Exception: pass
            overlay["win"] = None
            overlay["labels"] = {}
            messagebox.showerror("Game Overlay",
                "The overlay failed to open:\n\n" + err)

    def _build_overlay():
        w = tk.Toplevel(root)
        overlay["win"] = w
        overlay["labels"] = {}
        overlay["cache"] = {}
        overlay["collapsed"] = {
            "cur": bool(core.cfg.get("overlay_cur_c", False)),
            "last": bool(core.cfg.get("overlay_last_c", False))}
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        try:
            w.attributes("-alpha", float(core.cfg.get("overlay_alpha", 0.88)))
        except Exception:
            pass
        pos = core.cfg.get("overlay_pos") or [60, 60]
        try:
            w.geometry("+%d+%d" % (int(pos[0]), int(pos[1])))
        except Exception:
            w.geometry("+60+60")
        w.configure(bg=GOLD_D)
        inner = tk.Frame(w, bg=BG); inner.pack(padx=1, pady=1)
        pad = tk.Frame(inner, bg=BG); pad.pack(padx=12, pady=8)
        top = tk.Frame(pad, bg=BG); top.pack(anchor="w")
        no_drag = []

        def cell(key, label):
            c = tk.Frame(top, bg=BG); c.pack(side="left", padx=(0, 14))
            v = tk.Label(c, text="-", bg=BG, fg=GOLD, font=("Georgia", 13, "bold"))
            v.pack()
            tk.Label(c, text=label, bg=BG, fg=DIM, font=("Segoe UI", 7)).pack()
            overlay["labels"][key] = v
        for key, label in (("kills", "KILLS"), ("kph", "KILLS/HR"),
                           ("xph", "XP/HR"), ("coin", "COIN (SESSION)"),
                           ("dps", "DPS"), ("time", "SESSION"),
                           ("tolvl", "TO LVL"), ("to50", "TO 50")):
            cell(key, label)
        zone = tk.Label(pad, text="", bg=BG, fg=GOLD, font=("Segoe UI", 9, "bold"))
        zone.pack(anchor="w", pady=(6, 0))
        overlay["labels"]["zone"] = zone
        mono = ("Consolas", 9)

        def section(key, title, top_pad):
            hdr = tk.Frame(pad, bg=BG); hdr.pack(anchor="w", pady=(top_pad, 0))
            tk.Label(hdr, text=title, bg=BG, fg=GOLD_D,
                     font=("Segoe UI", 7, "bold")).pack(side="left")
            tog = tk.Label(hdr, text="", bg=BG, fg=GOLD, cursor="hand2",
                           font=("Segoe UI", 10, "bold"))
            tog.pack(side="left", padx=(6, 0))
            no_drag.append(tog)
            body = tk.Label(pad, text="Waiting for combat...", bg=BG, fg=DIM,
                            font=mono, justify="left", anchor="w")
            body.pack(anchor="w", after=hdr)

            def redraw():
                col = overlay["collapsed"][key]
                tog.config(text="+" if col else "\u2212")
                if col:
                    body.pack_forget()
                else:
                    body.pack(anchor="w", after=hdr)

            def flip(_e=None):
                overlay["collapsed"][key] = not overlay["collapsed"][key]
                core.cfg["overlay_%s_c" % key] = overlay["collapsed"][key]
                core.save_cfg()
                overlay["cache"].pop(key, None)
                redraw()
                return "break"
            tog.bind("<Button-1>", flip)
            redraw()
            return body
        overlay["labels"]["cur"] = section("cur", "CURRENT COMBAT", 4)
        overlay["labels"]["last"] = section("last", "LAST COMBAT", 7)

        def press(e):
            overlay["drag"] = [e.x_root - w.winfo_x(), e.y_root - w.winfo_y()]
        def move(e):
            w.geometry("+%d+%d" % (e.x_root - overlay["drag"][0],
                                   e.y_root - overlay["drag"][1]))
        def release(e):
            core.cfg["overlay_pos"] = [w.winfo_x(), w.winfo_y()]
            core.save_cfg()

        def bind_all_drag(widget):
            if widget not in no_drag:
                widget.bind("<Button-1>", press)
                widget.bind("<B1-Motion>", move)
                widget.bind("<ButtonRelease-1>", release)
                widget.bind("<Button-3>", lambda e: close_overlay())
            for ch in widget.winfo_children():
                bind_all_drag(ch)
        bind_all_drag(w)
        w.after(50, apply_clickthrough)
        overlay_btn.config(text="Close Overlay")

    tk.Frame(actions2, bg=BG, width=8).pack(side="left")
    overlay_btn = btn(actions2, "Game Overlay", toggle_overlay)
    overlay_btn.pack(side="left")
    ct = tk.Checkbutton(actions2, text="click-through", variable=ct_var,
                        command=apply_clickthrough, bg=BG, fg=DIM,
                        activebackground=BG, activeforeground=GOLD,
                        selectcolor=PANEL, font=("Segoe UI", 8),
                        highlightthickness=0, bd=0)
    ct.pack(side="left", padx=(4, 0))
    root.geometry("720x400")

    def toggle():
        if core.running():
            core.stop_tail()
        elif core.cfg.get("log_path"):
            core.start(core.cfg["log_path"])
        refresh_toggle()

    def do_rebuild():
        if not core.cfg.get("log_path"):
            messagebox.showerror("EQL Hunting Log", "Pick a log file first.")
            return
        if not messagebox.askyesno("Rebuild data",
                "Re-scan the entire log and rebuild all data files?\n\n"
                "Current stats and kill history will be archived to a zip "
                "first. Tracked mobs are kept."):
            return
        ok, zname = core.rebuild_data()
        if ok:
            messagebox.showinfo("Rebuild data",
                "Old data archived to %s.\nRe-scanning the log now." % zname)
        elif core.error:
            messagebox.showerror("Rebuild data", core.error)

    def do_archive():
        if not core.cfg.get("log_path"):
            messagebox.showerror("EQL Hunting Log", "Pick a log file first.")
            return
        if not messagebox.askyesno("Archive log",
                "Zip the current log into the 'Log Archive' folder (next to "
                "the log) and start a fresh, empty log?\n\nAll drop, kill, "
                "and combat history stays in the app's data files.\n"
                "Best done while the game is closed or after /log off."):
            return
        ok, res = core.archive_log()
        if ok:
            messagebox.showinfo("Archive log",
                "Archived to Log Archive\\%s\nThe log is now empty and "
                "tracking continues fresh." % res)
        else:
            messagebox.showerror("Archive log", core.error or res)

    def do_truncate():
        if not core.cfg.get("log_path"):
            messagebox.showerror("EQL Hunting Log", "Pick a log file first.")
            return
        chans = core.scan_channels()
        if not chans:
            messagebox.showinfo("Truncate chat",
                                "No channel chat found in the log.")
            return
        win = tk.Toplevel(root)
        win.title("Truncate chat")
        win.configure(bg=BG)
        win.geometry("420x230")
        lbl(win, text="Remove a channel's chat lines from the log to shrink it.",
            font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=(14, 4))
        names = sorted(chans, key=lambda k: -chans[k])
        lbl(win, text="Found: " + ", ".join("%s (%s)" % (n, chans[n]) for n in names),
            fg=DIM, font=("Segoe UI", 8), wraplength=380, justify="left")\
            .pack(anchor="w", padx=16)
        var = tk.StringVar(value=names[0])
        om = tk.OptionMenu(win, var, *(names + ["All channels"]))
        om.configure(bg=PANEL, fg=TX, activebackground=PANEL,
                     activeforeground=GOLD, highlightthickness=0, relief="flat")
        om["menu"].configure(bg=PANEL, fg=TX)
        om.pack(anchor="w", padx=16, pady=8)
        bk = tk.BooleanVar(value=True)
        tk.Checkbutton(win, text="Back up log to a zip in Log Archive first",
                       variable=bk, bg=BG, fg=TX, activebackground=BG,
                       activeforeground=GOLD, selectcolor=PANEL,
                       highlightthickness=0).pack(anchor="w", padx=16)

        def go():
            sel = var.get()
            picked = names if sel == "All channels" else [sel]
            if not messagebox.askyesno("Truncate chat",
                    "Remove all '%s' chat lines from the log?\nBest done "
                    "while the game is closed or after /log off." % sel,
                    parent=win):
                return
            ok, zname, removed = core.truncate_channels(picked, bk.get())
            win.destroy()
            if ok:
                messagebox.showinfo("Truncate chat",
                    "Removed %.1f MB of %s chat.%s" % (
                        removed / 1048576.0, sel,
                        ("\nBackup: Log Archive\\" + zname) if zname else ""))
            else:
                messagebox.showerror("Truncate chat", core.error or zname)
        btn(win, "Truncate", go, accent=True).pack(anchor="e", padx=16, pady=10)

    toggle_btn = btn(actions2, "Stop", toggle)
    toggle_btn.pack(side="right")
    tk.Frame(actions2, bg=BG, width=8).pack(side="right")
    btn(actions2, "Rebuild Data", do_rebuild).pack(side="right")

    actions3 = tk.Frame(root, bg=BG); actions3.pack(fill="x", padx=16, pady=(2, 4))
    btn(actions3, "Features", show_features).pack(side="left")
    tk.Frame(actions3, bg=BG, width=6).pack(side="left")
    btn(actions3, "Archive", do_archive).pack(side="left")
    tk.Frame(actions3, bg=BG, width=6).pack(side="left")
    btn(actions3, "Truncate", do_truncate).pack(side="left")
    tk.Frame(actions3, bg=BG, width=6).pack(side="left")
    btn(actions3, "Release and Troubleshooting", show_release_notes).pack(side="left")

    def refresh_toggle():
        toggle_btn.config(text="Stop" if core.running() else "Start")

    url_lbl = lbl(root, text="v" + VERSION, fg="#5a6272", font=("Segoe UI", 8))
    url_lbl.pack(side="bottom", pady=(0, 8))

    # poll loop (main thread only touches tk)
    def tick():
        state, msg = core.status()
        colors = {"live": GRN, "busy": GOLD, "stopped": DIM, "error": RED}
        dot.itemconfigure(dot_id, fill=colors.get(state, DIM))
        status_lbl.config(text=msg, fg=RED if state == "error" else DIM)
        url_lbl.config(text="v%s  -  Dashboard: %s    Overlay: %s" %
                       (VERSION, core.url("/"), core.url("/overlay"))
                       if core.port else "v" + VERSION)
        if core.tracker:
            snap = core.tracker.snapshot(core.tailer.following if core.tailer else False)
            s = snap["session"]
            cells["kills"].config(text=s["kills"])
            cells["dps"].config(text=s["dps"])
            cells["kph"].config(text=s["kph"])
            cells["deaths"].config(text=s["deaths"], fg=RED if s["deaths"] else TX)
            cells["elapsed"].config(text=fmt_elapsed(s["elapsed"]))
            if overlay["win"] is not None:
                L = overlay["labels"]
                cache = overlay["cache"]

                def setlbl(key, text, fg=None):
                    if cache.get(key) != (text, fg):
                        cache[key] = (text, fg)
                        if fg:
                            L[key].config(text=text, fg=fg)
                        else:
                            L[key].config(text=text)
                setlbl("kills", str(py_f(s["kills"])))
                setlbl("kph", str(py_f(s["kph"])))
                setlbl("xph", "%s%%" % s["xp_hr"])
                setlbl("coin", s["coin"])
                setlbl("dps", str(py_f(s["dps"])))
                setlbl("time", fmt_elapsed(s["elapsed"]))
                lv = snap.get("leveling") or {}
                setlbl("tolvl", fmt_elapsed(lv["to_lvl_s"])
                       if lv.get("to_lvl_s") is not None else "-")
                setlbl("to50", fmt_elapsed(lv["to_50_s"])
                       if lv.get("to_50_s") is not None else "-")
                setlbl("zone", snap.get("zone", ""))
                if not overlay["collapsed"]["cur"]:
                    cc = snap.get("current_combat")
                    setlbl("cur", enc_text(cc, True) if cc else "Waiting for combat...",
                           TX if cc else DIM)
                if not overlay["collapsed"]["last"]:
                    lc2 = snap.get("last_combat")
                    setlbl("last", enc_text(lc2, False) if lc2 else "Waiting for combat...",
                           TX if lc2 else DIM)
        refresh_toggle()
        root.after(1000, tick)

    def on_close():
        if overlay["win"] is not None:
            close_overlay()
        core.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # auto-resume the last log
    if core.cfg.get("log_path") and os.path.exists(core.cfg["log_path"]):
        core.start(core.cfg["log_path"])
        if core.cfg.get("open_dashboard_on_start", True):
            root.after(800, lambda: webbrowser.open(core.url("/")))
    tick()
    root.mainloop()

# ---------------------------------------------------------------- main
def main():
    core = AppCore()
    headless = "--headless" in sys.argv
    argv_paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    if argv_paths:
        core.cfg["log_path"] = argv_paths[0]
    if not headless:
        try:
            run_gui(core)
            return
        except Exception:
            import traceback
            err = traceback.format_exc()
            try:
                with open(os.path.join(app_dir(), "eql_tracker_error.log"), "w") as f:
                    f.write(err)
            except Exception:
                pass
            print(err, file=sys.stderr)
            if not core.cfg.get("log_path"):
                return
            print("GUI unavailable - falling back to headless mode.", file=sys.stderr)
    # headless: tail the configured/passed log until Ctrl+C
    if not core.cfg.get("log_path"):
        print("Usage: eql_tracker_app.pyw [logfile] [--headless]")
        return
    if core.start(core.cfg["log_path"]):
        print("EQL Hunting Log -> %s  (overlay: /overlay)" % core.url("/"))
        print("Tailing: %s" % core.cfg["log_path"])
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            core.shutdown()
    else:
        print(core.error or "Failed to start.", file=sys.stderr)

if __name__ == "__main__":
    main()
