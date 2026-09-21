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

# Beside the exe on the share, so the lab shares one list.  Every program in
# 'Python programs' has its own folder, and this one writes two json files
# and keeps a 'previous' folder, so it keeps to that convention rather than
# dropping loose files in among the other tools.
SHARE_DIR = r"\\10.70.119.100\Glikobiologija\Python programs\IgG Concentration Builder"
LOCAL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()),
                         "IgG Concentration Builder")

CONSUMABLES_FILE = "consumables.json"
RUNS_FILE = "runs.json"

# The consumables the program offers a remembered value for.  'Times this
# Protein G plate has been used' is deliberately NOT here: it is counted from
# the plates the lab has actually run, not typed in - see proteing_uses().
#   key            label shown in the form                     keeps history
CONSUMABLE_FIELDS = [
    ("wwptfe_lot",           "wwPTFE plate LOT no.",              True),
    ("proteing_no",          "Protein G monolithic plate (No.)",  True),
    ("enzyme_lot",           "PNGase F enzyme LOT",               True),
    ("enzyme_reconstituted", "Enzyme date of reconstitution",     False),
]

# Solutions, per worksheet, exactly as their rows are printed.
SOLUTIONS = {
    "isolation": ["1x PBS", "1xPBS (0,25M NaCl)", "10x PBS",
                  "0,1M FA", "1M AmBic", "Storage buffer"],
    "deglyco":   ["1,66x PBS", "0,5% SDS", "4% Igepal",
                  "5x PBS", "1,2M 2-PB", "30mM APTS"],
    "cleanup":   ["Biogel P10 slurry", "80 % ACN",
                  "80% ACN / 100mM TEA", "HiDi Formamide"],
}
# Printed row name -> what to call it in the form.
SOLUTION_LABELS = {"1,2M 2-PB": "1,2M 2-PB",
                   "80 % ACN": "80% ACN",
                   "80% ACN / 100mM TEA": "80% ACN / 100mM TEA"}

# ---------------------------------------------------------------------------
#  How much of each solution one plate needs.
#
#  Read off the worksheets themselves rather than guessed, so the figures can
#  be checked against the SOP.  Each entry is the steps that consume it:
#  (microlitres, "well" or "plate", which step).  A 'well' step is multiplied
#  by the number of wells on the plate.
#
#  OVERAGE is added on top for dead volume, priming a repeater tip and the
#  odd repeat - a plate's worth of solution measured exactly is never enough
#  in practice.
# ---------------------------------------------------------------------------
OVERAGE = 0.20
PLATE_WELLS = 96

SOLUTION_RECIPE = {
    # --- IgG isolation, GBL-WS-031/07 ---
    "1x PBS": [
        (800, "well", "step 1.1/1.2 dilute each sample and the blank"),
    ],
    "1xPBS (0,25M NaCl)": [
        (500, "well", "step 2 pre-conditioning wash"),
        (1000, "well", "step 2 equilibrate"),
        (500, "well", "step 3 wash x3"),
        (500, "well", "step 3 wash x3"),
        (500, "well", "step 3 wash x3"),
        (1000, "well", "step 5 regeneration wash"),
    ],
    "10x PBS": [
        (500, "well", "step 2 neutralize the plate"),
        (500, "well", "step 5 regeneration wash"),
    ],
    "0,1M FA": [
        (250, "well", "step 2 pre-conditioning wash"),
        (250, "well", "step 4 elute IgG"),
        (500, "well", "step 5 regeneration wash"),
    ],
    "1M AmBic": [
        (42.5, "well", "step 4 neutralization buffer in the collection plate"),
    ],
    "Storage buffer": [
        (250, "well", "step 5 vacuum to waste"),
        (750, "well", "step 5 store at 4 C"),
    ],
    # --- Deglycosylation + APTS, GBL-WS-029/04 ---
    "1,66x PBS":  [(3, "well", "step 1 add to each sample")],
    "0,5% SDS":   [(4, "well", "step 1 add to each sample")],
    "4% Igepal":  [(2, "well", "step 2 add to each sample")],
    "5x PBS":     [(1, "well", "step 2 enzyme mixture, 1 uL per sample")],
    "1,2M 2-PB":  [(230, "plate", "step 3 APTS/PB labelling mixture")],
    "30mM APTS":  [(230, "plate", "step 3 APTS/PB labelling mixture")],
    # --- HILIC-SPE clean-up, GBL-WS-030/04 ---
    "Biogel P10 slurry": [
        (200, "well", "step 2 load the wwPTFE plate"),
    ],
    # 'Repeat this step twice' is read as twice in total, which is how the
    # same worksheet uses 'Repeat this step 4 times' for the ACN/TEA wash.
    # The 100 uL inside the 106 uL transfer is the ACN added at step 1 and is
    # deliberately not counted a second time.
    "80 % ACN": [
        (100, "well", "step 1 stop the labelling reaction"),
        (200, "well", "step 2 pre-conditioning wash, twice"),
        (200, "well", "step 2 pre-conditioning wash, twice"),
        (200, "well", "step 3 clean-up wash, twice"),
        (200, "well", "step 3 clean-up wash, twice"),
    ],
    "80% ACN / 100mM TEA": [
        (200, "well", "step 3 wash x4"),
        (200, "well", "step 3 wash x4"),
        (200, "well", "step 3 wash x4"),
        (200, "well", "step 3 wash x4"),
    ],
    "HiDi Formamide": [
        (7, "well", "step 4 into each well of the reaction plate"),
        (17, "plate", "step 4 the IgG pool column"),
    ],
}


