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
import re
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import ws_sheets
import ws_fill
import store as store_mod
import layout_colours

DONE, PART, NEW = "✓", "◐", "·"

# A restrained palette: one accent for the things you press, grey for the
# things that only explain, and the traffic colours kept for stock and
# progress so they still mean something when they appear.
INK        = "#1b1f24"
MUTED      = "#5b6672"
ACCENT     = "#1f4e79"
OK_GREEN   = "#1a7f37"
WARN_AMBER = "#9a6700"
BAD_RED    = "#b00000"
HAIRLINE   = "#d7dce2"


def apply_theme(root):
    """Make it look like a program written this decade.

    ttk's Windows themes are the ones Explorer shipped with in about 2009 -
    grey boxes, hairline borders, 8pt Tahoma.  sv_ttk is the Sun Valley
    theme: the same ttk widgets restyled to match Windows 11, in 0.1 MB of
    Tcl.  It is bundled with the exe.  If it is ever missing the old vista
    theme still works, so nothing breaks - it just looks like it used to.
    """
    try:
        import tkinter.font as tkfont
        for name, size, weight in (("TkDefaultFont", 10, "normal"),
                                   ("TkTextFont", 10, "normal"),
                                   ("TkMenuFont", 10, "normal"),
                                   ("TkHeadingFont", 10, "bold")):
            tkfont.nametofont(name).configure(family="Segoe UI", size=size,
                                              weight=weight)
        tkfont.nametofont("TkFixedFont").configure(family="Consolas", size=10)
    except Exception:
        pass

    modern = False
    try:
        import sv_ttk
        sv_ttk.set_theme("light")
        modern = True
    except Exception:
        style = ttk.Style(root)
        for theme in ("vista", "winnative", "clam"):
            try:
                style.theme_use(theme)
                break
            except tk.TclError:
                continue

    style = ttk.Style(root)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Head.TLabel", foreground=INK,
                    font=("Segoe UI Semibold", 15))
    style.configure("Sub.TLabel", foreground=MUTED, font=("Segoe UI", 10))
    style.configure("Good.TLabel", foreground=OK_GREEN)
    style.configure("Warn.TLabel", foreground=WARN_AMBER)
    style.configure("Bad.TLabel", foreground=BAD_RED)
    style.configure("Section.TLabel", foreground=ACCENT,
                    font=("Segoe UI Semibold", 11))
    style.configure("Treeview", rowheight=26)
    if not modern:
        style.configure("TLabelframe", borderwidth=1, relief="solid",
                        bordercolor=HAIRLINE, padding=10)
        style.configure("TLabelframe.Label", foreground=ACCENT,
                        font=("Segoe UI Semibold", 10))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10),
                        padding=(12, 5))
    root.configure(background=style.lookup("TFrame", "background") or "#f3f3f3")
    return style


def _norm(path):
    return os.path.normpath(path) if path else path


def next_number(value, step=1):
    """'GA3084' -> 'GA3085'.  Keeps the prefix and the digit width.

    Worksheet and storage numbers are taken in a run, so only the first one
    is worth typing.  Returns '' if there is no trailing number to step.
    """
    m = re.search(r"^(.*?)(\d+)\s*$", value or "")
    if not m:
        return ""
    head, digits = m.group(1), m.group(2)
    return f"{head}{str(int(digits) + step).zfill(len(digits))}"


def fill_series(first, vars_in_order, overwrite=False):
    """Put first, first+1, first+2 ... into `vars_in_order`. -> how many set."""
    value = (first or "").strip()
    if not value:
        return 0
    n = 0
    for i, var in enumerate(vars_in_order):
        want = value if i == 0 else next_number(value, i)
        if not want:
            break
        if overwrite or not var.get().strip():
            var.set(want)
            n += 1
    return n


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


