#!/usr/bin/env python3
"""
What the program remembers between runs.

Two things:

* **Consumables** - the wwPTFE plate LOT, the Protein G plate and how many
  times it has been used, the PNGase F LOT, and when each buffer/solution was
  prepared.  The lab shares the physical plates and solution batches, so this
  lives on the share: open a new wwPTFE plate, record it once, and the next
  analyst is offered it as the current one.

* **Runs** - where a plate got to.  A GlycanAge plate is worked over two days
  (isolation, then the NanoDrop, then deglycosylation and clean-up), so the
  worksheet numbers entered on day 1 have to still be there on day 2.

Both are plain JSON so they can be read, fixed or cleared with Notepad if
anything goes wrong - no database to repair on a lab PC.

Concurrency: several analysts share the file.  A write re-reads the file,
merges its own change into whatever is there now, and renames a temporary
file over the original, so two people saving at the same moment cannot
truncate each other.  The worst case is a lost edit, never a corrupt file.
If the share is unreachable the local copy under %LOCALAPPDATA% is used, so
a network outage does not stop work.
"""
import os
import json
import time
import datetime
import tempfile

# Beside the exe on the share, so the lab shares one list.
SHARE_DIR = (r"\\10.70.119.100\Glikobiologija\POPULATION DATA BASE"
             r"\_tools\IgG Concentration Builder")
LOCAL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()),
                         "IgG Concentration Builder")

CONSUMABLES_FILE = "consumables.json"
RUNS_FILE = "runs.json"

# The consumables the program offers a remembered value for.
#   key            label shown in the form                     keeps history
CONSUMABLE_FIELDS = [
    ("wwptfe_lot",           "wwPTFE plate LOT no.",              True),
    ("proteing_no",          "Protein G monolithic plate (No.)",  True),
    ("proteing_uses",        "Times this Protein G plate used",   False),
    ("enzyme_lot",           "PNGase F enzyme LOT",               True),
    ("enzyme_reconstituted", "Enzyme date of reconstitution",     False),
]

# Solutions, per worksheet, exactly as their rows are printed.
SOLUTIONS = {
    "isolation": ["1x PBS", "1xPBS (0,25M NaCl)", "10x PBS",
                  "0,1M FA", "1M AmBic", "Storage buffer"],
    "deglyco":   ["1,66x PBS", "0,5% SDS", "4% Igepal",
                  "5x PBS", "1,2M 2", "30mM APTS"],
    "cleanup":   ["Biogel P10 slurry", "80 % ACN", "80% ACN", "HiDi Formamide"],
}
# Printed row name -> what to call it in the form.
SOLUTION_LABELS = {"1,2M 2": "1,2M 2-PB", "80 % ACN": "80% ACN",
                   "80% ACN": "80% ACN / 100mM TEA"}


class Store:
    """JSON on the share, with a local fallback."""

    def __init__(self, folder=None, log=None):
        self.log = log or (lambda *_: None)
        self.folder = folder or SHARE_DIR
        self.using_local = False
        if not self._writable(self.folder):
            self.folder = LOCAL_DIR
            self.using_local = True

    # -- plumbing ----------------------------------------------------------

    @staticmethod
    def _writable(folder):
        try:
            os.makedirs(folder, exist_ok=True)
            probe = os.path.join(folder, ".write-probe")
            with open(probe, "w") as fh:
                fh.write("ok")
            os.remove(probe)
            return True
        except Exception:
            return False

    def path(self, name):
        return os.path.join(self.folder, name)

    def _read(self, name):
        try:
            with open(self.path(name), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception as e:
            self.log(f"  !! {name} could not be read ({e}) - starting empty")
            return {}

    def _write(self, name, merge):
        """Re-read, apply `merge(data)`, then rename a temp file over it."""
        target = self.path(name)
        for attempt in range(4):
            try:
                data = self._read(name)
                merge(data)
                fd, tmp = tempfile.mkstemp(dir=self.folder, suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2, ensure_ascii=False)
                os.replace(tmp, target)
                return True
            except Exception as e:
                if attempt == 3:
                    self.log(f"  !! could not save {name}: {e}")
                    return False
                time.sleep(0.25 * (attempt + 1))
        return False

    # -- consumables -------------------------------------------------------

    def consumables(self):
        """-> {key: {'current': str, 'history': [str]}}"""
        return self._read(CONSUMABLES_FILE)

    def current(self):
        """-> {key: current value} for filling straight into a worksheet."""
        return {k: v.get("current", "")
                for k, v in self.consumables().items() if isinstance(v, dict)}

    def options(self, key):
        """-> [value] most recently used first, for the dropdown."""
        rec = self.consumables().get(key) or {}
        hist = [h for h in rec.get("history", []) if h]
        cur = rec.get("current", "")
        return ([cur] if cur else []) + [h for h in hist if h != cur]

    def remember(self, key, value, who=""):
        """Make `value` the current one for `key`, keeping the old ones."""
        value = (value or "").strip()
        if not value:
            return
        def merge(data):
            rec = data.get(key)
            if not isinstance(rec, dict):
                rec = {"current": "", "history": []}
            hist = [h for h in rec.get("history", []) if h and h != value]
            if rec.get("current") and rec["current"] != value:
                hist.insert(0, rec["current"])
            rec["current"] = value
            rec["history"] = hist[:20]
            rec["changed"] = datetime.date.today().isoformat()
            if who:
                rec["by"] = who
            data[key] = rec
        self._write(CONSUMABLES_FILE, merge)

    def solutions(self):
        """-> {solution name: date of preparation}"""
        return self._read(CONSUMABLES_FILE).get("_solutions", {})

    def remember_solution(self, name, date):
        date = (date or "").strip()
        def merge(data):
            sols = data.setdefault("_solutions", {})
            if date:
                sols[name] = date
            else:
                sols.pop(name, None)
        self._write(CONSUMABLES_FILE, merge)

    # -- per-plate run state ----------------------------------------------

    def run(self, batch):
        """-> what was already entered for this plate."""
        return self._read(RUNS_FILE).get(batch, {}) if batch else {}

    def save_run(self, batch, state):
        if not batch:
            return
        def merge(data):
            rec = data.get(batch) or {}
            rec.update(state)
            rec["saved"] = datetime.datetime.now().isoformat(timespec="seconds")
            data[batch] = rec
        self._write(RUNS_FILE, merge)

    def recent_runs(self, limit=15):
        data = self._read(RUNS_FILE)
        rows = sorted(data.items(), key=lambda kv: kv[1].get("saved", ""),
                      reverse=True)
        return [b for b, _ in rows[:limit]]

    # The three worksheets a plate has to produce before it counts as done.
    ALL_BUILT = ("isolation", "deglyco", "cleanup")

    def plates(self, limit=200):
        """-> [{batch, saved, built, layout, done}] newest first.

        Feeds the plate list.  `done` means all three worksheets have been
        built for that plate, which is as close as this program can get to
        knowing a plate is finished - it never sees the bench.
        """
        data = self._read(RUNS_FILE)
        rows = []
        for batch, rec in data.items():
            if not isinstance(rec, dict):
                continue
            built = [b for b in rec.get("built", []) if b]
            rows.append({
                "batch": batch,
                "saved": rec.get("saved", ""),
                "built": built,
                "layout": rec.get("layout", ""),
                "done": all(k in built for k in self.ALL_BUILT),
            })
        rows.sort(key=lambda r: r["saved"], reverse=True)
        return rows[:limit]

    def forget_run(self, batch):
        """Drop a plate from the list (the files it produced are untouched)."""
        def merge(data):
            data.pop(batch, None)
        self._write(RUNS_FILE, merge)
