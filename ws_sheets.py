#!/usr/bin/env python3
"""
Companion sheets for the three GlycanAge worksheets.

One page each for GBL-WS-031/07 (IgG isolation), GBL-WS-029/04
(deglycosylation + APTS labelling) and GBL-WS-030/04 (HILIC-SPE clean-up).
Each page carries the filled 8x12 "List of samples" grid and the numbers
that *that* worksheet asks for, so it can be printed and attached on the
day it is used.

GBL-WS-030/04 step 3 says outright: "write down the correct sample list in
the provided table or paste printed table with sample name" - attaching a
printed list is already how these are meant to be filled.

The worksheets are controlled documents and are never modified.  Anything
the operator has to observe - times, LOT numbers, plate labels, signatures
- stays on the worksheet.
"""
import os
import re
import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer, PageBreak)

ROWS = "ABCDEFGH"

# same colours as the concentration workbook, so the two read alike
CELL_COLOURS = {
    "blank":    colors.HexColor("#FFC7CE"),   # red
    "STAND_08": colors.HexColor("#C6EFCE"),   # green
    "STAND_09": colors.HexColor("#BDD7EE"),   # blue
    "STAND_10": colors.HexColor("#FFEB9C"),   # yellow
    "filler":   colors.HexColor("#E8E8E8"),   # grey - HiDi etc.
}
FILLER_NAMES = {"hidi", "hi-di", "formamide"}

# The three worksheets a plate runs through.  The number taken for each is
# quoted by the next one, which is why they are collected in one place.
WORKSHEETS = [
    ("isolation", "GBL-WS-031/07", "IgG isolation"),
    ("deglyco",   "GBL-WS-029/04", "Deglycosylation"),
    ("cleanup",   "GBL-WS-030/04", "Clean up"),
]
# The three GBL-WS-002 storage numbers taken for a plate - one per output.
STORAGE = [
    ("eluate",     "IgG eluate"),
    ("dry_eluate", "Dry IgG eluate"),
    ("apts",       "APTS labelled IgG N-glycans"),
]

# What each worksheet asks for, in its own wording.
PAGES = [
    {
        "key": "isolation", "code": "GBL-WS-031/07", "step": "step 1.3",
        "name": "IgG isolation",
        "title": "IgG isolation from DBS and plasma",
        "refs": [("reception",      "Sample reception worksheet no."),
                 ("sample_storage", "Sample storage worksheet no."),
                 ("dry_eluate",     "Dry sample storage worksheet no."),
                 ("eluate",         "IgG eluate storage worksheet no.")],
        "show_plate_detail": True,
        "show_plate_label": True,
    },
    {
        "key": "deglyco", "code": "GBL-WS-029/04", "step": "step 1",
        "name": "Deglycosylation",
        "title": "In solution deglycosylation and APTS labelling",
        "refs": [("isolation",  "IgG isolation worksheet no."),
                 ("dry_eluate", "Dry sample storage worksheet no.")],
        "show_dried_igg": True,
    },
    {
        "key": "cleanup", "code": "GBL-WS-030/04", "step": "step 3",
        "name": "Clean up",
        "title": "HILIC-SPE clean-up for CGE-LIF and ABI3500 run",
        "refs": [("deglyco", "In solution deglycosylation and APTS "
                             "labelling worksheet no."),
                 ("apts",    "APTS IgG N-glycan storage worksheet no.")],
    },
]

CODE_BY_KEY = {k: c for k, c, _ in WORKSHEETS}


def classify_cell(name):
    """-> ('standard', group) | ('blank', None) | ('filler', None) | ('sample', None)"""
    if not name:
        return "empty", None
    m = re.match(r"(STAND_\d+)_\d+$", name)
    if m:
        return "standard", m.group(1)
    if name.lower().startswith("blank"):
        return "blank", None
    if name.lower() in FILLER_NAMES:
        return "filler", None
    return "sample", None


BATCH_RE = re.compile(r"([0-9]+[-_]GA[-_][0-9]{4,6})", re.I)