def _ask_float(parent, prompt, unit, current=0):
    """A small number prompt. -> float, or None if cancelled."""
    win = tk.Toplevel(parent)
    win.title("Amount")
    win.transient(parent.winfo_toplevel())
    win.resizable(False, False)
    frame = ttk.Frame(win, padding=14)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=prompt, wraplength=340, justify="left").grid(
        row=0, column=0, columnspan=2, sticky="w")
    var = tk.StringVar(value=(f"{float(current):g}" if current else ""))
    entry = ttk.Entry(frame, textvariable=var, width=12)
    entry.grid(row=1, column=0, sticky="w", pady=(10, 0))
    ttk.Label(frame, text=unit, style="Muted.TLabel").grid(
        row=1, column=1, sticky="w", padx=(6, 0), pady=(10, 0))

    out = {}

    def ok(_=None):
        try:
            out["v"] = float(var.get().strip().replace(",", "."))
        except ValueError:
            messagebox.showerror("Not a number",
                                 "Type a number, for example 60 or 7.5.",
                                 parent=win)
            return
        win.destroy()

    btns = ttk.Frame(frame)
    btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(14, 0))
    ttk.Button(btns, text="Cancel", command=win.destroy).grid(row=0, column=0)
    ttk.Button(btns, text="OK", command=ok).grid(row=0, column=1, padx=(6, 0))
    entry.bind("<Return>", ok)
    entry.focus_set()
    win.grab_set()
    parent.winfo_toplevel().wait_window(win)
    return out.get("v")


class SolutionBatchDialog(tk.Toplevel):
    """Record a solution somebody made, for the whole lab to draw on."""

    def __init__(self, parent, solution, store, who, on_done=None):
        super().__init__(parent)
        self.store, self.solution = store, solution
        self.on_done = on_done or (lambda: None)
        label = store_mod.SOLUTION_LABELS.get(solution, solution)
        self.title(f"New batch - {label}")
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)

        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=f"A batch of {label} you have made.\n"
                          "Everyone in the lab draws on it from here.",
                  justify="left").grid(row=0, column=0, columnspan=2, sticky="w")

        self.date_var = tk.StringVar(
            value=datetime.date.today().strftime("%d.%m.%Y"))
        self.made_var = tk.StringVar()
        self.by_var = tk.StringVar(value=who)
        for i, (lbl, var, unit) in enumerate((
                ("Date of preparation", self.date_var, ""),
                ("Amount made", self.made_var, "mL"),
                ("Initials", self.by_var, ""))):
            ttk.Label(f, text=lbl).grid(row=i + 1, column=0, sticky="w",
                                        pady=(10 if i == 0 else 4, 0))
            e = ttk.Entry(f, textvariable=var, width=16)
            e.grid(row=i + 1, column=1, sticky="w", padx=(10, 0),
                   pady=(10 if i == 0 else 4, 0))
            if unit:
                ttk.Label(f, text=unit, style="Muted.TLabel").grid(
                    row=i + 1, column=2, sticky="w", padx=(4, 0))

        btns = ttk.Frame(f)
        btns.grid(row=5, column=0, columnspan=3, sticky="e", pady=(16, 0))
        ttk.Button(btns, text="Cancel", command=self.destroy).grid(row=0, column=0)
        ttk.Button(btns, text="Save", command=self.save).grid(row=0, column=1,
                                                              padx=(6, 0))
        self.grab_set()

    def save(self):
        try:
            made = float(self.made_var.get().strip().replace(",", "."))
            if made <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Amount made",
                                 "How many mL did you make?  For example 500.",
                                 parent=self)
            return
        if not self.date_var.get().strip():
            messagebox.showerror("Date", "Put the date of preparation in.",
                                 parent=self)
            return
        self.store.add_solution_batch(self.solution, self.date_var.get().strip(),
                                      made, self.by_var.get().strip().upper())
        self.destroy()
        self.on_done()