def derived_per_plate(name, wells=PLATE_WELLS, overage=OVERAGE):
    """-> mL one plate needs, from the worksheet steps, plus the overage."""
    steps = SOLUTION_RECIPE.get(name)
    if not steps:
        return None
    ul = sum(v * (wells if per == "well" else 1) for v, per, _ in steps)
    return round(ul * (1 + overage) / 1000.0, 2)


def recipe_note(name, wells=PLATE_WELLS, overage=OVERAGE):
    """A one-line explanation of where the figure came from."""
    steps = SOLUTION_RECIPE.get(name)
    if not steps:
        return ""
    ul = sum(v * (wells if per == "well" else 1) for v, per, _ in steps)
    per_well = sum(v for v, per, _ in steps if per == "well")
    per_plate = sum(v for v, per, _ in steps if per == "plate")
    bits = []
    if per_well:
        bits.append(f"{per_well:g} uL/well x {wells}")
    if per_plate:
        bits.append(f"{per_plate:g} uL/plate")
    return (f"{' + '.join(bits)} = {ul / 1000.0:.2f} mL, "
            f"+{int(overage * 100)}% = {derived_per_plate(name, wells, overage):g} mL")


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
        """-> {key: current value} for filling straight into a worksheet.

        Keys beginning '_' are the file's own sections (the solution library,
        the Protein G counts) rather than consumables, so they are skipped -
        otherwise they come back looking like a LOT number with no value.
        """
        return {k: v.get("current", "")
                for k, v in self.consumables().items()
                if isinstance(v, dict) and not k.startswith("_")}

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

    # -- Protein G plate use count ----------------------------------------

    def proteing_uses(self, plate_no):
        """-> how many plates this Protein G plate has been used for.

        Counted, not typed.  The count is the number of distinct GA batches
        the plate has been used on, so rebuilding a worksheet does not
        inflate it and two analysts running different plates both count.
        """
        plate_no = (plate_no or "").strip()
        if not plate_no:
            return 0
        rec = self._read(CONSUMABLES_FILE).get("_proteing", {}).get(plate_no)
        return len(rec.get("batches", [])) if isinstance(rec, dict) else 0

    def record_proteing_use(self, plate_no, batch, who=""):
        """Note that `plate_no` was used for `batch`. -> the new count."""
        plate_no = (plate_no or "").strip()
        batch = (batch or "").strip()
        if not plate_no or not batch:
            return self.proteing_uses(plate_no)

        def merge(data):
            plates = data.setdefault("_proteing", {})
            rec = plates.setdefault(plate_no, {"batches": []})
            if batch not in rec["batches"]:
                rec["batches"].append(batch)
            rec["last_used"] = datetime.date.today().isoformat()
            if who:
                rec["by"] = who
        self._write(CONSUMABLES_FILE, merge)
        return self.proteing_uses(plate_no)

    def proteing_plates(self):
        """-> {plate no: use count} for every Protein G plate seen."""
        plates = self._read(CONSUMABLES_FILE).get("_proteing", {})
        return {k: len(v.get("batches", [])) for k, v in plates.items()
                if isinstance(v, dict)}

    # -- solution library --------------------------------------------------
    #
    # A solution is made in a batch by one analyst and then drawn down by
    # every plate the lab runs.  So the library holds, per solution, how much
    # one plate needs and the batches currently in the fridge.  Anyone can
    # add a batch; everyone sees the stock.

    def solution_library(self):
        """-> {name: {'per_plate_ml': float, 'batches': [...]}}"""
        lib = self._read(CONSUMABLES_FILE).get("_solutions", {})
        out = {}
        for name, rec in lib.items():
            if isinstance(rec, dict) and "batches" in rec:
                out[name] = rec
            elif isinstance(rec, str):
                # the v1.5 shape was {name: date} - carry it forward as a
                # batch of unknown size so nothing entered then is lost
                out[name] = {"per_plate_ml": 0.0,
                             "batches": [{"prepared": rec, "by": "",
                                          "made_ml": 0.0, "remaining_ml": 0.0,
                                          "used_by": []}]}
        return out

    def solutions(self):
        """-> {name: date of the batch in use}, for filling the worksheets."""
        out = {}
        for name, rec in self.solution_library().items():
            b = self._active_batch(rec)
            if b:
                out[name] = b.get("prepared", "")
        return out

    @staticmethod
    def _active_batch(rec):
        """The batch to draw from: oldest one that still has stock."""
        batches = [b for b in rec.get("batches", []) if isinstance(b, dict)]
        with_stock = [b for b in batches if float(b.get("remaining_ml") or 0) > 0]
        return (with_stock or batches or [None])[0]

    def per_plate(self, name):
        """-> (mL one plate needs, where it came from).

        A figure someone set by hand wins; otherwise the one worked out from
        the worksheet steps is used, so the library is useful the first time
        it is opened rather than after somebody fills in sixteen numbers.
        """
        rec = self.solution_library().get(name) or {}
        set_by_hand = rec.get("per_plate_ml")
        if set_by_hand:
            return float(set_by_hand), "set"
        derived = derived_per_plate(name)
        return (derived, "calculated") if derived else (0.0, "unknown")

    def set_per_plate(self, name, ml):
        """How much of `name` one plate needs.  Set once, shared by everyone."""
        def merge(data):
            rec = data.setdefault("_solutions", {}).setdefault(
                name, {"per_plate_ml": 0.0, "batches": []})
            if not isinstance(rec, dict) or "batches" not in rec:
                rec = {"per_plate_ml": 0.0, "batches": []}
                data["_solutions"][name] = rec
            rec["per_plate_ml"] = float(ml or 0)
        self._write(CONSUMABLES_FILE, merge)

    def add_solution_batch(self, name, prepared, made_ml, who=""):
        """Record a solution someone made.  Visible to the whole lab."""
        def merge(data):
            sols = data.setdefault("_solutions", {})
            rec = sols.get(name)
            if not isinstance(rec, dict) or "batches" not in rec:
                rec = {"per_plate_ml": 0.0, "batches": []}
                sols[name] = rec
            rec["batches"].insert(0, {
                "prepared": (prepared or "").strip(),
                "by": who,
                "made_ml": float(made_ml or 0),
                "remaining_ml": float(made_ml or 0),
                "used_by": [],
                "added": datetime.datetime.now().isoformat(timespec="seconds"),
            })
            del rec["batches"][12:]          # keep the history readable
        self._write(CONSUMABLES_FILE, merge)

    def stock_ml(self, name):
        rec = self.solution_library().get(name) or {}
        return sum(float(b.get("remaining_ml") or 0)
                   for b in rec.get("batches", []) if isinstance(b, dict))

    def plates_left(self, name):
        """-> how many more plates the stock covers, or None if unknown."""
        per, _ = self.per_plate(name)
        if per <= 0:
            return None
        return int(self.stock_ml(name) // per)

    def shortages(self, names):
        """-> [(name, stock_ml, per_plate_ml)] that cannot cover one plate."""
        short = []
        for n in names:
            per, _ = self.per_plate(n)
            if per <= 0:
                continue                      # no requirement known - can't judge
            if not self.has_batches(n):
                continue                      # nobody has recorded this one yet
            have = self.stock_ml(n)
            if have < per:
                short.append((n, have, per))
        return short

    def has_batches(self, name):
        """Whether anyone has ever recorded a batch of this.

        A solution nobody has recorded is *unknown*, not empty - the library
        starts out blank and crying shortage on all sixteen would be noise
        the analysts would learn to click through.  Once a batch exists the
        stock is tracked and a real shortage is worth stopping for.
        """
        rec = self.solution_library().get(name) or {}
        return bool([b for b in rec.get("batches", []) if isinstance(b, dict)])

    def consume(self, names, batch, who=""):
        """Draw one plate's worth of each solution down. -> [(name, left)].

        Keyed by the GA batch, so rebuilding a worksheet for the same plate
        does not double-count, and two analysts on two plates both count.
        """
        batch = (batch or "").strip()
        if not batch:
            return []

        def merge(data):
            sols = data.setdefault("_solutions", {})
            for n in names:
                rec = sols.get(n)
                if not isinstance(rec, dict) or "batches" not in rec:
                    continue
                per = float(rec.get("per_plate_ml") or 0) or (
                    derived_per_plate(n) or 0)
                if per <= 0:
                    continue
                if any(batch in b.get("used_by", [])
                       for b in rec["batches"] if isinstance(b, dict)):
                    continue                  # this plate already drew its share
                need = per
                for b in rec["batches"]:
                    if not isinstance(b, dict) or need <= 0:
                        continue
                    have = float(b.get("remaining_ml") or 0)
                    if have <= 0:
                        continue
                    take = min(have, need)
                    b["remaining_ml"] = round(have - take, 2)
                    b.setdefault("used_by", []).append(batch)
                    need -= take
        self._write(CONSUMABLES_FILE, merge)
        return [(n, self.stock_ml(n)) for n in names]

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