def batch_from_path(path):
    """Work out the GA batch from where the layout file lives.

    The batch is not stored in any cell of the Pippeting List, so it comes
    from the file name ('999-GA-202609 Pippeting List.xlsx') and, failing
    that, from the plate folder the file sits in ('999-GA-202609').
    """
    path = os.path.abspath(path)
    candidates = [os.path.basename(path)]
    d = os.path.dirname(path)
    for _ in range(2):                      # plate folder, then its parent
        candidates.append(os.path.basename(d))
        d = os.path.dirname(d)
    for c in candidates:
        m = BATCH_RE.match(c) or BATCH_RE.search(c)
        if m:
            return m.group(1)
    return ""


# kept so older callers keep working
batch_from_filename = batch_from_path


def plate_label(batch, storage_no, date, initials):
    """'999-GA-202609 IgG eluate ss0912 18.09.2026 MF'

    The label written on the 1 mL collection plate that holds the IgG
    eluate: batch, what is in it, the storage sheet number it is logged
    under, the date, and who did it.
    """
    bits = [batch or "", "IgG eluate"]
    if storage_no:
        bits.append(f"ss{storage_no}")
    bits.append(date.strftime("%d.%m.%Y"))
    if initials:
        bits.append(initials)
    return " ".join(b for b in bits if b)


def summarise(layout):
    """-> dict of standards / blanks / fillers / samples / donors."""
    stands, blanks, fillers, samples = {}, [], [], []
    for well, name in layout.items():
        kind, grp = classify_cell(name)
        if kind == "standard":
            stands.setdefault(grp, []).append(well)
        elif kind == "blank":
            blanks.append(well)
        elif kind == "filler":
            fillers.append(well)
        elif kind == "sample":
            samples.append(well)
    donors = {re.sub(r"_\d+$", "", layout[w]) for w in samples}
    return {"stands": stands, "blanks": blanks, "fillers": fillers,
            "samples": samples, "donors": donors}


def well_key(w):
    return (int(w[1:]), ROWS.index(w[0]))


# --------------------------------------------------------------- rendering

def _styles():
    return {
        "h1":    ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=12,
                                spaceAfter=1),
        "sub":   ParagraphStyle("sub", fontName="Helvetica", fontSize=8,
                                textColor=colors.HexColor("#444444")),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=7.5,
                                leading=10),
        "foot":  ParagraphStyle("foot", fontName="Helvetica-Oblique",
                                fontSize=6.5,
                                textColor=colors.HexColor("#666666")),
    }


def _grid(layout, ncols):
    """The filled 8 x ncols plate table."""
    rows = [[""] + [str(c) for c in range(1, ncols + 1)]]
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("BOX", (0, 0), (-1, -1), 0.9, colors.black),
        ("FONT", (0, 0), (-1, -1), "Helvetica", 5.4),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 7),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    for ri, rl in enumerate(ROWS, start=1):
        line = [rl]
        for ci in range(1, ncols + 1):
            name = layout.get(f"{rl}{ci}", "")
            line.append(name)
            kind, grp = classify_cell(name)
            key = grp if kind == "standard" else (
                kind if kind in ("blank", "filler") else None)
            if key in CELL_COLOURS:
                style.append(("BACKGROUND", (ci, ri), (ci, ri), CELL_COLOURS[key]))
        rows.append(line)

    label_w = 7 * mm
    cell_w = (landscape(A4)[0] - 20 * mm - label_w) / ncols
    t = Table(rows, colWidths=[label_w] + [cell_w] * ncols,
              rowHeights=[6 * mm] + [9 * mm] * 8)
    t.setStyle(TableStyle(style))
    return t


