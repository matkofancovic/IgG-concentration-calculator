#!/usr/bin/env python3
"""
The window.

One plate at a time: the Pippeting List goes in once, the NanoDrop export
goes in once, and every output comes from those two files.

Laid out the way the lab's own site is - deep green, one orange accent, a
soft off-white ground and plenty of air:

    left    a green rail carrying the plates seen so far
    top     which plate is open and how far it got
    middle  ONE step at a time, not one long scroll
    bottom  the report

The step rail matters more than it looks.  Everything used to be stacked in
six sections down a scrolling page, so finding the button you wanted meant
hunting.  Four steps, one visible at a time, and the thing you need is
always on screen.

Nothing is ever locked.  Every output can be rebuilt at any point, in any
order; the steps are the normal path, not a cage.
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

# ---------------------------------------------------------------------------
#  The GlycanAge palette, taken from glycanage.hr so the tool looks like part
#  of the same thing rather than a lab script someone bolted on.
# ---------------------------------------------------------------------------
GREEN      = "#09341F"      # headings, the side rail
GREEN_MID  = "#5E9479"
GREEN_SOFT = "#A3C2B2"
TINT       = "#E1EBE6"      # panel washes
ORANGE     = "#E66439"      # the one accent - only on things you press
ORANGE_DK  = "#C9552F"
GROUND     = "#F1F5F3"      # page
CARD       = "#FFFFFF"
LINE       = "#DCE5E0"
MUTED      = "#6B7F75"
OK_GREEN   = "#1a7f37"
WARN_AMBER = "#9a6700"
BAD_RED    = "#b00000"

DONE, PART, NEW = "✓", "◐", "·"
FONT = "Segoe UI"


def apply_theme(root):
    """Dress the ttk widgets in the GlycanAge colours."""
    try:
        import tkinter.font as tkfont
        for name, size, weight in (("TkDefaultFont", 10, "normal"),
                                   ("TkTextFont", 10, "normal"),
                                   ("TkMenuFont", 10, "normal"),
                                   ("TkHeadingFont", 10, "bold")):
            tkfont.nametofont(name).configure(family=FONT, size=size,
                                              weight=weight)
        tkfont.nametofont("TkFixedFont").configure(family="Consolas", size=10)
    except Exception:
        pass

    try:
        import sv_ttk
        sv_ttk.set_theme("light")
    except Exception:
        for theme in ("vista", "winnative", "clam"):
            try:
                ttk.Style(root).theme_use(theme)
                break
            except tk.TclError:
                continue

    st = ttk.Style(root)
    st.configure("TFrame", background=GROUND)
    st.configure("TLabel", background=GROUND, foreground=GREEN)
    st.configure("TCheckbutton", background=CARD, foreground=GREEN)
    st.configure("TRadiobutton", background=CARD, foreground=GREEN)

    st.configure("Card.TFrame", background=CARD)
    st.configure("Card.TLabel", background=CARD, foreground=GREEN)
    st.configure("CardMuted.TLabel", background=CARD, foreground=MUTED)
    st.configure("Tint.TFrame", background=TINT)
    st.configure("Tint.TLabel", background=TINT, foreground=GREEN)

    st.configure("H1.TLabel", background=GROUND, foreground=GREEN,
                 font=(FONT, 19, "bold"))
    st.configure("H2.TLabel", background=CARD, foreground=GREEN,
                 font=(FONT, 13, "bold"))
    st.configure("Sub.TLabel", background=GROUND, foreground=MUTED,
                 font=(FONT, 10))
    st.configure("Muted.TLabel", background=GROUND, foreground=MUTED)
    st.configure("Good.TLabel", background=GROUND, foreground=OK_GREEN)
    st.configure("Warn.TLabel", background=GROUND, foreground=WARN_AMBER)
    st.configure("Bad.TLabel", background=GROUND, foreground=BAD_RED)

    # the one accent, used only for the thing you are meant to press next
    st.configure("Accent.TButton", font=(FONT, 10, "bold"))
    st.map("Accent.TButton",
           background=[("pressed", ORANGE_DK), ("active", ORANGE_DK),
                       ("!disabled", ORANGE)],
           foreground=[("!disabled", "#FFFFFF")])
    st.configure("TButton", font=(FONT, 10))

    st.configure("Treeview", background=CARD, fieldbackground=CARD,
                 foreground=GREEN, rowheight=27, borderwidth=0)
    st.configure("Treeview.Heading", font=(FONT, 10, "bold"),
                 background=TINT, foreground=GREEN)
    st.map("Treeview", background=[("selected", GREEN_SOFT)],
           foreground=[("selected", GREEN)])

    root.configure(background=GROUND)
    return st


def _norm(path):
    return os.path.normpath(path) if path else path


# Everything the program writes goes here.  Deliberately on the Desktop and
# never onto the Glikobiologija share: the rest of that share is private
# participant data and this program has no business writing into it.
DESKTOP_ROOT = os.path.join(
    os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")),
                 "Desktop"),
    "GlycanAge plate runs")


def output_folder(batch):
    """-> the Desktop folder for this plate, made if it is not there yet."""
    folder = os.path.join(DESKTOP_ROOT, batch.strip() or "unnamed plate")
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        return DESKTOP_ROOT
    return folder


def next_number(value, step=1):
    """'GA3084' -> 'GA3085'.  Keeps the prefix and the digit width."""
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


# ---------------------------------------------------------------------- bits

class Card(ttk.Frame):
    """A white panel on the soft ground, with a title."""

    def __init__(self, parent, title, subtitle=""):
        super().__init__(parent, style="Card.TFrame", padding=(20, 16, 20, 18))
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text=title, style="H2.TLabel").grid(
            row=0, column=0, sticky="w")
        if subtitle:
            ttk.Label(self, text=subtitle, style="CardMuted.TLabel",
                      wraplength=760, justify="left").grid(
                row=1, column=0, sticky="w", pady=(3, 0))
        self.body = ttk.Frame(self, style="Card.TFrame")
        self.body.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self.body.columnconfigure(1, weight=1)


def field(parent, row, label, var, width=16, col=0, unit=""):
    """A labelled entry inside a card."""
    ttk.Label(parent, text=label, style="Card.TLabel").grid(
        row=row, column=col, sticky="w", pady=4, padx=(0, 10))
    e = ttk.Entry(parent, textvariable=var, width=width)
    e.grid(row=row, column=col + 1, sticky="w", pady=4)
    if unit:
        ttk.Label(parent, text=unit, style="CardMuted.TLabel").grid(
            row=row, column=col + 2, sticky="w", padx=(6, 18))
    return e


class AccentButton(tk.Button):
    """The orange button.

    ttk under sv_ttk draws its buttons from bitmaps, so a style map cannot
    recolour them - Accent.TButton comes out the theme's blue whatever you
    ask for.  A plain tk.Button takes the colour, and carries a .state()
    so the rest of the code can disable it like any ttk widget.
    """

    def __init__(self, parent, text, command, **kw):
        super().__init__(parent, text=f"  {text}  ", command=command, bd=0,
                         relief="flat", cursor="hand2",
                         font=(FONT, 10, "bold"), background=ORANGE,
                         foreground="#FFFFFF", activebackground=ORANGE_DK,
                         activeforeground="#FFFFFF", disabledforeground="#EEDCD4",
                         highlightthickness=0, padx=6, pady=6, **kw)

    def state(self, spec=None):
        if not spec:
            return ()
        if "disabled" in spec:
            self.configure(state="disabled", background=GREEN_SOFT)
        if "!disabled" in spec:
            self.configure(state="normal", background=ORANGE)
        return ()


class CalendarPopup(tk.Toplevel):
    """A month grid that opens on whatever date is already in the box.

    Written here rather than pulled in: tkcalendar drags in babel, and this
    way the calendar is in the same green and orange as everything else.

    Weeks start on Monday, which is how the lab writes a date.
    """

    def __init__(self, entry, var, on_pick=None):
        super().__init__(entry.winfo_toplevel())
        self.var, self.on_pick = var, on_pick or (lambda: None)
        self.overrideredirect(True)          # a popup, not a window
        self.configure(background=GREEN, padx=1, pady=1)

        # open on the date in the box, or today if it is empty or unreadable
        try:
            self.shown = datetime.datetime.strptime(var.get().strip(),
                                                    "%d.%m.%Y").date()
        except ValueError:
            self.shown = datetime.date.today()
        self.picked = self.shown

        body = tk.Frame(self, background=CARD, padx=10, pady=10)
        body.pack(fill="both", expand=True)

        head = tk.Frame(body, background=CARD)
        head.pack(fill="x")
        tk.Button(head, text="‹", command=lambda: self.step(-1), bd=0,
                  relief="flat", background=CARD, foreground=GREEN,
                  activebackground=TINT, font=(FONT, 13, "bold"),
                  cursor="hand2", width=2).pack(side="left")
        self.title_lbl = tk.Label(head, background=CARD, foreground=GREEN,
                                  font=(FONT, 11, "bold"), width=16)
        self.title_lbl.pack(side="left", expand=True)
        tk.Button(head, text="›", command=lambda: self.step(1), bd=0,
                  relief="flat", background=CARD, foreground=GREEN,
                  activebackground=TINT, font=(FONT, 13, "bold"),
                  cursor="hand2", width=2).pack(side="right")

        self.grid_frame = tk.Frame(body, background=CARD)
        self.grid_frame.pack(pady=(8, 4))

        foot = tk.Frame(body, background=CARD)
        foot.pack(fill="x", pady=(6, 0))
        tk.Button(foot, text="Today", command=self.today, bd=0, relief="flat",
                  background=TINT, foreground=GREEN, activebackground=GREEN_SOFT,
                  font=(FONT, 9), cursor="hand2", padx=10, pady=3).pack(side="left")
        tk.Button(foot, text="Cancel", command=self.close, bd=0, relief="flat",
                  background=CARD, foreground=MUTED, activebackground=TINT,
                  font=(FONT, 9), cursor="hand2", padx=10, pady=3).pack(side="right")

        self.draw()
        self.place_under(entry)
        self.grab_set()
        self.bind("<Escape>", lambda _: self.close())
        self.bind("<FocusOut>", lambda _: None)

    # -- behaviour ---------------------------------------------------------

    def step(self, months):
        y, m = self.shown.year, self.shown.month + months
        y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
        self.shown = self.shown.replace(year=y, month=m, day=1)
        self.draw()

    def today(self):
        self.choose(datetime.date.today())

    def choose(self, day):
        self.var.set(day.strftime("%d.%m.%Y"))
        self.close()
        self.on_pick()

    def close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def place_under(self, widget):
        """Below the box it belongs to, nudged back on screen if it would fall
        off the bottom or the right."""
        self.update_idletasks()
        x = widget.winfo_rootx()
        y = widget.winfo_rooty() + widget.winfo_height() + 2
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = max(0, min(x, self.winfo_screenwidth() - w - 8))
        if y + h > self.winfo_screenheight() - 40:
            y = widget.winfo_rooty() - h - 2
        self.geometry(f"+{x}+{y}")

    # -- drawing -----------------------------------------------------------

    def draw(self):
        import calendar
        for child in self.grid_frame.winfo_children():
            child.destroy()
        self.title_lbl.configure(
            text=f"{calendar.month_name[self.shown.month]} {self.shown.year}")

        for i, day in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            tk.Label(self.grid_frame, text=day, background=CARD,
                     foreground=MUTED if i < 5 else GREEN_SOFT,
                     font=(FONT, 9, "bold"), width=4).grid(row=0, column=i,
                                                           pady=(0, 4))

        today = datetime.date.today()
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(
            self.shown.year, self.shown.month)
        for r, week in enumerate(weeks, start=1):
            for c, day in enumerate(week):
                if day.month != self.shown.month:
                    tk.Label(self.grid_frame, text="", background=CARD,
                             width=4).grid(row=r, column=c)
                    continue
                selected = day == self.picked
                bg = ORANGE if selected else CARD
                fg = "#FFFFFF" if selected else (
                    GREEN if c < 5 else MUTED)          # weekends greyed
                b = tk.Button(self.grid_frame, text=str(day.day), width=4, bd=0,
                              relief="flat", cursor="hand2", background=bg,
                              foreground=fg, activebackground=GREEN_SOFT,
                              font=(FONT, 10, "bold" if selected else "normal"),
                              command=lambda d=day: self.choose(d))
                b.grid(row=r, column=c, padx=1, pady=1)
                if day == today and not selected:
                    b.configure(highlightthickness=1,
                                highlightbackground=GREEN_SOFT, foreground=GREEN)


def date_field(parent, row, label, var, col=0, on_pick=None):
    """A date box with a calendar button, opening on the date already in it."""
    ttk.Label(parent, text=label, style="Card.TLabel").grid(
        row=row, column=col, sticky="w", pady=4, padx=(0, 10))
    holder = ttk.Frame(parent, style="Card.TFrame")
    holder.grid(row=row, column=col + 1, sticky="w", pady=4)
    e = ttk.Entry(holder, textvariable=var, width=12)
    e.grid(row=0, column=0)
    tk.Button(holder, text="📅", bd=0, relief="flat", cursor="hand2",
              background=TINT, foreground=GREEN, activebackground=GREEN_SOFT,
              font=(FONT, 10), padx=6,
              command=lambda: CalendarPopup(e, var, on_pick)).grid(
        row=0, column=1, padx=(4, 0))
    e.bind("<Button-1>", lambda _: CalendarPopup(e, var, on_pick))
    return e


class StepRail(tk.Frame):
    """The four steps across the top - one panel visible at a time."""

    def __init__(self, parent, steps, on_pick):
        super().__init__(parent, background=GROUND)
        self.on_pick = on_pick
        self.buttons = {}
        for i, (key, text) in enumerate(steps):
            b = tk.Button(self, text=f"  {i + 1}   {text}  ", bd=0,
                          relief="flat", cursor="hand2",
                          font=(FONT, 10, "bold"),
                          activebackground=TINT, highlightthickness=0,
                          command=lambda k=key: self.on_pick(k))
            b.grid(row=0, column=i, sticky="w", padx=(0, 6), ipady=7)
            self.buttons[key] = b

    def show(self, key):
        for k, b in self.buttons.items():
            if k == key:
                b.configure(background=GREEN, foreground="#FFFFFF")
            else:
                b.configure(background=TINT, foreground=GREEN)


class Sidebar(tk.Frame):
    """The green rail: the wordmark, then every plate seen so far."""

    def __init__(self, parent, on_pick, store):
        super().__init__(parent, background=GREEN, width=250)
        self.grid_propagate(False)
        self.on_pick, self.store = on_pick, store
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        tk.Label(self, text="GlycanAge", background=GREEN, foreground="#FFFFFF",
                 font=(FONT, 17, "bold")).grid(row=0, column=0, sticky="w",
                                               padx=20, pady=(20, 0))
        tk.Label(self, text="plate run", background=GREEN, foreground=GREEN_SOFT,
                 font=(FONT, 11)).grid(row=1, column=0, sticky="w", padx=20,
                                       pady=(0, 16))

        wrap = tk.Frame(self, background=GREEN)
        wrap.grid(row=2, column=0, sticky="nsew", padx=14)
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        self.list = tk.Listbox(wrap, background=GREEN, foreground="#FFFFFF",
                               selectbackground=GREEN_MID,
                               selectforeground="#FFFFFF", borderwidth=0,
                               highlightthickness=0, activestyle="none",
                               font=(FONT, 10))
        self.list.grid(row=0, column=0, sticky="nsew")
        self.list.bind("<<ListboxSelect>>", self._picked)

        btns = tk.Frame(self, background=GREEN)
        btns.grid(row=3, column=0, sticky="ew", padx=14, pady=(12, 6))
        for i, (text, cmd) in enumerate((("New plate", self.new_plate),
                                         ("Remove", self.forget))):
            tk.Button(btns, text=text, command=cmd, bd=0, relief="flat",
                      cursor="hand2", font=(FONT, 10),
                      background=ORANGE if i == 0 else GREEN_MID,
                      foreground="#FFFFFF", activebackground=ORANGE_DK,
                      highlightthickness=0).grid(row=0, column=i, sticky="ew",
                                                 padx=(0, 6), ipadx=10, ipady=5)

        self.note = tk.Label(self, background=GREEN, foreground=GREEN_SOFT,
                             font=(FONT, 9), justify="left",
                             text=f"{DONE} all three built\n"
                                  f"{PART} part way\n"
                                  f"{NEW} not started")
        self.note.grid(row=4, column=0, sticky="w", padx=20, pady=(0, 16))
        self.refresh()

    def refresh(self, select=None):
        self.list.delete(0, "end")
        self._rows = []
        for row in self.store.plates():
            mark = DONE if row["done"] else (PART if row["built"] else NEW)
            self.list.insert("end", f" {mark}  {row['batch']}")
            self._rows.append(row)
        for i, row in enumerate(self._rows):
            self.list.itemconfigure(
                i, foreground="#FFFFFF" if row["done"] else GREEN_SOFT)
            if select and row["batch"] == select:
                self.list.selection_clear(0, "end")
                self.list.selection_set(i)
                self.list.see(i)

    def _picked(self, _=None):
        sel = self.list.curselection()
        if sel and sel[0] < len(self._rows):
            self.on_pick(self._rows[sel[0]])

    def selected_batch(self):
        sel = self.list.curselection()
        return self._rows[sel[0]]["batch"] if sel and sel[0] < len(self._rows) else None

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


class SolutionDialog(tk.Toplevel):
    """Record a preparation of one solution."""

    def __init__(self, parent, solution, store, on_done=None):
        super().__init__(parent, background=GROUND)
        self.store, self.solution = store, solution
        self.on_done = on_done or (lambda: None)
        label = store_mod.SOLUTION_LABELS.get(solution, solution)
        self.title(f"New preparation - {label}")
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)

        f = ttk.Frame(self, style="Card.TFrame", padding=18)
        f.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(f, text=label, style="H2.TLabel").grid(row=0, column=0,
                                                         columnspan=2, sticky="w")
        ttk.Label(f, text="The date on the bottle.  Everyone will be offered it.",
                  style="CardMuted.TLabel").grid(row=1, column=0, columnspan=2,
                                                 sticky="w", pady=(2, 12))
        self.date_var = tk.StringVar(
            value=datetime.date.today().strftime("%d.%m.%Y"))
        ttk.Label(f, text="Date of preparation", style="Card.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 10))
        e = ttk.Entry(f, textvariable=self.date_var, width=16)
        e.grid(row=2, column=1, sticky="w")
        e.focus_set()

        b = ttk.Frame(f, style="Card.TFrame")
        b.grid(row=3, column=0, columnspan=2, sticky="e", pady=(18, 0))
        ttk.Button(b, text="Cancel", command=self.destroy).grid(row=0, column=0)
        AccentButton(b, "Save", self.save).grid(row=0, column=1, padx=(8, 0))
        e.bind("<Return>", lambda _: self.save())
        self.grab_set()

    def save(self):
        if not self.date_var.get().strip():
            messagebox.showerror("Date", "Put the date of preparation in.",
                                 parent=self)
            return
        self.store.remember_solution(self.solution, self.date_var.get().strip())
        self.destroy()
        self.on_done()


# --------------------------------------------------------------------- panel

class PlateRunPanel(tk.Frame):
    """The run: header, step rail, and one step panel at a time."""

    STEPS = [("plate", "Plate"), ("numbers", "Numbers"),
             ("materials", "Materials"), ("build", "Build")]

    def __init__(self, parent, app, store, on_built=None):
        super().__init__(parent, background=GROUND,
                         padx=24, pady=14)
        self.app, self.store = app, store
        self.on_built = on_built or (lambda *_: None)
        self.layout, self.colours, self.sheet_used, self.built = None, {}, "", {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        head = tk.Frame(self, background=GROUND)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        self.title_lbl = ttk.Label(head, text="No plate open", style="H1.TLabel")
        self.title_lbl.grid(row=0, column=0, sticky="w")
        self.stage_lbl = ttk.Label(head, text="", style="Sub.TLabel")
        self.stage_lbl.grid(row=0, column=1, sticky="e")
        self.sub_lbl = ttk.Label(head, style="Sub.TLabel",
                                 text="Open a Pippeting List, or pick a plate "
                                      "on the left.")
        self.sub_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

        self.rail = StepRail(self, self.STEPS, self.show_step)
        self.rail.grid(row=1, column=0, sticky="w", pady=(16, 0))
        ttk.Separator(self, orient="horizontal").grid(row=2, column=0,
                                                      sticky="ew", pady=(10, 14))

        # The step area scrolls.  The solutions step is taller than a laptop
        # screen and was being cut off half way down the list.
        outer = tk.Frame(self, background=GROUND)
        outer.grid(row=3, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)
        canvas = tk.Canvas(outer, highlightthickness=0, background=GROUND,
                           borderwidth=0)
        bar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        bar.grid(row=0, column=1, sticky="ns")
        self.holder = tk.Frame(canvas, background=GROUND)
        win = canvas.create_window((0, 0), window=self.holder, anchor="nw")

        def _fit(_=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(win, width=canvas.winfo_width())
        self.holder.bind("<Configure>", _fit)
        canvas.bind("<Configure>", _fit)
        self.holder.bind("<Enter>", lambda _: canvas.bind_all(
            "<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120),
                                                          "units")))
        self.holder.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))
        self.holder.columnconfigure(0, weight=1)
        self.holder.rowconfigure(0, weight=1)

        self._vars()
        self.panels = {
            "plate": self._step_plate(),
            "numbers": self._step_numbers(),
            "materials": self._step_materials(),
            "build": self._step_build(),
        }
        self.show_step("plate")

        where = ("the share" if not self.store.using_local
                 else "this PC only - the share was unreachable")
        ttk.Label(self, text=f"LOTs, solutions and plate progress are shared on "
                             f"{where}.", style="Muted.TLabel").grid(
            row=4, column=0, sticky="w", pady=(10, 0))

    # ------------------------------------------------------------------ vars

    def _vars(self):
        self.lay_var = tk.StringVar()
        self.txt_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.batch_var = tk.StringVar()
        self.initials_var = tk.StringVar()
        # 'Day 1' and 'IgG isolation' were the same date in two boxes.  The
        # isolation date IS day 1, so it drives the other two directly.
        self.date_vars = {k: tk.StringVar() for k, _, _ in ws_sheets.WORKSHEETS}
        self.date_var = self.date_vars["isolation"]
        self.date_var.set(datetime.date.today().strftime("%d.%m.%Y"))
        self.date_var.trace_add("write", lambda *_: self.spread_dates())
        self.aliquot_var = tk.StringVar(value="40")
        # Where the blank worksheet PDFs are.  Empty until the analyst points
        # at the folder themselves - the program never goes looking on the
        # Glikobiologija share on its own.
        self.blank_var = tk.StringVar(value=self.store.blanks_folder())
        self.enzyme_var = tk.StringVar(value="30")
        self.strict_var = tk.BooleanVar(value=True)
        self.attach_var = tk.BooleanVar(value=False)
        self.skip_solutions = tk.BooleanVar(value=False)
        self.num_vars, self.cons_vars, self.cons_boxes, self.sol_vars = {}, {}, {}, {}

    # ----------------------------------------------------------------- steps

    def show_step(self, key):
        for k, panel in getattr(self, "panels", {}).items():
            panel.grid_remove()
        self.panels[key].grid(row=0, column=0, sticky="nsew")
        self.rail.show(key)

    def _step_plate(self):
        wrap = tk.Frame(self.holder, background=GROUND)
        wrap.columnconfigure(0, weight=1)

        c = Card(wrap, "The plate",
                 "Both files go in here once.  The .txt is only needed on day 2 "
                 "- leave it empty until the NanoDrop is done.")
        c.grid(row=0, column=0, sticky="ew")
        for i, (label, var, cmd) in enumerate((
                ("Pippeting List (.xlsx)", self.lay_var, self.pick_layout),
                ("NanoDrop concentrations (.txt)", self.txt_var, self.pick_txt),
                ("Save everything into", self.out_var, self.pick_out))):
            ttk.Label(c.body, text=label, style="Card.TLabel").grid(
                row=i, column=0, sticky="w", pady=5, padx=(0, 12))
            ttk.Entry(c.body, textvariable=var).grid(row=i, column=1, sticky="ew",
                                                     pady=5, padx=(0, 8))
            ttk.Button(c.body, text="Browse...", command=cmd).grid(row=i, column=2)

        d = Card(wrap, "This run",
                 "Three days of bench work.  Put day 1 in and the other two "
                 "follow on the next working days - start on a Friday and you "
                 "get Monday and Tuesday, not the weekend.")
        d.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        d.body.columnconfigure(1, weight=0)
        d.body.columnconfigure(6, weight=1)          # slack goes on the right
        field(d.body, 0, "GA batch No.", self.batch_var, 20)
        field(d.body, 0, "Analyst initials", self.initials_var, 8, col=3)
        field(d.body, 1, "Aliquot dried down", self.aliquot_var, 8, col=3,
              unit="µL")
        for i, (key, _, name) in enumerate(ws_sheets.WORKSHEETS):
            date_field(d.body, 1 + i, f"Day {i + 1}  -  {name}",
                       self.date_vars[key])
        self.spread_dates()

        self.plate_info = ttk.Label(wrap, text="No plate loaded yet.",
                                    style="Muted.TLabel")
        self.plate_info.grid(row=2, column=0, sticky="w", pady=(12, 0))
        return wrap

    def _step_numbers(self):
        wrap = tk.Frame(self.holder, background=GROUND)
        wrap.columnconfigure(0, weight=1)
        c = Card(wrap, "Worksheet and storage numbers",
                 "They are taken in a run, so only the first is worth typing - "
                 "press Fill down and the rest follow (GA3084, GA3085, GA3086).")
        c.grid(row=0, column=0, sticky="ew")

        def group(col, heading, rows):
            f = ttk.Frame(c.body, style="Card.TFrame")
            f.grid(row=0, column=col, sticky="nw", padx=(0, 44))
            ttk.Label(f, text=heading, style="CardMuted.TLabel").grid(
                row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
            order = []
            for i, (key, label) in enumerate(rows):
                ttk.Label(f, text=label, style="Card.TLabel").grid(
                    row=i + 1, column=0, sticky="w", pady=4, padx=(0, 12))
                v = tk.StringVar()
                self.num_vars[key] = v
                order.append(v)
                ttk.Entry(f, textvariable=v, width=15).grid(row=i + 1, column=1,
                                                            sticky="w", pady=4)
            ttk.Button(f, text="Fill down",
                       command=lambda o=order: self.fill_down(o)).grid(
                row=1, column=2, sticky="w", padx=(10, 0))
            return order

        self.ws_order = group(0, "Working worksheets",
                              [(k, n) for k, _, n in ws_sheets.WORKSHEETS])
        self.store_order = group(1, "Storage (GBL-WS-002)",
                                 list(ws_sheets.STORAGE))

        extra = ttk.Frame(c.body, style="Card.TFrame")
        extra.grid(row=1, column=0, columnspan=2, sticky="w", pady=(16, 0))
        for i, (key, label) in enumerate(
                (("reception", "Sample reception worksheet no."),
                 ("sample_storage", "Sample storage worksheet no."))):
            ttk.Label(extra, text=label, style="Card.TLabel").grid(
                row=0, column=i * 2, sticky="w", padx=(0 if i == 0 else 28, 10))
            v = tk.StringVar()
            self.num_vars[key] = v
            ttk.Entry(extra, textvariable=v, width=15).grid(row=0, column=i * 2 + 1,
                                                            sticky="w")
        return wrap

    def _step_materials(self):
        wrap = tk.Frame(self.holder, background=GROUND)
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(1, weight=1)

        c = Card(wrap, "Filter plates and enzyme",
                 "Grouped by the day they are opened.  The last one used is "
                 "offered - check it against the label in front of you before "
                 "printing; what was used last is a convenience, not proof.")
        c.grid(row=0, column=0, sticky="ew")
        day_of = dict((k, n) for k, _, n in ws_sheets.WORKSHEETS)
        n, row = len(store_mod.CONSUMABLE_FIELDS), 0
        seen_day = None
        for key, label, day in store_mod.CONSUMABLE_FIELDS:
            if day != seen_day:
                seen_day = day
                ttk.Label(c.body, text=day_of.get(day, day),
                          style="CardMuted.TLabel").grid(
                    row=row, column=0, columnspan=3, sticky="w",
                    pady=(10 if row else 0, 2))
                row += 1
            i = row
            row += 1
            ttk.Label(c.body, text=label, style="Card.TLabel").grid(
                row=i, column=0, sticky="w", pady=4, padx=(0, 12))
            v = tk.StringVar()
            self.cons_vars[key] = v
            box = ttk.Combobox(c.body, textvariable=v, width=30,
                               values=self.store.options(key))
            box.grid(row=i, column=1, sticky="w", pady=4)
            self.cons_boxes[key] = box
            opts = self.store.options(key)
            if opts:
                v.set(opts[0])
            if key == "proteing_no":
                v.trace_add("write", lambda *_: self.show_proteing_uses())
                self.uses_lbl = ttk.Label(c.body, text="",
                                          style="CardMuted.TLabel")
                self.uses_lbl.grid(row=i, column=2, sticky="w", padx=(14, 0))

        vial = ttk.Frame(c.body, style="Card.TFrame")
        vial.grid(row=row, column=0, columnspan=3, sticky="w", pady=(12, 0))
        ttk.Label(vial, text="PNGase F vial", style="Card.TLabel").grid(
            row=0, column=0, padx=(0, 12))
        ttk.Radiobutton(vial, text="30 µg", value="30",
                        variable=self.enzyme_var).grid(row=0, column=1, padx=(0, 16))
        ttk.Radiobutton(vial, text="50 µg", value="50",
                        variable=self.enzyme_var).grid(row=0, column=2)
        ttk.Label(vial, text="decides which 'Enzyme LOT' line is filled",
                  style="CardMuted.TLabel").grid(row=0, column=3, padx=(16, 0))

        s = Card(wrap, "Solutions",
                 "Pick the preparation you are using.  Everyone shares the "
                 "list, so a bottle someone else made is already here.  Remove "
                 "one when it has been used up.")
        s.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        ttk.Checkbutton(s.body, text="Skip these and fill the tables in by hand "
                                     "after printing",
                        variable=self.skip_solutions).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        cols = ttk.Frame(s.body, style="Card.TFrame")
        cols.grid(row=1, column=0, columnspan=3, sticky="w")
        for ci, (key, _, name) in enumerate(ws_sheets.WORKSHEETS):
            col = ttk.Frame(cols, style="Card.TFrame")
            col.grid(row=0, column=ci, sticky="nw", padx=(0, 30))
            ttk.Label(col, text=name, style="CardMuted.TLabel").grid(
                row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
            for i, sol in enumerate(store_mod.SOLUTIONS[key]):
                ttk.Label(col, text=store_mod.SOLUTION_LABELS.get(sol, sol),
                          style="Card.TLabel").grid(row=i + 1, column=0,
                                                    sticky="w", pady=3,
                                                    padx=(0, 10))
                v = tk.StringVar()
                self.sol_vars[sol] = v
                cb = ttk.Combobox(col, textvariable=v, width=13,
                                  values=self.store.solution_options(sol))
                cb.grid(row=i + 1, column=1, sticky="w", pady=3)
                self.cons_boxes[f"sol::{sol}"] = cb
                bar = ttk.Frame(col, style="Card.TFrame")
                bar.grid(row=i + 1, column=2, sticky="w", padx=(6, 0))
                ttk.Button(bar, text="+", width=2,
                           command=lambda x=sol: self.add_solution(x)).grid(
                    row=0, column=0)
                ttk.Button(bar, text="−", width=2,
                           command=lambda x=sol: self.remove_solution(x)).grid(
                    row=0, column=1, padx=(3, 0))
        self.refresh_solutions()
        return wrap

    def _step_build(self):
        wrap = tk.Frame(self.holder, background=GROUND)
        wrap.columnconfigure(0, weight=1)

        c = Card(wrap, "Build",
                 "Any of these, in any order, as often as you like.  Building "
                 "something twice does not double-count anything.")
        c.grid(row=0, column=0, sticky="ew")

        def row(r, day, main_text, main_cmd, extras, accent=True):
            f = ttk.Frame(c.body, style="Card.TFrame")
            f.grid(row=r, column=0, columnspan=3, sticky="w", pady=6)
            ttk.Label(f, text=day, style="CardMuted.TLabel", width=9).grid(
                row=0, column=0, sticky="w")
            b = (AccentButton(f, main_text, main_cmd) if accent
                 else ttk.Button(f, text=main_text, command=main_cmd))
            b.grid(row=0, column=1)
            for i, (t, cmd) in enumerate(extras):
                ttk.Button(f, text=t, command=cmd).grid(row=0, column=2 + i,
                                                        padx=(8, 0))
            return b

        self.iso_btn = row(0, "Day 1", "IgG isolation worksheet",
                           self.build_isolation,
                           [("Open", lambda: self.open_built("isolation")),
                            ("Print", lambda: self.print_built("isolation"))])
        self.day2_btn = row(1, "Day 2-3", "Workbook + deglyco + clean up",
                            self.build_day2,
                            [("Print deglyco", lambda: self.print_built("deglyco")),
                             ("Print clean up", lambda: self.print_built("cleanup"))])
        self.wb_btn = row(2, "Any time", "Concentration workbook only",
                          self.build_workbook,
                          [("Open", self.open_workbook)], accent=False)
        self.stor_btn = row(3, "", "Storage worksheets (×3)",
                            self.build_storage,
                            [("Open folder", self.open_folder)], accent=False)

        opts = ttk.Frame(c.body, style="Card.TFrame")
        opts.grid(row=4, column=0, columnspan=3, sticky="w", pady=(14, 0))
        ttk.Checkbutton(opts, text="Stop if the layout does not match the readings",
                        variable=self.strict_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(opts, text="Separate sheet to attach, instead of filling "
                                   "the worksheets",
                        variable=self.attach_var).grid(row=1, column=0, sticky="w")
        self.note = ttk.Label(c.body, text="", style="CardMuted.TLabel")
        self.note.grid(row=5, column=0, columnspan=3, sticky="w", pady=(12, 0))

        # Where the blank worksheets are.  Shown rather than hidden, because
        # pointing it at the wrong folder is easy and the only symptom is
        # 'no blank worksheet found' three clicks later.
        ttk.Separator(c.body, orient="horizontal").grid(
            row=6, column=0, columnspan=3, sticky="ew", pady=(14, 8))
        wsrow = ttk.Frame(c.body, style="Card.TFrame")
        wsrow.grid(row=7, column=0, columnspan=3, sticky="ew")
        wsrow.columnconfigure(1, weight=1)
        ttk.Label(wsrow, text="Blank worksheets", style="CardMuted.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 10))
        self.blanks_lbl = ttk.Label(wsrow, style="Card.TLabel",
                                    text=self.blank_var.get() or "not chosen yet")
        self.blanks_lbl.grid(row=0, column=1, sticky="w")
        ttk.Button(wsrow, text="Worksheets folder",
                   command=self.change_blanks).grid(row=0, column=2, sticky="e")

        return wrap

    # --------------------------------------------------------------- helpers

    def spread_dates(self):
        """The isolation date typed -> the other two on the next working days."""
        try:
            start = datetime.datetime.strptime(self.date_var.get().strip(),
                                               "%d.%m.%Y").date()
        except ValueError:
            return
        days = ws_fill.working_days(start, len(ws_sheets.WORKSHEETS))
        for (key, _, _n), d in zip(ws_sheets.WORKSHEETS, days):
            self.date_vars[key].set(d.strftime("%d.%m.%Y"))

    def fill_down(self, order):
        first = order[0].get().strip()
        if not first:
            messagebox.showinfo("Type the first one",
                                "Put the first number in and press Fill down - "
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

    def show_proteing_uses(self):
        if not hasattr(self, "uses_lbl"):
            return
        no = self.cons_vars["proteing_no"].get().strip()
        if not no:
            self.uses_lbl.config(text="")
            return
        used = self.store.proteing_uses(no)
        batch = self.batch_var.get().strip()
        seen = (self.store._read(store_mod.CONSUMABLES_FILE)
                .get("_proteing", {}).get(no, {}).get("batches", []))
        nxt = used if (batch and batch in seen) else used + 1
        self.uses_lbl.config(
            text=f"used on {used} plate(s)  →  this is no. {nxt}")

    # ------------------------------------------------------------- solutions

    def refresh_solutions(self):
        """Reload each dropdown and select the preparation last used."""
        last = self.store.solutions()
        for key, _, _n in ws_sheets.WORKSHEETS:
            for sol in store_mod.SOLUTIONS[key]:
                opts = self.store.solution_options(sol)
                box = self.cons_boxes.get(f"sol::{sol}")
                if box is not None:
                    box.configure(values=opts)
                var = self.sol_vars.get(sol)
                if var is not None and not var.get().strip():
                    var.set(last.get(sol, ""))

    def add_solution(self, sol):
        SolutionDialog(self, sol, self.store, on_done=self.refresh_solutions)

    def remove_solution(self, sol):
        var = self.sol_vars.get(sol)
        date = var.get().strip() if var else ""
        if not date:
            messagebox.showinfo(
                "Nothing selected",
                "Pick the preparation you want to remove first.")
            return
        label = store_mod.SOLUTION_LABELS.get(sol, sol)
        if not messagebox.askyesno(
                "Remove this preparation?",
                f"Take {label} prepared {date} off the list?\n\n"
                "It will stop being offered to everyone.  Worksheets already "
                "printed are not touched."):
            return
        self.store.forget_solution(sol, date)
        var.set("")
        self.refresh_solutions()
        self.app.say(f"Removed {label} prepared {date} from the shared list.")

    # ----------------------------------------------------------------- plate

    def load(self, path, batch=None):
        from igg_conc_gui import read_layout, BuildError
        path = _norm(path)
        if not path or not os.path.isfile(path):
            messagebox.showerror(
                "Not found",
                f"The Pippeting List for this plate is not where it was:\n\n"
                f"{path}\n\nPick it again with Browse and it will be relinked.")
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
            self.out_var.set(output_folder(self.batch_var.get().strip()))

        self.title_lbl.config(text=self.batch_var.get().strip()
                              or os.path.basename(path))
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
        names = dict((k, n) for k, _, n in ws_sheets.WORKSHEETS)
        self.app.say(f"Restored {batch} (saved {saved.get('saved', '?')}).")
        if done:
            self.app.say(f"  already built: {', '.join(done)}")
        self.note.config(text="Already built: "
                              + ", ".join(names[k] for k in done if k in names)
                         if done else "")
        self.stage_lbl.config(
            text=("all three worksheets built" if len(done) >= 3
                  else f"{len(done)} of 3 worksheets built" if done
                  else "nothing built yet"),
            style=("Good.TLabel" if len(done) >= 3
                   else "Warn.TLabel" if done else "Sub.TLabel"))

    # --------------------------------------------------------------- pickers

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

    def blanks(self):
        """-> the blank-worksheets folder, asking for it once if need be.

        The program does not go hunting on the share; the analyst points at
        the folder and it is remembered from then on.
        """
        folder = _norm(self.blank_var.get().strip())
        if folder and os.path.isdir(folder):
            return folder
        messagebox.showinfo(
            "Where are the blank worksheets?",
            "Point at the folder holding the blank worksheet PDFs - the ones "
            "named GBL-WS-029, 030, 031 and 002.\n\n"
            "You only have to do this once; it is remembered afterwards.")
        picked = filedialog.askdirectory(title="Folder holding the blank worksheets")
        if not picked:
            return ""
        picked = _norm(picked)
        if not self.check_blanks(picked):
            return ""
        self.blank_var.set(picked)
        self.store.set_blanks_folder(picked)
        if hasattr(self, "blanks_lbl"):
            self.blanks_lbl.config(text=picked)
        return picked

    def check_blanks(self, folder):
        """-> True if `folder` actually holds blank worksheets.

        Checked when it is picked rather than only at build time, so a wrong
        folder is caught while the analyst is still looking at the chooser
        instead of three clicks later as 'no blank worksheet found'.
        """
        try:
            found = ws_fill.discover(folder)
        except ws_fill.FillError:
            found = {}
        if found:
            return True
        messagebox.showerror(
            "No worksheets in that folder",
            folder + "\n\nhas no blank worksheet PDFs in it.\n\n"
            "The program is looking for files whose names start GBL-WS-029, "
            "GBL-WS-030, GBL-WS-031 and GBL-WS-002.\n\n"
            "Pick the folder those PDFs are actually in.")
        return False

    def change_blanks(self):
        """Re-point at the blank worksheets folder."""
        picked = filedialog.askdirectory(
            title="Folder holding the blank worksheets",
            initialdir=self.blank_var.get() or None)
        if not picked:
            return
        picked = _norm(picked)
        if not self.check_blanks(picked):
            return
        self.blank_var.set(picked)
        self.store.set_blanks_folder(picked)
        self.blanks_lbl.config(text=picked)
        found = ws_fill.discover(picked)
        self.app.say(f"Blank worksheets folder set to {picked}")
        for k, v in sorted(found.items()):
            self.app.say(f"  found {k}: {os.path.basename(v)}")

    # ----------------------------------------------------------------- state

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
        dates = {}
        for key, _, _n in ws_sheets.WORKSHEETS:
            raw = self.date_vars[key].get().strip()
            try:
                dates[key] = datetime.datetime.strptime(raw, "%d.%m.%Y").date()
            except ValueError:
                raise ValueError(f"The {key} date must look like 21.09.2026.")

        cons = {k: v.get().strip() for k, v in self.cons_vars.items()}
        cons[f"enzyme_lot_{self.enzyme_var.get()}"] = cons.pop("enzyme_lot", "")
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
            "dates": dates, "batch": batch,
            "initials": self.initials_var.get().strip().upper(),
            "numbers": {k: v.get().strip() for k, v in self.num_vars.items()},
            "consumables": cons, "solutions": sols,
        }

    def save_state(self, built=None):
        batch = self.batch_var.get().strip()
        if not batch:
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

    def remember_consumables(self, count_proteing=False):
        who = self.initials_var.get().strip().upper()
        batch = self.batch_var.get().strip()
        for key, var in self.cons_vars.items():
            self.store.remember(key, var.get().strip(), who)
            self.cons_boxes[key].configure(values=self.store.options(key))
        if not self.skip_solutions.get():
            for name, var in self.sol_vars.items():
                self.store.remember_solution(name, var.get().strip())
            self.refresh_solutions()
        if count_proteing:
            no = self.cons_vars["proteing_no"].get().strip()
            if no and batch:
                n = self.store.record_proteing_use(no, batch, who)
                self.app.say(f"Protein G plate {no}: now used on {n} plate(s).")
                self.show_proteing_uses()

    # ---------------------------------------------------------------- builds

    def _produce(self, keys, spec, avg):
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
        folder = self.blanks()
        sources = ws_fill.discover(folder)
        names = dict((k, n) for k, _, n in ws_sheets.WORKSHEETS)
        missing = [k for k in keys if k not in sources]
        if missing:
            self.app.say("")
            self.app.say(f"  !! Looked in:  {folder}")
            for k in missing:
                self.app.say(f"  !! and found no blank worksheet for "
                             f"{names[k]} - a PDF whose name starts "
                             f"{ws_fill.WS_CODES[k]}")
            self.app.say("  !! That folder is not the one with the blank "
                         "worksheets in it.")
            self.app.say("  !! Press 'Worksheets folder' at the bottom of "
                         "Build and point at the right one.")
        return ws_fill.fill_all(
            sources, spec["out"], self.layout, batch=spec["batch"],
            numbers=spec["numbers"], date=spec["date"], initials=spec["initials"],
            avg_conc=avg, aliquot_ul=spec["aliquot"], pages=keys,
            colours=self.colours, consumables=spec["consumables"],
            solutions=spec["solutions"], dates=spec["dates"], log=self.app.say)

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
            self.remember_consumables(count_proteing=True)
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

    def workbook_path(self, spec=None):
        out = _norm((spec or {}).get("out") or self.out_var.get().strip())
        batch = (spec or {}).get("batch") or self.batch_var.get().strip()
        return os.path.join(out, f"{batch or 'plate'}.xlsx") if out else ""

    def build_workbook(self):
        from igg_conc_gui import build
        try:
            spec = self.gather()
        except ValueError as e:
            messagebox.showwarning("Not ready", str(e))
            return
        txt = _norm(self.txt_var.get().strip())
        if not txt or not os.path.isfile(txt):
            messagebox.showwarning(
                "NanoDrop file",
                "Pick the NanoDrop .txt for this plate - the workbook is built "
                "from it.")
            return
        wb = self.workbook_path(spec)
        if os.path.exists(wb) and not messagebox.askyesno(
                "Overwrite?",
                os.path.basename(wb) + " already exists.\n\nOverwrite it?"):
            return

        def work():
            build(txt, spec["lay"], wb, strict=self.strict_var.get(),
                  log=self.app.say)
            self.built["workbook"] = wb
            self.save_state()
            self.app.say("")
            self.app.say(f"Saved {os.path.basename(wb)} into {spec['out']}")
            self.note.config(text=f"Built {os.path.basename(wb)}")

        self.app.go(self.wb_btn, wb, False, work)

    def build_storage(self):
        try:
            spec = self.gather()
        except ValueError as e:
            messagebox.showwarning("Not ready", str(e))
            return
        taken = [k for k, _ in ws_sheets.STORAGE if spec["numbers"].get(k)]
        if not taken:
            messagebox.showwarning(
                "No storage numbers",
                "Put the GBL-WS-002 storage numbers in first - one sheet is "
                "produced per number.")
            return

        def work():
            sources = ws_fill.discover(self.blanks())
            if "storage" not in sources:
                self.app.say("  !! no blank GBL-WS-002 found in the worksheets "
                             "folder")
                return
            written = ws_fill.fill_storage_sheets(
                sources["storage"], spec["out"], self.layout,
                batch=spec["batch"], numbers=spec["numbers"],
                date=spec["dates"].get("isolation") or spec["date"],
                dates=spec["dates"], colours=self.colours, kinds=taken,
                labels=ws_fill.storage_labels(
                    spec["batch"], spec["numbers"], spec["dates"],
                    spec["initials"], spec["date"]),
                log=self.app.say)
            self.app.say("")
            self.app.say(f"Saved {len(written)} storage worksheet(s) into "
                         f"{spec['out']}")
            self.app.say("  the fridge/freezer letter and drawer are left blank "
                         "- fill those in at the freezer")
            self.note.config(text=f"Built {len(written)} storage worksheet(s)")

        self.app.go(self.stor_btn, spec["out"], False, work)

    # ------------------------------------------------------------------ open

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

    def open_workbook(self):
        wb = self.workbook_path()
        if not wb or not os.path.isfile(wb):
            messagebox.showinfo("Not built yet",
                                "The concentration workbook is not in the save "
                                "folder yet.")
            return
        try:
            os.startfile(wb)
        except Exception as e:
            messagebox.showerror("Could not open it", str(e))

    def open_folder(self):
        out = _norm(self.out_var.get().strip())
        if out and os.path.isdir(out):
            os.startfile(out)


class MainView(tk.Frame):
    """The green rail beside the run."""

    def __init__(self, parent, app):
        super().__init__(parent, background=GROUND)
        self.store = store_mod.Store(log=app.say)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.plates = Sidebar(self, self.open_plate, self.store)
        self.plates.grid(row=0, column=0, sticky="nsw")
        self.panel = PlateRunPanel(self, app, self.store,
                                   on_built=self.refresh_list)
        self.panel.grid(row=0, column=1, sticky="nsew")

    def open_plate(self, row):
        self.panel.load(row.get("layout"), row.get("batch"))

    def refresh_list(self, batch=None):
        self.plates.refresh(select=batch)
