#!/usr/bin/env python3
"""
Companion sheet for GBL-WS-031/07, step 1.3 "List of samples".

Fills the 8x12 plate grid from the Pippeting List (sheet 'Plate_layouts')
so it does not have to be copied out by hand at the bench, and prints the
identifying details that can be derived.  Everything the operator must
observe or record - times, LOT numbers, plate numbers, signatures - stays
on the worksheet.

The controlled document itself is never modified; this prints as a separate
page to attach, the way NanoDrop results already are.
"""
import os
import re
import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer)

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


def batch_from_filename(path):
    """'999-GA-202609 Pippeting List.xlsx' -> '999-GA-202609'"""
    m = re.match(r"([0-9]+[-_]GA[-_][0-9]+)", os.path.basename(path), re.I)
    return m.group(1) if m else ""


# The three worksheets a GlycanAge plate runs through, and the three
# GBL-WS-002 storage numbers taken for it.  The worksheets quote each
# other's numbers - WS-029 asks for the isolation number, WS-030 for the
# deglycosylation number - which is why they are collected in one place.
WORKSHEETS = [
    ("isolation",   "GBL-WS-031/07", "IgG isolation (DBS/plasma)"),
    ("deglyco",     "GBL-WS-029/04", "Deglycosylation + APTS labelling"),
    ("cleanup",     "GBL-WS-030/04", "HILIC-SPE clean-up + ABI3500"),
]
STORAGE = [
    ("eluate",      "IgG eluate"),
    ("dry_eluate",  "Dry IgG eluate"),
    ("apts",        "APTS labelled IgG N-glycans"),
]