def _page(cfg, layout, info, batch, numbers, date, avg_conc, aliquot_ul,
          source_name, sheet_name, initials, st):
    """Flowables for one worksheet's companion page."""
    def val(k):
        return numbers.get(k) or "—"

    story = [
        Paragraph(f"{cfg['name']} &mdash; list of samples", st["h1"]),
        Paragraph(f"{cfg['title']}, {cfg['step']} &nbsp;&middot;&nbsp; companion "
                  f"sheet for <font color='#888888'>{cfg['code']}</font>, attach to "
                  "the worksheet. The worksheet itself is the controlled record.",
                  st["sub"]),
        Spacer(1, 3.5 * mm),
    ]

    # ---- identifying details --------------------------------------------
    head = [["GA batch No.:", batch or "—",
             f"{cfg['name']} no.:", val(cfg["key"]),
             "Date:", date.strftime("%d.%m.%Y"),
             "Analyst:", initials or ""]]
    t = Table(head, colWidths=[24 * mm, 36 * mm, 30 * mm, 24 * mm,
                               14 * mm, 24 * mm, 20 * mm, 30 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("FONT", (0, 0), (0, 0), "Helvetica-Bold", 8),
        ("FONT", (2, 0), (2, 0), "Helvetica-Bold", 8),
        ("FONT", (4, 0), (4, 0), "Helvetica-Bold", 8),
        ("FONT", (6, 0), (6, 0), "Helvetica-Bold", 8),
        ("FONT", (1, 0), (1, 0), "Helvetica-Bold", 9),
        ("FONT", (3, 0), (3, 0), "Helvetica-Bold", 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (7, 0), (7, 0), 0.5, colors.black),
    ]))
    story += [t, Spacer(1, 2.5 * mm)]

    # ---- the numbers this worksheet quotes ------------------------------
    ref_rows = [[Paragraph("<b>This worksheet also asks for</b>", st["small"]), ""]]
    for key, label in cfg["refs"]:
        ref_rows.append([label, val(key)])
    if cfg.get("show_dried_igg"):
        # The worksheet wants two figures - DBS samples and plasma standards -
        # each the mean concentration times the aliquot volume dried down.
        dbs, std = avg_conc if avg_conc else (None, None)
        if dbs is not None or std is not None:
            def ug(c):
                return f"{c * aliquot_ul:.1f}" if c is not None else "—"
            txt = (f"<b>{ug(dbs)} / {ug(std)} µg</b> &nbsp;"
                   f"<font size=6.5 color='#666666'>(DBS {dbs:.4f} / standards "
                   f"{std:.4f} mg/ml &times; {aliquot_ul:g} µL)</font>")
        else:
            txt = ("— / — &nbsp;<font size=6.5 color='#666666'>"
                   "(add the NanoDrop file to compute these)</font>")
        ref_rows.append([Paragraph("Average amount of dried IgG "
                                   "(DBS / plasma; µg)", st["small"]),
                         Paragraph(txt, st["small"])])

    rt = Table(ref_rows, colWidths=[96 * mm, 60 * mm])
    rt.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
        ("FONT", (1, 1), (1, -1), "Helvetica-Bold", 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#999999")),
        ("LINEBEFORE", (1, 0), (1, -1), 0.5, colors.HexColor("#999999")),
    ]))
    story += [rt, Spacer(1, 3 * mm)]

    # ---- plate detail, only where the worksheet asks for it -------------
    if cfg.get("show_plate_label"):
        lbl = plate_label(batch, numbers.get("eluate"), date, initials)
        pl = Table([["1 mL collection plate label:", Paragraph(
            f"<font face='Helvetica-Bold' size='9'>{lbl}</font>", st["small"])]],
            colWidths=[38 * mm, 138 * mm])
        pl.setStyle(TableStyle([
            ("FONT", (0, 0), (0, 0), "Helvetica-Bold", 7.5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F7F7")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story += [pl, Spacer(1, 2.5 * mm)]

    if cfg.get("show_plate_detail"):
        std_names = ", ".join(sorted(info["stands"])) or "—"
        blank_txt = ", ".join(f"{w} ({layout[w]})"
                              for w in sorted(info["blanks"], key=well_key)) or "—"
        pd = Table([["Plasma standards:", std_names, "Blanks:", blank_txt]],
                   colWidths=[28 * mm, 60 * mm, 18 * mm, 70 * mm])
        pd.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
            ("FONT", (0, 0), (0, 0), "Helvetica-Bold", 7.5),
            ("FONT", (2, 0), (2, 0), "Helvetica-Bold", 7.5),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story += [pd, Spacer(1, 2 * mm)]

    # ---- grid ------------------------------------------------------------
    ncols = max(max((int(w[1:]) for w in layout), default=12), 12)
    story += [_grid(layout, ncols), Spacer(1, 3 * mm)]

    # ---- legend and counts ----------------------------------------------
    def swatch(key, text):
        return (f'<font size="7" color="#{CELL_COLOURS[key].hexval()[2:]}">'
                f'■</font> {text}')

    items = [swatch("blank", "blank"), swatch("STAND_08", "STAND_08"),
             swatch("STAND_09", "STAND_09"), swatch("STAND_10", "STAND_10")]
    if info["fillers"]:
        items.append(swatch("filler", "HiDi"))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;".join(items), st["small"]))

    counts = (f"<b>{len(info['samples'])}</b> sample wells "
              f"({len(info['donors'])} donors &times; 3) &nbsp;&middot;&nbsp; "
              f"<b>{sum(len(v) for v in info['stands'].values())}</b> standard wells "
              + " ".join(f"({g}: {len(w)})" for g, w in sorted(info["stands"].items()))
              + f" &nbsp;&middot;&nbsp; <b>{len(info['blanks'])}</b> blanks")
    if info["fillers"]:
        counts += f" &nbsp;&middot;&nbsp; <b>{len(info['fillers'])}</b> HiDi wells"
    story.append(Paragraph(counts, st["small"]))

    story += [
        Spacer(1, 2.5 * mm),
        Paragraph(
            f"Generated {datetime.datetime.now():%d.%m.%Y %H:%M} from "
            f"{source_name or '(layout file)'}"
            + (f", sheet &lsquo;{sheet_name}&rsquo;" if sheet_name else "")
            + ". Positions are set by the randomization in that file &mdash; "
              "check this sheet against it before pipetting.", st["foot"]),
    ]
    return story


def build_worksheet_pack(layout, out_path, batch="", source_name="",
                         sheet_name="", numbers=None, avg_conc=None,
                         aliquot_ul=40.0, pages=None, date=None, initials="",
                         log=print):
    """Render one companion page per selected worksheet into a single PDF.

    avg_conc is (dbs_mean, standards_mean) in mg/ml.  Times the aliquot
    volume dried down, those are the two average-dried-IgG figures
    GBL-WS-029/04 asks for.
    """
    date = date or datetime.date.today()
    numbers = numbers or {}
    wanted = set(pages or [p["key"] for p in PAGES])
    chosen = [p for p in PAGES if p["key"] in wanted]
    if not chosen:
        raise ValueError("No worksheet pages selected.")

    info = summarise(layout)
    st = _styles()

    doc = SimpleDocTemplate(
        out_path, pagesize=landscape(A4),
        leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=10 * mm, bottomMargin=8 * mm,
        title=f"List of samples {batch}".strip(),
        author="IgG Concentration Builder")

    story = []
    for i, cfg in enumerate(chosen):
        if i:
            story.append(PageBreak())
        story += _page(cfg, layout, info, batch, numbers, date,
                       avg_conc, aliquot_ul, source_name, sheet_name,
                       initials, st)
    doc.build(story)

    # ---- report ----------------------------------------------------------
    log(f"Pages             : {len(chosen)}  ("
        + ", ".join(c["name"] for c in chosen) + ")")
    if any(c.get("show_plate_label") for c in chosen):
        log("IgG eluate label  : "
            + plate_label(batch, numbers.get("eluate"), date, initials))
    log(f"Wells on the grid : {len(layout)}")
    log(f"Samples           : {len(info['samples'])}  ({len(info['donors'])} donors)")
    log("Standards         : " + ", ".join(f"{g} ({len(w)})"
                                           for g, w in sorted(info["stands"].items())))
    log("Blanks            : " + ", ".join(
        f"{w} {layout[w]}" for w in sorted(info["blanks"], key=well_key)))
    if info["fillers"]:
        log(f"HiDi wells        : {len(info['fillers'])}")
    if avg_conc and avg_conc[0] is not None:
        dbs, std = avg_conc
        log(f"Avg dried IgG     : DBS {dbs * aliquot_ul:.1f} ug / "
            f"standards {std * aliquot_ul:.1f} ug  "
            f"({dbs:.4f} / {std:.4f} mg/ml x {aliquot_ul:g} uL)")
    missing = [t for k, _, t in WORKSHEETS
               if k in wanted and not numbers.get(k)]
    missing += [s for k, s in STORAGE if not numbers.get(k)]
    if missing:
        log("  !! no number entered for: " + ", ".join(missing))
    log("")
    log(f"Saved: {out_path}")
    return out_path
