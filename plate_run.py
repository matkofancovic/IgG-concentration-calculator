#!/usr/bin/env python3
"""
One window, one plate at a time.

There used to be three tabs, and each of them asked for the plate layout
again - two of them for the NanoDrop export as well.  That is the same two
files typed in up to three times to produce outputs that all describe the
same plate.  So: one window.  The Pippeting List goes in once, the NanoDrop
export goes in once, and every output comes from those.

    left    every plate the program has seen, newest first, with how far it
            got.  Click one and it comes back exactly as it was left.
    right   the run itself, top to bottom in the order it happens.

A GlycanAge plate is worked over two days - isolation, then the NanoDrop,
then deglycosylation and clean-up - so the form has to survive being closed
and reopened.  It does: everything is filed under the GA batch number.

Nothing is ever locked.  Every output can be rebuilt and saved again at any
point, in any order.  The numbered sections are the normal path, not a cage.
"""
import os
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import ws_sheets
import ws_fill
import store as store_mod
import layout_colours

DONE, PART, NEW = "✓", "◐", "·"


def _norm(path):
    return os.path.normpath(path) if path else path


def _scrollable(parent):
    """A frame that scrolls - the form is taller than a laptop screen."""
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

    # only while the pointer is over the form
    inner.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", wheel))
    inner.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))
    return outer, inner


class Section(ttk.LabelFrame):
    def __init__(self, parent, n, title, **kw):
        super().__init__(parent, text=f"  {n}.  {title}  ", padding=10, **kw)
        self.columnconfigure(1, weight=1)


class PlateList(ttk.Frame):
    """Every plate seen so far, newest first, with how far each one got."""

    def __init__(self, parent, on_pick, store):
        super().__init__(parent, padding=(10, 12, 6, 12))
        self.on_pick = on_pick
        self.store = store
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="Plates", font=("", 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6))

        self.tree = ttk.Treeview(self, columns=("state",), show="tree headings",
                                 selectmode="browse", height=18)
        self.tree.heading("#0", text="GA batch")
        self.tree.heading("state", text="")
        self.tree.column("#0", width=160, stretch=True)
        self.tree.column("state", width=34, stretch=False, anchor="center")
        self.tree.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._picked)

        self.tree.tag_configure("done", foreground="#1a7f37")
        self.tree.tag_configure("part", foreground="#9a6700")

        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="New plate...", command=self.new_plate).grid(
            row=0, column=0, sticky="w")
        ttk.Button(btns, text="Remove", command=self.forget).grid(
            row=0, column=1, sticky="w", padx=(6, 0))

        self.key = ttk.Label(
            self, foreground="#666666", justify="left",
            text=f"{DONE} all three worksheets built\n"
                 f"{PART} part way through\n"
                 f"{NEW} nothing built yet")
        self.key.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.refresh()

    def refresh(self, select=None):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._rows = {}
        for row in self.store.plates():
            built = row["built"]
            mark = DONE if row["done"] else (PART if built else NEW)
            tag = "done" if row["done"] else ("part" if built else "")
            iid = self.tree.insert("", "end", text=row["batch"],
                                   values=(mark,), tags=(tag,))
            self._rows[iid] = row
        if select:
            for iid, row in self._rows.items():
                if row["batch"] == select:
                    self.tree.selection_set(iid)
                    self.tree.see(iid)
                    break

    def _picked(self, _=None):
        sel = self.tree.selection()
        if sel and sel[0] in self._rows:
            self.on_pick(self._rows[sel[0]])

    def selected_batch(self):
        sel = self.tree.selection()
        return self._rows[sel[0]]["batch"] if sel and sel[0] in self._rows else None

    def new_plate(self):
        p = filedialog.askopenfilename(
            title="Pippeting List for the new plate",
            filetypes=[("Excel files", "*.xlsx *.xlsm"), ("All files", "*.*")])
        if p:
            self.on_pick({"batch": None, "layout": _norm(p)})

    def forget(self):
        batch = self.selected_batch()
        if not batch:
            return
        if messagebox.askyesno(
                "Remove from the list?",
                f"Forget what was entered for {batch}?\n\n"
                "The worksheets and workbook already saved are NOT deleted - "
                "only this program's memory of the plate."):
            self.store.forget_run(batch)
            self.refresh()


