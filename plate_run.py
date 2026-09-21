#!/usr/bin/env python3
"""
One plate, start to finish.

The two original tabs each do one job well but leave the analyst to remember
the order and to retype the same numbers into both.  This tab is the job as
it is actually done:

    1  open the Pippeting List for the plate
    2  say which worksheet and storage numbers were taken for it
    3  confirm the filter plate / enzyme LOTs and the solution dates
    4  print the IgG isolation worksheet and go and do the isolation
    -- next day --
    5  drop in the NanoDrop .txt
    6  get the concentration workbook, and the deglycosylation and
       clean-up worksheets, with the average dried IgG already worked out

Nothing is ever locked.  Every output can be rebuilt and saved again at any
point, in any order - the steps are the normal path, not a cage.  Step 4 is
the only one that has to happen before step 5 in the real world, and that is
the bench's constraint, not this program's.

What was entered is remembered per plate, so day 2 does not mean retyping
day 1.  The LOTs are remembered for everyone, because the lab shares the
physical plates and solution batches.
"""
import os
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import ws_sheets
import ws_fill
import store as store_mod
import layout_colours


def _scrollable(parent):
    """A frame that scrolls, because this form is taller than a laptop screen."""
    outer = ttk.Frame(parent)
    canvas = tk.Canvas(outer, highlightthickness=0)
    bar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas, padding=12)
    window = canvas.create_window((0, 0), window=inner, anchor="nw")

    def resized(_=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(window, width=canvas.winfo_width())

    inner.bind("<Configure>", resized)
    canvas.bind("<Configure>", resized)
    canvas.configure(yscrollcommand=bar.set)
    canvas.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")

    def wheel(e):
        canvas.yview_scroll(-1 * (e.delta // 120), "units")

    # bound while the pointer is over this tab, not bind_all - otherwise the
    # wheel keeps scrolling this canvas while another tab is showing
    inner.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", wheel))
    inner.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))
    return outer, inner


class Step(ttk.LabelFrame):
    def __init__(self, parent, n, title, **kw):
        super().__init__(parent, text=f"  {n}.  {title}  ", padding=10, **kw)
        self.columnconfigure(1, weight=1)


class PlateRunTab(ttk.Frame):
    """The whole day-1-to-day-2 run for one plate."""

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.store = store_mod.Store(log=app.say)
        self.layout = None
        self.colours = {}
        self.sheet_used = ""

        outer, body = _scrollable(self)
        outer.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)

        self.lay_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.txt_var = tk.StringVar()
        self.batch_var = tk.StringVar()
        self.initials_var = tk.StringVar()
        self.date_var = tk.StringVar(
            value=datetime.date.today().strftime("%d.%m.%Y"))
        self.aliquot_var = tk.StringVar(value="40")
        self.blank_var = tk.StringVar(value=ws_fill.WS_DIR)
        self.enzyme_var = tk.StringVar(value="30")
        self.skip_solutions = tk.BooleanVar(value=False)
        self.num_vars = {}
        self.cons_vars = {}
        self.cons_boxes = {}
        self.sol_vars = {}

        r = 0
        r = self._step_plate(body, r)
        r = self._step_numbers(body, r)
        r = self._step_consumables(body, r)
        r = self._step_solutions(body, r)
        r = self._step_day1(body, r)
        r = self._step_day2(body, r)

        where = ("the share" if not self.store.using_local
                 else "this PC only - the share was unreachable")
        ttk.Label(body, text=f"LOTs and plate progress are remembered on {where}.",
                  foreground="#666666").grid(row=r, column=0, sticky="w", pady=(4, 10))

    # ---------------------------------------------------------------- steps

    def _step_plate(self, body, r):
        s = Step(body, 1, "The plate")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(s, text="Pippeting List (.xlsx)").grid(row=0, column=0, sticky="w")
        ttk.Entry(s, textvariable=self.lay_var).grid(row=0, column=1, sticky="ew",
                                                     padx=(8, 6))
        ttk.Button(s, text="Browse...", command=self.pick_layout).grid(row=0, column=2)

        ttk.Label(s, text="Save everything into").grid(row=1, column=0, sticky="w",
                                                      pady=(6, 0))
        ttk.Entry(s, textvariable=self.out_var).grid(row=1, column=1, sticky="ew",
                                                     padx=(8, 6), pady=(6, 0))
        ttk.Button(s, text="Browse...", command=self.pick_out).grid(row=1, column=2,
                                                                    pady=(6, 0))

        row = ttk.Frame(s)
        row.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        for i, (lbl, var, w) in enumerate((("GA batch No.", self.batch_var, 18),
                                           ("Analyst initials", self.initials_var, 6),
                                           ("Date", self.date_var, 12),
                                           ("Aliquot dried down (µL)",
                                            self.aliquot_var, 6))):
            ttk.Label(row, text=lbl).grid(row=0, column=i * 2, sticky="w",
                                          padx=(0 if i == 0 else 18, 6))
            ttk.Entry(row, textvariable=var, width=w).grid(row=0, column=i * 2 + 1,
                                                           sticky="w")

        self.plate_info = ttk.Label(s, text="No plate loaded yet.",
                                    foreground="#666666")
        self.plate_info.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        return r + 1

    def _step_numbers(self, body, r):
        s = Step(body, 2, "Worksheet and storage numbers taken for this plate")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(s, text="Working worksheets", foreground="#666666").grid(
            row=0, column=0, sticky="w")
        for i, (key, _, name) in enumerate(ws_sheets.WORKSHEETS):
            ttk.Label(s, text=name).grid(row=i + 1, column=0, sticky="w", pady=2)
            v = tk.StringVar()
            self.num_vars[key] = v
            ttk.Entry(s, textvariable=v, width=14).grid(row=i + 1, column=1,
                                                        sticky="w", padx=(10, 30))

        ttk.Label(s, text="Storage (GBL-WS-002)", foreground="#666666").grid(
            row=0, column=2, sticky="w")
        for i, (key, label) in enumerate(ws_sheets.STORAGE):
            ttk.Label(s, text=label).grid(row=i + 1, column=2, sticky="w", pady=2)
            v = tk.StringVar()
            self.num_vars[key] = v
            ttk.Entry(s, textvariable=v, width=14).grid(row=i + 1, column=3,
                                                        sticky="w", padx=(10, 0))

        extra = ttk.Frame(s)
        extra.grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))
        for i, (key, label) in enumerate((("reception", "Sample reception worksheet no."),
                                          ("sample_storage", "Sample storage worksheet no."))):
            ttk.Label(extra, text=label).grid(row=0, column=i * 2, sticky="w",
                                              padx=(0 if i == 0 else 24, 8))
            v = tk.StringVar()
            self.num_vars[key] = v
            ttk.Entry(extra, textvariable=v, width=14).grid(row=0, column=i * 2 + 1,
                                                            sticky="w")
        return r + 1

    def _step_consumables(self, body, r):
        s = Step(body, 3, "Filter plates and enzyme  -  the last one used is offered")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))

        for i, (key, label, _hist) in enumerate(store_mod.CONSUMABLE_FIELDS):
            ttk.Label(s, text=label).grid(row=i, column=0, sticky="w", pady=2)
            v = tk.StringVar()
            self.cons_vars[key] = v
            box = ttk.Combobox(s, textvariable=v, width=28,
                               values=self.store.options(key))
            box.grid(row=i, column=1, sticky="w", padx=(10, 10), pady=2)
            self.cons_boxes[key] = box
            opts = self.store.options(key)
            if opts:
                v.set(opts[0])

        ttk.Label(s, text="PNGase F vial", foreground="#666666").grid(
            row=len(store_mod.CONSUMABLE_FIELDS), column=0, sticky="w", pady=(8, 0))
        vial = ttk.Frame(s)
        vial.grid(row=len(store_mod.CONSUMABLE_FIELDS), column=1, sticky="w",
                  padx=(10, 0), pady=(8, 0))
        ttk.Radiobutton(vial, text="30 µg", value="30",
                        variable=self.enzyme_var).grid(row=0, column=0, padx=(0, 14))
        ttk.Radiobutton(vial, text="50 µg", value="50",
                        variable=self.enzyme_var).grid(row=0, column=1)
        ttk.Label(vial, text="- decides which 'Enzyme LOT' line is filled",
                  foreground="#666666").grid(row=0, column=2, padx=(14, 0))

        ttk.Label(s, text="Anything left empty stays empty on the worksheet for "
                          "you to write in.", foreground="#666666").grid(
            row=len(store_mod.CONSUMABLE_FIELDS) + 1, column=0, columnspan=3,
            sticky="w", pady=(8, 0))
        return r + 1

    def _step_solutions(self, body, r):
        s = Step(body, 4, "Solution preparation dates  -  optional")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))

        ttk.Checkbutton(s, text="Skip these and fill the tables in by hand after "
                               "printing", variable=self.skip_solutions).grid(
            row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))

        known = self.store.solutions()
        col = 0
        for key, _, name in ws_sheets.WORKSHEETS:
            frame = ttk.Frame(s)
            frame.grid(row=1, column=col, sticky="nw", padx=(0, 24))
            ttk.Label(frame, text=name, foreground="#666666").grid(
                row=0, column=0, columnspan=2, sticky="w")
            for i, sol in enumerate(store_mod.SOLUTIONS[key]):
                label = store_mod.SOLUTION_LABELS.get(sol, sol)
                ttk.Label(frame, text=label).grid(row=i + 1, column=0, sticky="w",
                                                  pady=1)
                v = tk.StringVar(value=known.get(sol, ""))
                self.sol_vars[sol] = v
                ttk.Entry(frame, textvariable=v, width=12).grid(
                    row=i + 1, column=1, sticky="w", padx=(8, 0), pady=1)
            col += 1
        return r + 1

    def _step_day1(self, body, r):
        s = Step(body, 5, "Day 1  -  IgG isolation")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(s, text="Fills and saves the IgG isolation worksheet with the "
                          "coloured plate layout.").grid(row=0, column=0,
                                                         columnspan=3, sticky="w")
        btns = ttk.Frame(s)
        btns.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.iso_btn = ttk.Button(btns, text="Build isolation worksheet",
                                  command=self.build_isolation)
        self.iso_btn.grid(row=0, column=0)
        ttk.Button(btns, text="Open", command=lambda: self.open_last("isolation")).grid(
            row=0, column=1, padx=(8, 0))
        ttk.Button(btns, text="Print", command=lambda: self.print_last("isolation")).grid(
            row=0, column=2, padx=(8, 0))
        self.iso_note = ttk.Label(s, text="", foreground="#666666")
        self.iso_note.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        return r + 1

    def _step_day2(self, body, r):
        s = Step(body, 6, "Day 2  -  after the NanoDrop")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(s, text="NanoDrop concentrations (.txt)").grid(row=0, column=0,
                                                                 sticky="w")
        ttk.Entry(s, textvariable=self.txt_var).grid(row=0, column=1, sticky="ew",
                                                     padx=(8, 6))
        ttk.Button(s, text="Browse...", command=self.pick_txt).grid(row=0, column=2)

        ttk.Label(s, text="Gives the concentration workbook, plus the "
                          "deglycosylation and clean-up worksheets with the "
                          "average dried IgG filled in.").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        btns = ttk.Frame(s)
        btns.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.day2_btn = ttk.Button(btns, text="Build workbook + both worksheets",
                                   command=self.build_day2)
        self.day2_btn.grid(row=0, column=0)
        ttk.Button(btns, text="Open folder", command=self.open_folder).grid(
            row=0, column=1, padx=(8, 0))
        ttk.Button(btns, text="Print deglycosylation",
                   command=lambda: self.print_last("deglyco")).grid(row=0, column=2,
                                                                    padx=(8, 0))
        ttk.Button(btns, text="Print clean up",
                   command=lambda: self.print_last("cleanup")).grid(row=0, column=3,
                                                                    padx=(8, 0))
        self.day2_note = ttk.Label(s, text="", foreground="#666666")
        self.day2_note.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
        return r + 1

    # -------------------------------------------------------------- pickers

    def pick_layout(self):
        p = filedialog.askopenfilename(
            title="Pippeting List for the plate",
            filetypes=[("Excel files", "*.xlsx *.xlsm"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.lay_var.get()) or None)
        if p:
            self.load_layout(_norm(p))

    def pick_out(self):
        p = filedialog.askdirectory(title="Save everything into",
                                    initialdir=self.out_var.get() or None)
        if p:
            self.out_var.set(_norm(p))

    def pick_txt(self):
        p = filedialog.askopenfilename(
            title="NanoDrop concentrations",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=(os.path.dirname(self.txt_var.get())
                        or os.path.dirname(self.lay_var.get()) or None))
        if p:
            self.txt_var.set(_norm(p))

    # --------------------------------------------------------------- layout

    def load_layout(self, path):
        """Read the plate, then restore whatever was already entered for it."""
        from igg_conc_gui import read_layout, BuildError
        self.lay_var.set(path)
        self.app.clear()
        try:
            layout, sheet, conflicts = read_layout(path, keep_filler=True)
        except BuildError as e:
            messagebox.showerror("Could not read the plate layout", str(e))
            return
        self.layout = layout
        self.sheet_used = sheet
        self.colours = layout_colours.read_colours(path, sheet)

        batch = ws_sheets.batch_from_path(path)
        if batch:
            self.batch_var.set(batch)
        if not self.out_var.get():
            self.out_var.set(os.path.dirname(path))

        named = sum(1 for v in layout.values() if v)
        stands = sorted({v.rsplit("_", 1)[0] for v in layout.values()
                         if v and v.startswith("STAND_")})
        blanks = [v for v in layout.values() if v and v.lower().startswith("blank")]
        self.plate_info.config(
            text=f"sheet {sheet!r}  -  {named} wells, "
                 f"{len(stands)} standard sets ({', '.join(stands)}), "
                 f"{len(blanks)} blanks, {len(self.colours)} coloured wells")
        for w, v1, v2 in conflicts[:10]:
            self.app.say(f"  !! layout conflict {w}: {v1!r} vs {v2!r}")

        self.restore(batch)

    def restore(self, batch):
        saved = self.store.run(batch)
        if not saved:
            self.app.say(f"New plate {batch or ''} - nothing remembered yet.")
            return
        for key, var in self.num_vars.items():
            if saved.get("numbers", {}).get(key):
                var.set(saved["numbers"][key])
        for key, var in self.cons_vars.items():
            if saved.get("consumables", {}).get(key):
                var.set(saved["consumables"][key])
        for key, var in self.sol_vars.items():
            if saved.get("solutions", {}).get(key):
                var.set(saved["solutions"][key])
        for key, var in (("initials", self.initials_var), ("date", self.date_var),
                         ("aliquot", self.aliquot_var), ("enzyme", self.enzyme_var),
                         ("nanodrop", self.txt_var), ("out", self.out_var)):
            if saved.get(key):
                var.set(saved[key])
        self.app.say(f"Restored what was entered for {batch} "
                     f"(saved {saved.get('saved', '?')}).")
        done = saved.get("built", [])
        if done:
            self.app.say(f"  already built: {', '.join(done)}")

    # ---------------------------------------------------------------- state

    def gather(self):
        """-> everything the fill needs, or raise ValueError with the reason."""
        lay = _norm(self.lay_var.get().strip())
        out = _norm(self.out_var.get().strip())
        if not lay or not os.path.isfile(lay):
            raise ValueError("Pick the Pippeting List for the plate first.")
        if not out or not os.path.isdir(out):
            raise ValueError("Pick an existing folder to save into.")
        if self.layout is None:
            self.load_layout(lay)
        if self.layout is None:
            raise ValueError("The plate layout could not be read.")
        try:
            aliquot = float(self.aliquot_var.get().strip().replace(",", "."))
            if aliquot <= 0:
                raise ValueError
        except ValueError:
            raise ValueError("The aliquot volume must be a positive number, e.g. 40.")
        try:
            date = datetime.datetime.strptime(self.date_var.get().strip(),
                                              "%d.%m.%Y").date()
        except ValueError:
            raise ValueError("The date must look like 21.09.2026.")

        cons = {k: v.get().strip() for k, v in self.cons_vars.items()}
        # the worksheet has a separate Enzyme LOT line per vial size
        cons[f"enzyme_lot_{self.enzyme_var.get()}"] = cons.pop("enzyme_lot", "")
        sols = ({} if self.skip_solutions.get()
                else {k: v.get().strip() for k, v in self.sol_vars.items()
                      if v.get().strip()})
        return {
            "lay": lay, "out": out, "aliquot": aliquot, "date": date,
            "batch": self.batch_var.get().strip(),
            "initials": self.initials_var.get().strip().upper(),
            "numbers": {k: v.get().strip() for k, v in self.num_vars.items()},
            "consumables": cons, "solutions": sols,
        }

    def save_state(self, built=None):
        batch = self.batch_var.get().strip()
        if not batch:
            # Everything is filed under the GA batch number.  Without one the
            # run cannot be remembered, and the analyst would silently lose
            # day 1's numbers when they come back on day 2 - so say so.
            self.app.say("  !! no GA batch number - nothing was remembered for "
                         "this plate.  Type the batch number to keep it.")
            return
        prior = self.store.run(batch).get("built", [])
        state = {
            "numbers": {k: v.get().strip() for k, v in self.num_vars.items()},
            "consumables": {k: v.get().strip() for k, v in self.cons_vars.items()},
            "solutions": {k: v.get().strip() for k, v in self.sol_vars.items()
                          if v.get().strip()},
            "initials": self.initials_var.get().strip().upper(),
            "date": self.date_var.get().strip(),
            "aliquot": self.aliquot_var.get().strip(),
            "enzyme": self.enzyme_var.get(),
            "nanodrop": _norm(self.txt_var.get().strip()),
            "out": _norm(self.out_var.get().strip()),
            "layout": _norm(self.lay_var.get().strip()),
            "built": sorted(set(prior) | set(built or [])),
        }
        self.store.save_run(batch, state)

    def remember_consumables(self):
        who = self.initials_var.get().strip().upper()
        for key, var in self.cons_vars.items():
            self.store.remember(key, var.get().strip(), who)
            self.cons_boxes[key].configure(values=self.store.options(key))
        if not self.skip_solutions.get():
            for name, var in self.sol_vars.items():
                self.store.remember_solution(name, var.get().strip())

    # --------------------------------------------------------------- builds

    def _fill(self, keys, spec, avg):
        sources = ws_fill.discover(_norm(self.blank_var.get().strip()) or None)
        for k in keys:
            if k not in sources:
                name = dict((a, n) for a, _, n in ws_sheets.WORKSHEETS)[k]
                self.app.say(f"  !! no blank worksheet found for {name}")
        return ws_fill.fill_all(
            sources, spec["out"], self.layout, batch=spec["batch"],
            numbers=spec["numbers"], date=spec["date"], initials=spec["initials"],
            avg_conc=avg, aliquot_ul=spec["aliquot"], pages=keys,
            colours=self.colours, consumables=spec["consumables"],
            solutions=spec["solutions"], log=self.app.say)

    def build_isolation(self):
        try:
            spec = self.gather()
        except ValueError as e:
            messagebox.showwarning("Not ready", str(e))
            return
        missing = [n for k, _, n in ws_sheets.WORKSHEETS
                   if k == "isolation" and not spec["numbers"].get(k)]
        missing += [s for k, s in ws_sheets.STORAGE if not spec["numbers"].get(k)]
        if missing and not messagebox.askyesno(
                "Numbers missing",
                "Nothing entered for:\n\n  - " + "\n  - ".join(missing)
                + "\n\nThose stay blank on the worksheet.  Build anyway?"):
            return

        def work():
            written = self._fill(["isolation"], spec, None)
            self.built = getattr(self, "built", {})
            if written:
                self.built["isolation"] = written[0]
            self.remember_consumables()
            self.save_state(["isolation"])
            self.app.say("")
            self.app.say(f"Saved into {spec['out']}")
            self.iso_note.config(
                text=f"Built {os.path.basename(written[0])}" if written else "")

        self.app.go(self.iso_btn, spec["out"], False, work)

    def build_day2(self):
        from igg_conc_gui import build, mean_concentrations
        try:
            spec = self.gather()
        except ValueError as e:
            messagebox.showwarning("Not ready", str(e))
            return
        txt = _norm(self.txt_var.get().strip())
        if not txt or not os.path.isfile(txt):
            messagebox.showwarning(
                "NanoDrop file",
                "Pick the NanoDrop .txt for this plate.\n\nWithout it the average "
                "amount of dried IgG cannot be worked out, and the concentration "
                "workbook cannot be built.")
            return

        def work():
            wb = os.path.join(spec["out"], f"{spec['batch'] or 'plate'}.xlsx")
            build(txt, spec["lay"], wb, strict=True, log=self.app.say)
            self.app.say("")
            avg = mean_concentrations(txt, self.layout)
            self.app.say(f"Avg dried IgG     : DBS {avg[0] * spec['aliquot']:.1f} ug"
                         + (f" / standards {avg[1] * spec['aliquot']:.1f} ug"
                            if avg[1] is not None else ""))
            self.app.say("")
            written = self._fill(["deglyco", "cleanup"], spec, avg)
            self.built = getattr(self, "built", {})
            for key, path in zip(["deglyco", "cleanup"], written):
                self.built[key] = path
            self.remember_consumables()
            self.save_state(["deglyco", "cleanup"])
            self.app.say("")
            self.app.say(f"Saved {len(written) + 1} files into {spec['out']}")
            self.day2_note.config(
                text="Built the workbook, deglycosylation and clean-up worksheets.")

        self.app.go(self.day2_btn, spec["out"], False, work)

    # ---------------------------------------------------------------- open

    def _path_for(self, key):
        built = getattr(self, "built", {})
        if built.get(key) and os.path.isfile(built[key]):
            return built[key]
        out = _norm(self.out_var.get().strip())
        batch = self.batch_var.get().strip()
        name = dict((k, n) for k, _, n in ws_sheets.WORKSHEETS)[key]
        guess = os.path.join(out, f"{batch + ' ' if batch else ''}{name} worksheet.pdf")
        return guess if os.path.isfile(guess) else None

    def open_last(self, key):
        p = self._path_for(key)
        if not p:
            messagebox.showinfo("Not built yet",
                                "That worksheet has not been built into this folder yet.")
            return
        try:
            os.startfile(p)
        except Exception as e:
            messagebox.showerror("Could not open it", str(e))

    def print_last(self, key):
        p = self._path_for(key)
        if not p:
            messagebox.showinfo("Not built yet",
                                "That worksheet has not been built into this folder yet.")
            return
        try:
            os.startfile(p, "print")
        except Exception:
            # no print verb registered for .pdf - open it and let the reader print
            try:
                os.startfile(p)
                self.app.say("  (no print handler registered - opened it instead)")
            except Exception as e:
                messagebox.showerror("Could not print it", str(e))

    def open_folder(self):
        out = _norm(self.out_var.get().strip())
        if out and os.path.isdir(out):
            os.startfile(out)


def _norm(path):
    return os.path.normpath(path) if path else path