def build_sample_list_pdf(layout, out_path, batch="", source_name="",
                          sheet_name="", date=None, numbers=None, log=print):
    """Render the filled 'List of samples' grid as a one-page A4 landscape PDF.

    `numbers` is an optional dict of worksheet / storage numbers keyed by the
    ids in WORKSHEETS, STORAGE, plus 'reception' and 'sample_storage'.
    """
    date = date or datetime.date.today()
    numbers = numbers or {}

    # ---- summarise what is on the plate ---------------------------------
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

    def wkey(w):
        return (int(w[1:]), ROWS.index(w[0]))

    # donors: GA-RW-A00792_3 -> GA-RW-A00792
    donors = {re.sub(r"_\d+$", "", layout[w]) for w in samples}

    # ---- page ------------------------------------------------------------
    doc = SimpleDocTemplate(
        out_path, pagesize=landscape(A4),
        leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=10 * mm, bottomMargin=8 * mm,
        title=f"List of samples {batch}".strip(),
        author="IgG Concentration Builder")

    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=12, spaceAfter=1)
    sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=8,
                         textColor=colors.HexColor("#444444"))
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=7.5, leading=10)
    foot = ParagraphStyle("foot", fontName="Helvetica-Oblique", fontSize=6.5,
                          textColor=colors.HexColor("#666666"))

    story = [
        Paragraph("List of samples &mdash; GBL-WS-031/07, step 1.3", h1),
        Paragraph("Companion sheet &mdash; attach to the worksheet. "
                  "The worksheet itself is the controlled record.", sub),
        Spacer(1, 4 * mm),
    ]

    # ---- identifying details --------------------------------------------
    std_names = ", ".join(sorted(stands)) or "-"
    blank_txt = ", ".join(f"{w} ({layout[w]})" for w in sorted(blanks, key=wkey)) or "-"
    head = [
        ["GA batch No.:", batch or "—",
         "Date:", date.strftime("%d.%m.%Y"),
         "Operator:", ""],
        ["Plasma standards:", std_names,
         "Blanks:", blank_txt,
         "Checked by:", ""],
    ]
    t = Table(head, colWidths=[26 * mm, 52 * mm, 20 * mm, 74 * mm, 22 * mm, 38 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8),
        ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 8),
        ("FONT", (4, 0), (4, -1), "Helvetica-Bold", 8),
        ("FONT", (1, 0), (1, 0), "Helvetica-Bold", 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        # ruled lines for the two fields the operator fills in by hand
        ("LINEBELOW", (5, 0), (5, 0), 0.5, colors.black),
        ("LINEBELOW", (5, 1), (5, 1), 0.5, colors.black),
    ]))
    story += [t, Spacer(1, 3 * mm)]

    # ---- worksheet and storage numbers ----------------------------------
    def val(k):
        return numbers.get(k) or "—"

    nums = [[
        Paragraph("<b>Worksheet numbers</b>", small),
        "",
        Paragraph("<b>Storage worksheet numbers</b> (GBL-WS-002)", small),
        "",
    ]]
    for (key, code, title), (skey, slabel) in zip(WORKSHEETS, STORAGE):
        nums.append([f"{code}  {title}", val(key), slabel, val(skey)])
    nums.append([
        "Sample reception worksheet no.", val("reception"),
        "Sample storage worksheet no.", val("sample_storage"),
    ])

    nt = Table(nums, colWidths=[74 * mm, 24 * mm, 60 * mm, 24 * mm])
    nt.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
        ("FONT", (1, 1), (1, -1), "Helvetica-Bold", 8),
        ("FONT", (3, 1), (3, -1), "Helvetica-Bold", 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#999999")),
        ("LINEAFTER", (1, 0), (1, -1), 0.5, colors.HexColor("#999999")),
        # the reception / sample-storage row predates this plate
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#555555")),
        ("LINEABOVE", (0, -1), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
    ]))
    story += [nt, Spacer(1, 3.5 * mm)]

    # ---- the 8 x 12 grid -------------------------------------------------
    ncols = max((int(w[1:]) for w in layout), default=12)
    ncols = max(ncols, 12)
    grid = [[""] + [str(c) for c in range(1, ncols + 1)]]
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
            key = grp if kind == "standard" else (kind if kind in
                                                 ("blank", "filler") else None)
            if key in CELL_COLOURS:
                style.append(("BACKGROUND", (ci, ri), (ci, ri), CELL_COLOURS[key]))
        grid.append(line)

    avail = landscape(A4)[0] - 20 * mm
    label_w = 7 * mm
    cell_w = (avail - label_w) / ncols
    g = Table(grid, colWidths=[label_w] + [cell_w] * ncols,
              rowHeights=[6 * mm] + [9 * mm] * 8)
    g.setStyle(TableStyle(style))
    story += [g, Spacer(1, 4 * mm)]

    # ---- legend and counts ----------------------------------------------
    def swatch(key, text):
        return (f'<font face="Helvetica" size="7" color="'
                f'{CELL_COLOURS[key].hexval()[2:]}">■</font> {text}')

    legend = ("&nbsp;&nbsp;&nbsp;".join([
        swatch("blank", "blank"),
        swatch("STAND_08", "STAND_08"),
        swatch("STAND_09", "STAND_09"),
        swatch("STAND_10", "STAND_10"),
    ] + ([swatch("filler", "HiDi")] if fillers else [])))
    story.append(Paragraph(legend.replace("color=\"", "color=\"#"), small))

    counts = (f"<b>{len(samples)}</b> sample wells "
              f"({len(donors)} donors &times; 3) &nbsp;&middot;&nbsp; "
              f"<b>{sum(len(v) for v in stands.values())}</b> standard wells "
              + " ".join(f"({g}: {len(w)})" for g, w in sorted(stands.items()))
              + f" &nbsp;&middot;&nbsp; <b>{len(blanks)}</b> blanks")
    if fillers:
        counts += f" &nbsp;&middot;&nbsp; <b>{len(fillers)}</b> HiDi wells"
    story.append(Paragraph(counts, small))

    story += [
        Spacer(1, 3 * mm),
        Paragraph(
            f"Generated {datetime.datetime.now():%d.%m.%Y %H:%M} from "
            f"{source_name or '(layout file)'}"
            + (f", sheet &lsquo;{sheet_name}&rsquo;" if sheet_name else "")
            + ". Positions are set by the randomization in that file &mdash; "
              "check this sheet against it before pipetting.", foot),
    ]

    doc.build(story)
    missing = [t for k, _, t in WORKSHEETS if not numbers.get(k)] + \
              [s for k, s in STORAGE if not numbers.get(k)]
    if missing:
        log("  !! no number entered for: " + ", ".join(missing))
    log(f"Wells on the grid : {len(layout)}")
    log(f"Samples           : {len(samples)}  ({len(donors)} donors)")
    log("Standards         : " + ", ".join(f"{g} ({len(w)})"
                                           for g, w in sorted(stands.items())))
    log("Blanks            : " + ", ".join(f"{w} {layout[w]}"
                                           for w in sorted(blanks, key=wkey)))
    if fillers:
        log(f"HiDi wells        : {len(fillers)}")
    log("")
    log(f"Saved: {out_path}")
    return out_path