class PlateRunPanel(ttk.Frame):
    """The run itself: two files in, every output out."""

    def __init__(self, parent, app, store, on_built=None):
        super().__init__(parent)
        self.app = app
        self.store = store
        self.on_built = on_built or (lambda *_: None)
        self.layout = None
        self.colours = {}
        self.sheet_used = ""
        self.built = {}

        outer, body = _scrollable(self)
        outer.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)

        self.lay_var = tk.StringVar()
        self.txt_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.batch_var = tk.StringVar()
        self.initials_var = tk.StringVar()
        self.date_var = tk.StringVar(
            value=datetime.date.today().strftime("%d.%m.%Y"))
        self.aliquot_var = tk.StringVar(value="40")
        self.blank_var = tk.StringVar(value=ws_fill.WS_DIR)
        self.enzyme_var = tk.StringVar(value="30")
        self.strict_var = tk.BooleanVar(value=True)
        self.attach_var = tk.BooleanVar(value=False)
        self.skip_solutions = tk.BooleanVar(value=False)
        self.num_vars, self.cons_vars, self.cons_boxes, self.sol_vars = {}, {}, {}, {}

        r = 0
        r = self._sec_files(body, r)
        r = self._sec_numbers(body, r)
        r = self._sec_consumables(body, r)
        r = self._sec_solutions(body, r)
        r = self._sec_build(body, r)
        r = self._sec_settings(body, r)

        where = ("the share" if not self.store.using_local
                 else "this PC only - the share was unreachable")
        ttk.Label(body, text=f"LOTs and plate progress are remembered on {where}.",
                  foreground="#666666").grid(row=r, column=0, sticky="w",
                                             pady=(4, 10))

    # ------------------------------------------------------------- sections

    def _sec_files(self, body, r):
        s = Section(body, 1, "The plate  -  both files go in here, once")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))

        for i, (label, var, cmd) in enumerate((
                ("Pippeting List (.xlsx)", self.lay_var, self.pick_layout),
                ("NanoDrop concentrations (.txt)", self.txt_var, self.pick_txt),
                ("Save everything into", self.out_var, self.pick_out))):
            ttk.Label(s, text=label).grid(row=i, column=0, sticky="w",
                                          pady=(0 if i == 0 else 6, 0))
            ttk.Entry(s, textvariable=var).grid(row=i, column=1, sticky="ew",
                                                padx=(8, 6),
                                                pady=(0 if i == 0 else 6, 0))
            ttk.Button(s, text="Browse...", command=cmd).grid(
                row=i, column=2, pady=(0 if i == 0 else 6, 0))

        ttk.Label(s, text="The .txt is only needed on day 2 - leave it empty until "
                          "the NanoDrop is done.", foreground="#666666").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

        row = ttk.Frame(s)
        row.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
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
        self.plate_info.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))
        return r + 1

    def _sec_numbers(self, body, r):
        s = Section(body, 2, "Worksheet and storage numbers taken for this plate")
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
        for i, (key, label) in enumerate(
                (("reception", "Sample reception worksheet no."),
                 ("sample_storage", "Sample storage worksheet no."))):
            ttk.Label(extra, text=label).grid(row=0, column=i * 2, sticky="w",
                                              padx=(0 if i == 0 else 24, 8))
            v = tk.StringVar()
            self.num_vars[key] = v
            ttk.Entry(extra, textvariable=v, width=14).grid(row=0, column=i * 2 + 1,
                                                            sticky="w")
        return r + 1

    def _sec_consumables(self, body, r):
        s = Section(body, 3, "Filter plates and enzyme  -  the last one used is offered")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))

        n = len(store_mod.CONSUMABLE_FIELDS)
        for i, (key, label, _h) in enumerate(store_mod.CONSUMABLE_FIELDS):
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
            row=n, column=0, sticky="w", pady=(8, 0))
        vial = ttk.Frame(s)
        vial.grid(row=n, column=1, sticky="w", padx=(10, 0), pady=(8, 0))
        ttk.Radiobutton(vial, text="30 µg", value="30",
                        variable=self.enzyme_var).grid(row=0, column=0, padx=(0, 14))
        ttk.Radiobutton(vial, text="50 µg", value="50",
                        variable=self.enzyme_var).grid(row=0, column=1)
        ttk.Label(vial, text="- decides which 'Enzyme LOT' line is filled",
                  foreground="#666666").grid(row=0, column=2, padx=(14, 0))

        ttk.Label(s, text="Check the offered LOT against the label on the bench "
                          "before printing.  Anything left empty prints empty.",
                  foreground="#666666").grid(row=n + 1, column=0, columnspan=3,
                                             sticky="w", pady=(8, 0))
        return r + 1

    def _sec_solutions(self, body, r):
        s = Section(body, 4, "Solution preparation dates  -  optional")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))

        ttk.Checkbutton(s, text="Skip these and fill the tables in by hand after "
                               "printing", variable=self.skip_solutions).grid(
            row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))

        known = self.store.solutions()
        for col, (key, _, name) in enumerate(ws_sheets.WORKSHEETS):
            frame = ttk.Frame(s)
            frame.grid(row=1, column=col, sticky="nw", padx=(0, 24))
            ttk.Label(frame, text=name, foreground="#666666").grid(
                row=0, column=0, columnspan=2, sticky="w")
            for i, sol in enumerate(store_mod.SOLUTIONS[key]):
                ttk.Label(frame, text=store_mod.SOLUTION_LABELS.get(sol, sol)).grid(
                    row=i + 1, column=0, sticky="w", pady=1)
                v = tk.StringVar(value=known.get(sol, ""))
                self.sol_vars[sol] = v
                ttk.Entry(frame, textvariable=v, width=12).grid(
                    row=i + 1, column=1, sticky="w", padx=(8, 0), pady=1)
        return r + 1

    def _sec_build(self, body, r):
        s = Section(body, 5, "Build  -  any of these, in any order, as often as you like")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))

        day1 = ttk.Frame(s)
        day1.grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(day1, text="Day 1", width=8, foreground="#666666").grid(
            row=0, column=0, sticky="w")
        self.iso_btn = ttk.Button(day1, text="IgG isolation worksheet",
                                  command=self.build_isolation)
        self.iso_btn.grid(row=0, column=1)
        ttk.Button(day1, text="Open", width=7,
                   command=lambda: self.open_built("isolation")).grid(
            row=0, column=2, padx=(6, 0))
        ttk.Button(day1, text="Print", width=7,
                   command=lambda: self.print_built("isolation")).grid(
            row=0, column=3, padx=(6, 0))

        day2 = ttk.Frame(s)
        day2.grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(day2, text="Day 2", width=8, foreground="#666666").grid(
            row=0, column=0, sticky="w")
        self.day2_btn = ttk.Button(day2, text="Workbook + deglyco + clean up",
                                   command=self.build_day2)
        self.day2_btn.grid(row=0, column=1)
        ttk.Button(day2, text="Print deglyco", command=lambda:
                   self.print_built("deglyco")).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(day2, text="Print clean up", command=lambda:
                   self.print_built("cleanup")).grid(row=0, column=3, padx=(6, 0))
        ttk.Button(day2, text="Open folder", command=self.open_folder).grid(
            row=0, column=4, padx=(6, 0))

        opts = ttk.Frame(s)
        opts.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))
        ttk.Checkbutton(opts, text="Stop if the layout does not match the readings",
                        variable=self.strict_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(opts, text="Separate sheet to attach, instead of filling "
                                   "the worksheets",
                        variable=self.attach_var).grid(row=1, column=0, sticky="w")

        self.note = ttk.Label(s, text="", foreground="#666666")
        self.note.grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))
        return r + 1

    def _sec_settings(self, body, r):
        s = Section(body, 6, "Where the blank worksheets live")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))
        ttk.Entry(s, textvariable=self.blank_var).grid(row=0, column=0, sticky="ew",
                                                       padx=(0, 6))
        s.columnconfigure(0, weight=1)
        ttk.Button(s, text="Browse...", command=self.pick_blanks).grid(row=0, column=1)
        ttk.Label(s, text="Newest revision of each document code wins, so a new "
                          "release is picked up on its own.",
                  foreground="#666666").grid(row=1, column=0, columnspan=2,
                                             sticky="w", pady=(4, 0))
        return r + 1

    # -------------------------------------------------------------- pickers

    def pick_layout(self):
        p = filedialog.askopenfilename(
            title="Pippeting List for the plate",
            filetypes=[("Excel files", "*.xlsx *.xlsm"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.lay_var.get()) or None)
        if p:
            self.load(_norm(p))

    def pick_txt(self):
        p = filedialog.askopenfilename(
            title="NanoDrop concentrations",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=(os.path.dirname(self.txt_var.get())
                        or os.path.dirname(self.lay_var.get()) or None))
        if p:
            self.txt_var.set(_norm(p))

    def pick_out(self):
        p = filedialog.askdirectory(title="Save everything into",
                                    initialdir=self.out_var.get() or None)
        if p:
            self.out_var.set(_norm(p))

    def pick_blanks(self):
        p = filedialog.askdirectory(title="Folder holding the blank worksheets",
                                    initialdir=self.blank_var.get() or None)
        if p:
            self.blank_var.set(_norm(p))

    # --------------------------------------------------------------- plate

    def load(self, path, batch=None):
        """Read the plate, then put back whatever was entered for it before."""
        from igg_conc_gui import read_layout, BuildError
        path = _norm(path)
        if not path or not os.path.isfile(path):
            messagebox.showerror(
                "Not found",
                f"The Pippeting List for this plate is not where it was:\n\n{path}\n\n"
                "Pick it again with Browse and it will be relinked.")
            return
        self.app.clear()
        try:
            layout, sheet, conflicts = read_layout(path, keep_filler=True)
        except BuildError as e:
            messagebox.showerror("Could not read the plate layout", str(e))
            return

        self.layout, self.sheet_used = layout, sheet
        self.colours = layout_colours.read_colours(path, sheet)
        self.built = {}
        self.lay_var.set(path)

        found = batch or ws_sheets.batch_from_path(path)
        if found:
            self.batch_var.set(found)
        if not self.out_var.get():
            self.out_var.set(os.path.dirname(path))

        stands = sorted({v.rsplit("_", 1)[0] for v in layout.values()
                         if v and v.startswith("STAND_")})
        blanks = [v for v in layout.values() if v and v.lower().startswith("blank")]
        self.plate_info.config(
            text=f"sheet {sheet!r}  -  {len(layout)} wells, "
                 f"{len(stands)} standard sets ({', '.join(stands)}), "
                 f"{len(blanks)} blanks, {len(self.colours)} coloured wells")
        for w, v1, v2 in conflicts[:10]:
            self.app.say(f"  !! layout conflict {w}: {v1!r} vs {v2!r}")

        self.restore(self.batch_var.get().strip())

    def restore(self, batch):
        saved = self.store.run(batch)
        if not saved:
            self.app.say(f"{batch or 'This plate'} - nothing remembered yet.")
            self.note.config(text="")
            return
        for group, bag in (("numbers", self.num_vars),
                           ("consumables", self.cons_vars),
                           ("solutions", self.sol_vars)):
            for key, var in bag.items():
                if saved.get(group, {}).get(key):
                    var.set(saved[group][key])
        for key, var in (("initials", self.initials_var), ("date", self.date_var),
                         ("aliquot", self.aliquot_var), ("enzyme", self.enzyme_var),
                         ("nanodrop", self.txt_var), ("out", self.out_var)):
            if saved.get(key):
                var.set(saved[key])
        done = saved.get("built", [])
        self.app.say(f"Restored {batch} (saved {saved.get('saved', '?')}).")
        if done:
            self.app.say(f"  already built: {', '.join(done)}")
        names = dict((k, n) for k, _, n in ws_sheets.WORKSHEETS)
        self.note.config(text="Already built: " + ", ".join(names[k] for k in done
                                                            if k in names)
                         if done else "")

    # --------------------------------------------------------------- state

    def gather(self):
        lay = _norm(self.lay_var.get().strip())
        out = _norm(self.out_var.get().strip())
        if not lay or not os.path.isfile(lay):
            raise ValueError("Pick the Pippeting List for the plate first.")
        if not out or not os.path.isdir(out):
            raise ValueError("Pick an existing folder to save into.")
        if self.layout is None:
            self.load(lay)
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
            # run cannot be remembered and day 1 would be lost by day 2.
            self.app.say("  !! no GA batch number - nothing was remembered for "
                         "this plate.  Type the batch number to keep it.")
            return
        prior = self.store.run(batch).get("built", [])
        self.store.save_run(batch, {
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
        })
        self.on_built(batch)

    def remember_consumables(self):
        who = self.initials_var.get().strip().upper()
        for key, var in self.cons_vars.items():
            self.store.remember(key, var.get().strip(), who)
            self.cons_boxes[key].configure(values=self.store.options(key))
        if not self.skip_solutions.get():
            for name, var in self.sol_vars.items():
                self.store.remember_solution(name, var.get().strip())

    # -------------------------------------------------------------- builds

    def _produce(self, keys, spec, avg):
        """Fill the worksheets, or make the separate sheet to attach."""
        if self.attach_var.get():
            pdf = os.path.join(spec["out"],
                               f"{spec['batch'] or 'plate'} list of samples.pdf")
            ws_sheets.build_worksheet_pack(
                self.layout, pdf, batch=spec["batch"],
                source_name=os.path.basename(spec["lay"]),
                sheet_name=self.sheet_used, numbers=spec["numbers"],
                avg_conc=avg, aliquot_ul=spec["aliquot"], pages=keys,
                initials=spec["initials"], log=self.app.say)
            return [pdf]

        sources = ws_fill.discover(_norm(self.blank_var.get().strip()) or None)
        names = dict((k, n) for k, _, n in ws_sheets.WORKSHEETS)
        for k in keys:
            if k not in sources:
                self.app.say(f"  !! no blank worksheet found for {names[k]}")
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
            written = self._produce(["isolation"], spec, None)
            if written:
                self.built["isolation"] = written[0]
            self.remember_consumables()
            self.save_state(["isolation"])
            self.app.say("")
            self.app.say(f"Saved into {spec['out']}")
            self.note.config(text=f"Built {os.path.basename(written[0])}"
                             if written else "")

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
            build(txt, spec["lay"], wb, strict=self.strict_var.get(),
                  log=self.app.say)
            self.app.say("")
            avg = mean_concentrations(txt, self.layout)
            self.app.say(f"Avg dried IgG     : DBS {avg[0] * spec['aliquot']:.1f} ug"
                         + (f" / standards {avg[1] * spec['aliquot']:.1f} ug"
                            if avg[1] is not None else ""))
            self.app.say("")
            written = self._produce(["deglyco", "cleanup"], spec, avg)
            for key, path in zip(["deglyco", "cleanup"], written):
                self.built[key] = path
            self.remember_consumables()
            self.save_state(["deglyco", "cleanup"])
            self.app.say("")
            self.app.say(f"Saved {len(written) + 1} files into {spec['out']}")
            self.note.config(text="Built the workbook, deglycosylation and "
                                  "clean-up worksheets.")

        self.app.go(self.day2_btn, spec["out"], False, work)

    # ---------------------------------------------------------------- open

    def _path_for(self, key):
        if self.built.get(key) and os.path.isfile(self.built[key]):
            return self.built[key]
        out = _norm(self.out_var.get().strip())
        batch = self.batch_var.get().strip()
        name = dict((k, n) for k, _, n in ws_sheets.WORKSHEETS)[key]
        guess = os.path.join(out, f"{batch + ' ' if batch else ''}{name} worksheet.pdf")
        return guess if os.path.isfile(guess) else None

    def open_built(self, key):
        p = self._path_for(key)
        if not p:
            messagebox.showinfo("Not built yet",
                                "That worksheet is not in the save folder yet.")
            return
        try:
            os.startfile(p)
        except Exception as e:
            messagebox.showerror("Could not open it", str(e))

    def print_built(self, key):
        p = self._path_for(key)
        if not p:
            messagebox.showinfo("Not built yet",
                                "That worksheet is not in the save folder yet.")
            return
        try:
            os.startfile(p, "print")
        except Exception:
            try:
                os.startfile(p)
                self.app.say("  (no print handler registered - opened it instead)")
            except Exception as e:
                messagebox.showerror("Could not print it", str(e))

    def open_folder(self):
        out = _norm(self.out_var.get().strip())
        if out and os.path.isdir(out):
            os.startfile(out)


class MainView(ttk.Frame):
    """Plate list beside the run - the whole window."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.store = store_mod.Store(log=app.say)
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True)

        self.panel = PlateRunPanel(pane, app, self.store, on_built=self.refresh_list)
        self.plates = PlateList(pane, self.open_plate, self.store)
        pane.add(self.plates, weight=0)
        pane.add(self.panel, weight=1)

    def open_plate(self, row):
        self.panel.load(row.get("layout"), row.get("batch"))

    def refresh_list(self, batch=None):
        self.plates.refresh(select=batch)