class PlateList(ttk.Frame):
    """Every plate seen so far, newest first, with how far each one got."""

    def __init__(self, parent, on_pick, store):
        super().__init__(parent, padding=(14, 14, 8, 14))
        self.on_pick = on_pick
        self.store = store
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="Plates", style="Head.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6))

        self.tree = ttk.Treeview(self, columns=("state",), show="tree headings",
                                 selectmode="browse", height=18)
        self.tree.heading("#0", text="GA batch")
        self.tree.heading("state", text="•")
        self.tree.column("#0", width=170, stretch=True)
        self.tree.column("state", width=40, stretch=False, anchor="center")
        self.tree.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._picked)

        self.tree.tag_configure("done", foreground=OK_GREEN)
        self.tree.tag_configure("part", foreground=WARN_AMBER)

        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="New plate...", command=self.new_plate).grid(
            row=0, column=0, sticky="w")
        ttk.Button(btns, text="Remove", command=self.forget).grid(
            row=0, column=1, sticky="w", padx=(6, 0))

        self.key = ttk.Label(
            self, style="Muted.TLabel", justify="left",
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

        header = ttk.Frame(self, padding=(14, 12, 14, 8))
        header.pack(fill="x")
        header.columnconfigure(0, weight=1)
        self.title_lbl = ttk.Label(header, text="No plate open",
                                   style="Head.TLabel")
        self.title_lbl.grid(row=0, column=0, sticky="w")
        self.sub_lbl = ttk.Label(header, text="Open a Pippeting List to start, "
                                             "or pick a plate on the left.",
                                 style="Sub.TLabel")
        self.sub_lbl.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.stage_lbl = ttk.Label(header, text="", style="Sub.TLabel")
        self.stage_lbl.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Separator(self, orient="horizontal").pack(fill="x")

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
                  style="Muted.TLabel").grid(row=r, column=0, sticky="w",
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
                          "the NanoDrop is done.", style="Muted.TLabel").grid(
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
                                    style="Muted.TLabel")
        self.plate_info.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))
        return r + 1

    def _sec_numbers(self, body, r):
        s = Section(body, 2, "Worksheet and storage numbers taken for this plate")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))

        # Each group is its own frame, so the Fill button can sit beside the
        # first entry without landing in the next group's column.
        def group(col, heading, rows):
            f = ttk.Frame(s)
            f.grid(row=0, column=col, sticky="nw", padx=(0, 36))
            ttk.Label(f, text=heading, style="Muted.TLabel").grid(
                row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))
            order = []
            for i, (key, label) in enumerate(rows):
                ttk.Label(f, text=label).grid(row=i + 1, column=0, sticky="w",
                                              pady=2)
                v = tk.StringVar()
                self.num_vars[key] = v
                order.append(v)
                ttk.Entry(f, textvariable=v, width=14).grid(
                    row=i + 1, column=1, sticky="w", padx=(10, 6))
            ttk.Button(f, text="Fill ↓", width=7,
                       command=lambda o=order: self.fill_down(o)).grid(
                row=1, column=2, sticky="w")
            return order

        self.ws_order = group(0, "Working worksheets",
                              [(k, n) for k, _, n in ws_sheets.WORKSHEETS])
        self.store_order = group(1, "Storage (GBL-WS-002)",
                                 list(ws_sheets.STORAGE))

        ttk.Label(s, text="Type the first number and press Fill ↓ - they are "
                          "taken in a run, so the rest follow (GA3084, GA3085, "
                          "GA3086).", style="Muted.TLabel").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        extra = ttk.Frame(s)
        extra.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
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
            if key == "proteing_no":
                # the use count belongs to the plate, so it follows the number
                v.trace_add("write", lambda *_: self.show_proteing_uses())
                self.uses_lbl = ttk.Label(s, text="", style="Muted.TLabel")
                self.uses_lbl.grid(row=i, column=2, sticky="w", padx=(4, 0))

        ttk.Label(s, text="PNGase F vial", style="Muted.TLabel").grid(
            row=n, column=0, sticky="w", pady=(8, 0))
        vial = ttk.Frame(s)
        vial.grid(row=n, column=1, sticky="w", padx=(10, 0), pady=(8, 0))
        ttk.Radiobutton(vial, text="30 µg", value="30",
                        variable=self.enzyme_var).grid(row=0, column=0, padx=(0, 14))
        ttk.Radiobutton(vial, text="50 µg", value="50",
                        variable=self.enzyme_var).grid(row=0, column=1)
        ttk.Label(vial, text="- decides which 'Enzyme LOT' line is filled",
                  style="Muted.TLabel").grid(row=0, column=2, padx=(14, 0))

        ttk.Label(s, text="Check the offered LOT against the label on the bench "
                          "before printing.  Anything left empty prints empty.",
                  style="Muted.TLabel").grid(row=n + 1, column=0, columnspan=3,
                                             sticky="w", pady=(8, 0))
        self.show_proteing_uses()
        return r + 1

    def show_proteing_uses(self):
        """The Protein G use count, counted rather than typed."""
        if not hasattr(self, "uses_lbl"):
            return
        no = self.cons_vars["proteing_no"].get().strip()
        if not no:
            self.uses_lbl.config(text="")
            return
        used = self.store.proteing_uses(no)
        batch = self.batch_var.get().strip()
        already = batch and batch in (
            self.store._read(store_mod.CONSUMABLES_FILE)
            .get("_proteing", {}).get(no, {}).get("batches", []))
        nxt = used if already else used + 1
        self.uses_lbl.config(
            text=f"used on {used} plate(s) so far  →  this plate is no. {nxt}")

    def _sec_solutions(self, body, r):
        s = Section(body, 4, "Solution library  -  shared by the whole lab")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))
        s.columnconfigure(0, weight=1)

        ttk.Label(s, text="Whoever makes a solution records the batch here and "
                          "everyone sees it.  Set how much one plate needs and "
                          "the program works out how many plates are left.").grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(s, text="Skip the dates on the worksheets and fill those "
                               "tables in by hand after printing",
                        variable=self.skip_solutions).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(6, 6))

        cols = ("need", "stock", "left", "prepared", "by")
        self.sol_tree = ttk.Treeview(s, columns=cols, show="tree headings",
                                     selectmode="browse", height=16)
        self.sol_tree.heading("#0", text="Solution")
        for c, t, w in (("need", "Needs / plate", 118), ("stock", "In stock", 92),
                        ("left", "Plates left", 80),
                        ("prepared", "Batch prepared", 110), ("by", "By", 50)):
            self.sol_tree.heading(c, text=t)
            self.sol_tree.column(c, width=w, stretch=False, anchor="center")
        self.sol_tree.column("#0", width=210, stretch=True)
        self.sol_tree.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.sol_tree.tag_configure("short", foreground=BAD_RED)
        self.sol_tree.tag_configure("low", foreground=WARN_AMBER)
        self.sol_tree.tag_configure("head", foreground=MUTED)

        btns = ttk.Frame(s)
        btns.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Button(btns, text="I made a batch...", command=self.add_batch).grid(
            row=0, column=0)
        ttk.Button(btns, text="Set amount per plate...",
                   command=self.set_per_plate).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(btns, text="Refresh", command=self.refresh_solutions).grid(
            row=0, column=2, padx=(6, 0))
        ttk.Button(btns, text="Where does (calc) come from?",
                   command=self.explain_calc).grid(row=0, column=3, padx=(6, 0))
        ttk.Label(btns, text="   red = not enough for one plate,  amber = last plate",
                  style="Muted.TLabel").grid(row=0, column=4, padx=(10, 0))

        # the dates that go on the worksheets come from the batch in use
        for key, _, _n in ws_sheets.WORKSHEETS:
            for sol in store_mod.SOLUTIONS[key]:
                self.sol_vars.setdefault(sol, tk.StringVar())
        self.refresh_solutions()
        return r + 1

    # ---------------------------------------------------------- solutions

    def _all_solutions(self):
        """-> [(worksheet name, [solution, ...])] in worksheet order."""
        return [(name, store_mod.SOLUTIONS[key])
                for key, _, name in ws_sheets.WORKSHEETS]

    def selected_solution(self):
        sel = self.sol_tree.selection()
        if not sel:
            return None
        return getattr(self, "_sol_rows", {}).get(sel[0])

    def refresh_solutions(self):
        """Redraw the library and pull the in-use batch dates into the form."""
        lib = self.store.solution_library()
        for i in self.sol_tree.get_children():
            self.sol_tree.delete(i)
        self._sol_rows = {}

        for ws_name, sols in self._all_solutions():
            head = self.sol_tree.insert("", "end", text=ws_name, values=("", "", "", "", ""),
                                        tags=("head",), open=True)
            for sol in sols:
                rec = lib.get(sol) or {}
                per, source = self.store.per_plate(sol)
                stock = self.store.stock_ml(sol)
                left = self.store.plates_left(sol)
                batch = self.store._active_batch(rec) or {}
                prepared = batch.get("prepared", "")
                self.sol_vars.setdefault(sol, tk.StringVar()).set(prepared)

                known = self.store.has_batches(sol)
                tag = ""
                if not known:
                    tag = "head"              # nobody has recorded one yet
                elif per > 0:
                    if stock < per:
                        tag = "short"
                    elif left is not None and left <= 1:
                        tag = "low"
                iid = self.sol_tree.insert(
                    head, "end", text="   " + store_mod.SOLUTION_LABELS.get(sol, sol),
                    values=(f"{per:g} mL" + (" (calc)" if source == "calculated"
                                             else "") if per else "-",
                            f"{stock:g} mL" if known else "not recorded",
                            "-" if (left is None or not known) else str(left),
                            prepared or "-", batch.get("by", "") or "-"),
                    tags=(tag,) if tag else ())
                self._sol_rows[iid] = sol

    def add_batch(self):
        sol = self.selected_solution()
        if not sol:
            messagebox.showinfo("Pick a solution",
                                "Select the solution you made, then press "
                                "'I made a batch...'.")
            return
        SolutionBatchDialog(self, sol, self.store,
                            self.initials_var.get().strip().upper(),
                            on_done=self.refresh_solutions)

    def explain_calc(self):
        """Show how each calculated requirement was arrived at."""
        self.app.clear()
        self.app.say("Amount per plate, worked out from the worksheet steps")
        self.app.say(f"for a {store_mod.PLATE_WELLS}-well plate, "
                     f"plus {int(store_mod.OVERAGE * 100)}% for dead volume "
                     f"and priming:")
        self.app.say("")
        for ws_name, sols in self._all_solutions():
            self.app.say(f"  {ws_name}")
            for sol in sols:
                per, source = self.store.per_plate(sol)
                label = store_mod.SOLUTION_LABELS.get(sol, sol)
                if source == "set":
                    self.app.say(f"    {label:<24} {per:g} mL   (set by hand)")
                elif source == "calculated":
                    self.app.say(f"    {label:<24} {store_mod.recipe_note(sol)}")
                else:
                    self.app.say(f"    {label:<24} not known")
            self.app.say("")
        self.app.say("Set amount per plate... overrides any of these.")

    def set_per_plate(self):
        sol = self.selected_solution()
        if not sol:
            messagebox.showinfo("Pick a solution",
                                "Select a solution, then press 'Set amount per "
                                "plate...'.")
            return
        cur, source = self.store.per_plate(sol)
        note = store_mod.recipe_note(sol)
        prompt = (f"How much {store_mod.SOLUTION_LABELS.get(sol, sol)} "
                  f"does one plate need?")
        if note and source == "calculated":
            prompt += "\n\nFrom the worksheet: " + note
        ml = _ask_float(self, prompt, "mL per plate", cur)
        if ml is not None:
            self.store.set_per_plate(sol, ml)
            self.refresh_solutions()

    def _sec_build(self, body, r):
        s = Section(body, 5, "Build  -  any of these, in any order, as often as you like")
        s.grid(row=r, column=0, sticky="ew", pady=(0, 10))

        day1 = ttk.Frame(s)
        day1.grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(day1, text="Day 1", width=8, style="Muted.TLabel").grid(
            row=0, column=0, sticky="w")
        self.iso_btn = ttk.Button(day1, text="IgG isolation worksheet",
                                  style="Accent.TButton",
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
        ttk.Label(day2, text="Day 2", width=8, style="Muted.TLabel").grid(
            row=0, column=0, sticky="w")
        self.day2_btn = ttk.Button(day2, text="Workbook + deglyco + clean up",
                                   style="Accent.TButton",
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

        self.note = ttk.Label(s, text="", style="Muted.TLabel")
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
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=2,
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

        self.title_lbl.config(text=self.batch_var.get().strip() or
                              os.path.basename(path))
        self.sub_lbl.config(text=os.path.basename(path))
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
            self.stage_lbl.config(text="nothing built yet", style="Sub.TLabel")
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
        self.stage_lbl.config(
            text=("all three worksheets built" if len(done) >= 3
                  else f"{len(done)} of 3 worksheets built" if done
                  else "nothing built yet"),
            style=("Good.TLabel" if len(done) >= 3
                   else "Warn.TLabel" if done else "Sub.TLabel"))

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

        # 'How many times has this Protein G plate been used?' is counted from
        # the plates the lab has run, not typed.  This plate is the next one
        # unless it has already been counted (a rebuild).
        batch = self.batch_var.get().strip()
        pg = cons.get("proteing_no", "")
        if pg:
            seen = (self.store._read(store_mod.CONSUMABLES_FILE)
                    .get("_proteing", {}).get(pg, {}).get("batches", []))
            used = len(seen)
            cons["proteing_uses"] = str(used if (batch and batch in seen)
                                        else used + 1)
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

    def fill_down(self, order):
        """First number typed -> the rest of the run."""
        first = order[0].get().strip()
        if not first:
            messagebox.showinfo("Type the first one",
                                "Put the first number in and press Fill ↓ - "
                                "the rest follow it in order.")
            return
        if not next_number(first):
            messagebox.showwarning(
                "Cannot continue that",
                f"{first!r} does not end in a number, so there is nothing to "
                "count on from.  Fill the rest in by hand.")
            return
        blanks = [v for v in order[1:] if not v.get().strip()]
        if not blanks and not messagebox.askyesno(
                "Overwrite?", "The rest already have numbers.  Replace them?"):
            return
        fill_series(first, order, overwrite=not blanks)

    def solutions_for(self, keys):
        """Every solution the given worksheets draw on."""
        out = []
        for k in keys:
            for sol in store_mod.SOLUTIONS.get(k, []):
                if sol not in out:
                    out.append(sol)
        return out

    def warn_shortages(self, keys):
        """-> True to carry on.  Names the solutions that will not stretch."""
        short = self.store.shortages(self.solutions_for(keys))
        if not short:
            return True
        lines = "\n".join(
            f"  - {store_mod.SOLUTION_LABELS.get(n, n)}: "
            f"{have:g} mL left, this plate needs {per:g} mL"
            for n, have, per in short)
        self.app.say("")
        for n, have, per in short:
            self.app.say(f"  !! {store_mod.SOLUTION_LABELS.get(n, n)} - "
                         f"{have:g} mL left, needs {per:g} mL for this plate")
        return messagebox.askyesno(
            "Solutions need making",
            "There is not enough of:\n\n" + lines
            + "\n\nRecord a new batch in the solution library, or carry on "
              "anyway if the stock figure is out of date.\n\nCarry on?")

    def remember_consumables(self, keys=(), count_proteing=False):
        who = self.initials_var.get().strip().upper()
        batch = self.batch_var.get().strip()
        for key, var in self.cons_vars.items():
            self.store.remember(key, var.get().strip(), who)
            self.cons_boxes[key].configure(values=self.store.options(key))

        if count_proteing:
            no = self.cons_vars["proteing_no"].get().strip()
            if no and batch:
                n = self.store.record_proteing_use(no, batch, who)
                self.app.say(f"Protein G plate {no}: now used on {n} plate(s).")
                self.show_proteing_uses()

        if keys and not self.skip_solutions.get():
            for name, left in self.store.consume(self.solutions_for(keys),
                                                 batch, who):
                per, _src = self.store.per_plate(name)
                if per:
                    self.app.say(f"  {store_mod.SOLUTION_LABELS.get(name, name)}: "
                                 f"{left:g} mL left")
            self.refresh_solutions()

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
        if not self.warn_shortages(["isolation"]):
            return

        def work():
            written = self._produce(["isolation"], spec, None)
            if written:
                self.built["isolation"] = written[0]
            self.remember_consumables(["isolation"], count_proteing=True)
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
        if not self.warn_shortages(["deglyco", "cleanup"]):
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
            self.remember_consumables(["deglyco", "cleanup"])
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
