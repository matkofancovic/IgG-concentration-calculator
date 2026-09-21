#!/usr/bin/env python3
"""
Fill the GlycanAge worksheet PDFs.

Writes the values that can be derived - the 8x12 sample grid, GA batch,
worksheet and storage numbers, plate label, average dried IgG - onto a
*copy* of each worksheet, and leaves everything the operator has to
observe blank.

Fields are found at run time from the labels printed on the page, not from
hard-coded coordinates, so a revised worksheet still fills correctly as
long as the wording holds.  Anything that cannot be located is reported
rather than guessed at.
"""
import io
import os
import re
import datetime

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics

import ws_sheets
import layout_colours
import store

ROWS = "ABCDEFGH"
FONT = "Helvetica"
INK = (0.05, 0.15, 0.55)        # dark blue, so filled values read as added


def _grid_fonts():
    """-> (regular, bold) font names for the plate grid.

    Helvetica at 4pt in a 40x15pt cell is cramped and hard to read on paper,
    which is the whole complaint about the printed grid.  Segoe UI is on
    every Windows PC in the lab, is narrower per character at small sizes and
    has a taller x-height, so the same name fits with room to spare and still
    reads.  It is loaded from the system rather than bundled - no font is
    redistributed with the exe - and Helvetica stands in if it is not there.
    """
    try:
        from reportlab.pdfbase import pdfmetrics as _pm
        from reportlab.pdfbase.ttfonts import TTFont
        win = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        pairs = (("GridSans", "segoeui.ttf"), ("GridSans-Bold", "seguisb.ttf"))
        for name, fn in pairs:
            if name not in _pm.getRegisteredFontNames():
                _pm.registerFont(TTFont(name, os.path.join(win, fn)))
        return "GridSans", "GridSans-Bold"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


GRID_FONT, GRID_FONT_BOLD = _grid_fonts()

# where the blank worksheets live, and the document code of each
WS_DIR = r"\\10.70.119.100\Glikobiologija\SOPs and WS\WSs"
WS_CODES = {"isolation": "GBL-WS-031",
            "deglyco":   "GBL-WS-029",
            "cleanup":   "GBL-WS-030",
            "storage":   "GBL-WS-002"}

# One GBL-WS-002 per storage number a plate takes.  The sample type and the
# packing are fixed by what is being stored, so they are ticked; the freezer
# and drawer are the operator's choice at the freezer and are left blank.
#
# The last field is the day the material actually goes into storage, which is
# not always day 1: the eluate and the dried IgG are both put away at the end
# of the isolation, but the APTS-labelled glycans do not exist until the
# clean-up on day 3.
#   key         what it is on the sheet   Sample type   Packed in   stored on
STORAGE_KINDS = {
    "eluate":     ("IgG eluate", "IgG", "1 ml collection plat", "isolation"),
    "dry_eluate": ("Dry IgG eluate", "IgG", "PCR plate", "isolation"),
    "apts":       ("APTS labelled IgG N-glycans", "Labeled glycans",
                   "Round collection plate", "cleanup"),
}


def working_days(start, n):
    """-> n dates beginning at `start`, skipping Saturdays and Sundays.

    A plate is three days of bench work - isolation, deglycosylation, clean
    up - and each worksheet carries the date it was actually done.  Starting
    an isolation on a Friday puts the other two on the Monday and Tuesday,
    not on the weekend.
    """
    out, day = [], start
    while len(out) < n:
        while day.weekday() >= 5:            # 5 = Saturday, 6 = Sunday
            day += datetime.timedelta(days=1)
        out.append(day)
        day += datetime.timedelta(days=1)
    return out


class FillError(Exception):
    pass


def discover(folder=None):
    """-> {key: newest blank worksheet PDF} found in `folder`.

    Worksheets are versioned in the file name ('GBL-WS-031-07 ...'), so the
    highest revision wins and a new one is picked up without a code change.
    """
    folder = folder or WS_DIR
    try:
        names = os.listdir(folder)
    except OSError as e:
        raise FillError(f"Cannot read the worksheets folder:\n{folder}\n\n{e}")
    found = {}
    for key, code in WS_CODES.items():
        best = None
        for n in names:
            if not n.lower().endswith(".pdf") or n.startswith("~$"):
                continue
            m = re.match(re.escape(code) + r"[-_ ]?(\d+)", n, re.I)
            if m:
                ver = int(m.group(1))
                if best is None or ver > best[0]:
                    best = (ver, os.path.join(folder, n))
        if best:
            found[key] = best[1]
    return found


# --------------------------------------------------------------- extraction

def page_items(page):
    """-> [(x, y, size, text)] in page points."""
    items = []

    def visitor(text, cm, tm, font_dict, font_size, _i=items):
        t = text.strip()
        if not t:
            return
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        size = (font_size or 1) * tm[3] * cm[3]
        _i.append((x, y, size, t))

    page.extract_text(visitor_text=visitor)
    return items


def squash(s):
    return re.sub(r"\s+", "", s).lower()


def lines(items):
    """Group runs onto shared baselines -> [(y, [(x, size, text), ...])]."""
    buckets = {}
    for x, y, size, t in items:
        buckets.setdefault(round(y), []).append((x, size, t))
    return [(y, sorted(v)) for y, v in sorted(buckets.items(), reverse=True)]


def _after(part):
    """x just past a text run."""
    x, size, text = part
    try:
        w = pdfmetrics.stringWidth(text, FONT, size or 10)
    except Exception:
        w = len(text) * (size or 10) * 0.5
    return x + w + 6


def find_label(items, label, near_x=None, exact=False, after=False):
    """Where a labelled field's value should start: (x, y), or None.

    Matching ignores whitespace, because the worksheets' text layer breaks
    words apart ('Dry s ample storage worksheet no.').

    By default the value goes after the *last* run on the line, which is
    right for a line holding one field.  `after=True` puts it immediately
    after the label itself instead - needed where several fields share a
    baseline, as in 'Enzyme LOT:  Incubation start:  Incubation end:'.
    """
    target = squash(label)
    for y, parts in lines(items):
        joined = squash(" ".join(p[2] for p in parts))
        hit = (joined == target) if exact else (target in joined)
        if not hit:
            continue
        if near_x is not None and abs(parts[0][0] - near_x) > 60:
            continue
        if after:
            acc = ""
            for p in parts:
                acc += squash(p[2])
                if target in acc:
                    return _after(p), y
        return _after(parts[-1]), y
    return None


def find_label_box(items, rects, label, near_x=None):
    """-> (x, y) just inside the answer box that follows `label`, or None.

    Some fields are a short ruled box with the rest of the line blank.  The
    width of the printed label cannot be measured reliably (the worksheet's
    font is not one reportlab knows), so rather than guess where the label
    ends, take the first drawn rectangle to its right on the same baseline
    and write inside that.
    """
    target = squash(label)
    for y, parts in lines(items):
        joined = squash(" ".join(p[2] for p in parts))
        if target not in joined:
            continue
        if near_x is not None and abs(parts[0][0] - near_x) > 60:
            continue
        left = parts[0][0]
        best = None
        for (x0, y0, w, h) in rects:
            if x0 <= left or not (y0 - 3 <= y <= y0 + h + 1):
                continue
            if best is None or x0 < best[0]:
                best = (x0, y0, w, h)
        if best:
            return best[0] + 4, y
    return None


def find_label_box_left(items, rects, label):
    """-> (x, y) inside the answer box drawn to the LEFT of `label`, or None.

    GBL-WS-002 puts the box before the wording - 'box  Sample reception
    worksheet no.' - where every other worksheet puts it after.  Writing to
    the right of the label there lands the value in open space beside an
    empty box, which looks like nobody filled it in.
    """
    for y, parts in lines(items):
        joined = squash(" ".join(p[2] for p in parts))
        if squash(label) not in joined:
            continue
        left = parts[0][0]
        best = None
        for (bx, by, bw, bh) in rects:
            if bx + bw > left + 2 or bw < 20:
                continue
            if not (by - 4 <= y <= by + bh + 2):
                continue
            if best is None or bx > best[0]:
                best = (bx, by, bw, bh)
        if best:
            return best[0] + 5, y
    return None


def find_tickbox(items, rects, option):
    """-> (x, y, w, h) of the tickbox belonging to `option`, or None.

    On GBL-WS-002 the options sit in four columns with their box drawn just
    to the left of the wording, so the box is found from the wording rather
    than from a coordinate - a re-laid-out revision still ticks correctly.
    """
    target = squash(option)
    for y, parts in lines(items):
        for x, size, text in parts:
            if squash(text) != target:
                continue
            best = None
            for (bx, by, bw, bh) in rects:
                if bw > 16 or bh > 18 or bx >= x:
                    continue
                if not (by - 3 <= y <= by + bh + 2):
                    continue
                if x - (bx + bw) > 30:       # too far left to belong to it
                    continue
                if best is None or bx > best[0]:
                    best = (bx, by, bw, bh)
            if best:
                return best
    return None


def draw_tick(c, box):
    """A tick inside `box`, in the same ink as everything else added."""
    x, y, w, h = box
    c.setLineWidth(1.4)
    c.setStrokeColorRGB(*INK)
    c.line(x + w * 0.22, y + h * 0.50, x + w * 0.44, y + h * 0.26)
    c.line(x + w * 0.44, y + h * 0.26, x + w * 0.80, y + h * 0.76)


def find_table_cell(items, row_label, col_label):
    """-> (x, y) where `row_label`'s row meets `col_label`'s column, or None.

    Used for the 'Solution | Date of preparation | Initials' tables, whose
    rows are named after the solution itself, so a reordered or extended
    table still fills correctly.

    Row names overlap - '1x PBS' is a prefix of '1xPBS (0,25M NaCl)', and
    '80 % ACN' of '80% ACN / 100mM TEA' - so an exact match always beats a
    prefix match.  Matching on the prefix alone silently writes the date on
    the wrong row, which is how this was caught.
    """
    col_x, header_y = None, None
    c_target = squash(col_label)
    for y, parts in lines(items):
        joined = squash(" ".join(p[2] for p in parts))
        if c_target in joined:
            acc = ""
            for p in parts:
                acc += squash(p[2])
                if c_target in acc:
                    col_x, header_y = p[0], y
                    break
            if col_x is not None:
                break
    if col_x is None:
        return None

    r_target = squash(row_label)
    exact = prefix = None
    for y, parts in lines(items):
        if y >= header_y:
            continue
        joined = squash(" ".join(p[2] for p in parts))
        if joined == r_target and exact is None:
            exact = y
        elif joined.startswith(r_target) and prefix is None:
            prefix = y
    row_y = exact if exact is not None else prefix
    return None if row_y is None else (col_x, row_y)


def find_grid(items):
    """-> ([12 column x], {row letter: y}, header size) or (None, None, None)."""
    letters = [(x, y, s, t) for x, y, s, t in items if t in ROWS]
    rows = None
    for cand in {round(x) for x, _, _, _ in letters}:
        col = [(x, y, t) for x, y, s, t in letters if abs(x - cand) < 6]
        seen = {t: y for x, y, t in col}
        if all(r in seen for r in ROWS):
            ys = [seen[r] for r in ROWS]
            gaps = [ys[i] - ys[i + 1] for i in range(7)]
            if all(g > 0 for g in gaps) and max(gaps) - min(gaps) < 3:
                rows = seen
                break
    if not rows:
        return None, None, None
    top = rows["A"]
    nums = [(x, y, s, t) for x, y, s, t in items
            if t.isdigit() and 1 <= int(t) <= 12 and 0 < y - top < 30]
    by_val, size = {}, 9.0
    for x, y, s, t in sorted(nums, key=lambda i: i[0]):
        if int(t) not in by_val:
            by_val[int(t)] = x
            size = s or size
    if len(by_val) < 11:
        return None, None, None
    return [by_val[i] for i in sorted(by_val)], rows, size


# ------------------------------------------------------- grid cell geometry

def page_rects(page, reader):
    """-> [(x, y, w, h)] of the page's vector rectangles, in page points.

    The worksheet tables are drawn as filled/stroked rectangles, so the real
    cell boxes are already on the page - far better than guessing a box from
    where the row letter sits.  Rectangles are given in the coordinate space
    current when they were emitted, so `cm` has to be tracked to place them.
    """
    try:
        cs = ContentStream(page.get_contents(), reader)
    except Exception:
        return []
    out, ctm, stack = [], [1, 0, 0, 1, 0, 0], []
    for operands, op in cs.operations:
        o = op.decode() if isinstance(op, bytes) else str(op)
        if o == "q":
            stack.append(list(ctm))
        elif o == "Q" and stack:
            ctm = stack.pop()
        elif o == "cm" and len(operands) == 6:
            try:
                a, b, c_, d, e, f = [float(v) for v in operands]
            except Exception:
                continue
            A, B, C, D, E, F = ctm
            ctm = [a * A + b * C, a * B + b * D, c_ * A + d * C,
                   c_ * B + d * D, e * A + f * C + E, e * B + f * D + F]
        elif o == "re" and len(operands) == 4:
            try:
                x, y, w, h = [float(v) for v in operands]
            except Exception:
                continue
            A, B, C, D, E, F = ctm
            X, Y, W, H = x * A + y * C + E, x * B + y * D + F, w * A, h * D
            if 5 < abs(W) < 90 and 4 < abs(H) < 60:
                out.append((min(X, X + W), min(Y, Y + H), abs(W), abs(H)))
    return out


def cell_boxes(cols, rows, rects):
    """-> {well: (x, y, w, h)} by snapping the text grid onto the vector cells.

    The columns are not all the same width, so each well is matched to the
    smallest rectangle that contains its column x and row baseline.  A well
    with no rectangle is left out and simply goes uncoloured.
    """
    boxes = {}
    for ci, cx in enumerate(cols, start=1):
        for r in ROWS:
            ry = rows[r]
            best = None
            for (x0, y0, w, h) in rects:
                if x0 - 2 <= cx <= x0 + w + 2 and y0 - 3 <= ry <= y0 + h + 1:
                    if best is None or w * h < best[2] * best[3]:
                        best = (x0, y0, w, h)
            if best:
                boxes[f"{r}{ci}"] = best
    return boxes


# ------------------------------------------------------------------ filling

def _draw_grid(c, cols, rows, size_hdr, layout, colours=None, boxes=None):
    """Sample names into the plate grid.

    `colours` paints each well the colour the Pippeting List gives it, so the
    printed grid reads like the Excel plate map.

    Each name is set in the largest size that still leaves a real margin
    inside its cell, and is centred in the cell box both ways rather than
    dropped on the row-letter baseline - the old version ran names hard into
    the cell walls and sat them low, which is what made the printed grid look
    cramped.  Standards and blanks are set bold so the plate's landmarks read
    at a glance.
    """
    colours = colours or {}
    boxes = boxes or {}
    gaps = [cols[i + 1] - cols[i] for i in range(len(cols) - 1)]
    cell_w = min(gaps) if gaps else 39.0

    ascent = pdfmetrics.getAscent(GRID_FONT) / 1000.0
    descent = pdfmetrics.getDescent(GRID_FONT) / 1000.0     # negative

    def font_for(name):
        landmark = name.startswith("STAND_") or name.lower().startswith("blank")
        return GRID_FONT_BOLD if landmark else GRID_FONT

    # One size for the whole grid.  Sizing each cell to its own width makes
    # the columns ragged, because the worksheet's columns are not all the
    # same width - so take the largest size that fits every name in its own
    # cell and use it throughout.
    size = 5.4
    while size > 3.0:
        if all(pdfmetrics.stringWidth(n, font_for(n), size)
               <= (boxes[w][2] if w in boxes else cell_w) - 4.0
               for w, n in layout.items() if n and w in boxes):
            break
        size -= 0.1

    for ci, cx in enumerate(cols, start=1):
        for r in ROWS:
            well = f"{r}{ci}"
            name = layout.get(well)
            rgb = colours.get(well)
            box = boxes.get(well)

            if rgb and box:
                x0, y0, w, h = box
                c.setFillColorRGB(*layout_colours.to_float(rgb))
                c.rect(x0 + 0.35, y0 + 0.35, w - 0.7, h - 0.7, stroke=0, fill=1)

            if not name:
                continue

            font = font_for(name)
            if box:
                x0, y0, w, h = box
                mid_x = x0 + w / 2.0
                # centre the glyph body, not the em box
                base_y = y0 + (h - (ascent - descent) * size) / 2.0 - descent * size
            else:
                mid_x = cx + pdfmetrics.stringWidth(str(ci), FONT, size_hdr) / 2
                base_y = rows[r] - 1.0

            c.setFillColorRGB(*(layout_colours.readable_ink(rgb) if rgb else INK))
            c.setFont(font, size)
            c.drawCentredString(mid_x, base_y, name)

    c.setFillColorRGB(*INK)


def fill_worksheet(pdf_path, out_path, spec, values, layout=None, colours=None,
                   log=print):
    """Write `values` onto a copy of `pdf_path` using `spec`.

    spec: {page_index: [(label, value_key, near_x or None), ...],
           "grid_page": index}
    """
    try:
        reader = PdfReader(pdf_path)
    except Exception as e:
        raise FillError(f"Cannot read {os.path.basename(pdf_path)}:\n{e}")

    writer = PdfWriter()
    missing, placed = [], 0

    for pno, page in enumerate(reader.pages):
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(w, h))
        c.setFillColorRGB(*INK)
        drew = False
        items = None

        for label, key, near_x in spec.get("fields", {}).get(pno, []):
            val = values.get(key)
            if not val:
                continue
            if items is None:
                items = page_items(page)
            spot = find_label(items, label, near_x)
            if spot is None:
                missing.append(f"p{pno + 1} {label!r}")
                continue
            x, y = spot
            c.setFont(FONT, 9)
            c.drawString(x, y, str(val))
            placed += 1
            drew = True

        for label, key, near_x, after in spec.get("consumables", {}).get(pno, []):
            val = values.get(key)
            if not val:
                continue
            if items is None:
                items = page_items(page)
            if after == "box":
                spot = find_label_box(items, page_rects(page, reader), label, near_x)
            elif after == "box_left":
                spot = find_label_box_left(items, page_rects(page, reader), label)
            else:
                spot = find_label(items, label, near_x, after=after)
            if spot is None:
                missing.append(f"p{pno + 1} {label!r}")
                continue
            x, y = spot
            c.setFont(FONT, 9)
            c.drawString(x, y, str(val))
            placed += 1
            drew = True

        for row_label, col_label, val in spec.get("table", {}).get(pno, []):
            if not val:
                continue
            if items is None:
                items = page_items(page)
            spot = find_table_cell(items, row_label, col_label)
            if spot is None:
                missing.append(f"p{pno + 1} {row_label!r} / {col_label!r}")
                continue
            x, y = spot
            c.setFont(FONT, 8)
            c.drawString(x, y, str(val))
            placed += 1
            drew = True

        for option in spec.get("ticks", {}).get(pno, []):
            if items is None:
                items = page_items(page)
            box = find_tickbox(items, page_rects(page, reader), option)
            if box is None:
                missing.append(f"p{pno + 1} tickbox {option!r}")
                continue
            draw_tick(c, box)
            c.setFillColorRGB(*INK)
            placed += 1
            drew = True

        if layout and spec.get("grid_page") == pno:
            if items is None:
                items = page_items(page)
            cols, rows, hdr = find_grid(items)
            if not cols:
                missing.append(f"p{pno + 1} sample grid")
            else:
                boxes = cell_boxes(cols, rows, page_rects(page, reader)) \
                    if colours else {}
                if colours and not boxes:
                    log("  !! could not locate the grid cell boxes - "
                        "the sample names are written without the layout colours")
                _draw_grid(c, cols, rows, hdr, layout, colours, boxes)
                placed += sum(1 for k in layout if re.fullmatch(r"[A-H](?:[1-9]|1[0-2])", k))
                drew = True

        c.save()
        if drew:
            buf.seek(0)
            page.merge_page(PdfReader(buf).pages[0])
        writer.add_page(page)

    try:
        with open(out_path, "wb") as fh:
            writer.write(fh)
    except PermissionError:
        raise FillError(f"Cannot write {os.path.basename(out_path)}.\n\n"
                        "It is probably open - close it and try again.")

    log(f"  {os.path.basename(out_path)}: {placed} values placed")
    for m in missing:
        log(f"  !! could not find {m}")
    return out_path


# -------------------------------------------------------------- worksheets

# The consumable LOT / plate-number fields.  Each is (page, label, value key,
# near_x, after) - `after` places the value right behind the label where the
# line carries more than one field.
CONSUMABLES = {
    "isolation": [
        (2, "wwPTFE plate LOT no.", "wwptfe_lot", None, False),
        (2, "50 µl CV Protein G monolithic plate", "proteing_no", None, False),
        (2, "How many times has this Protein G plate been used?",
         "proteing_uses", None, "box"),
    ],
    "deglyco": [
        (1, "Enzyme LOT:", "enzyme_lot_30", None, True),
        (1, "Enzyme LOT /", "enzyme_lot_50", None, True),
        (1, "Date of reconstitution:", "enzyme_reconstituted", None, True),
    ],
    "cleanup": [
        (0, "LOT no.:", "wwptfe_lot", None, False),
    ],
}

# The 'Buffer / Solution | Date of preparation | Initials' tables.  Rows are
# found by the solution's printed name, so the store keys read the same way.
# Which page the table is on and what its first column is called.  The row
# names come from store.SOLUTIONS so the library and the printed table can
# never drift apart - they did once, and the date went on the wrong row.
SOLUTION_TABLES = {
    "isolation": (4, "Buffer"),
    "deglyco":   (2, "Solution"),
    "cleanup":   (2, "Solution"),
}


def specs():
    """Where each value goes, keyed by the label printed on the page."""
    return {
        "isolation": {
            "grid_page": 2,                      # page 3
            "fields": {
                0: [("No.", "isolation", 472),
                    ("Date:", "date", 447),
                    ("Sample reception worksheet no.", "reception", None),
                    ("Sample storage worksheet no.", "sample_storage", None),
                    ("GA batch No.:", "batch", None)],
                3: [("1 mL collection plate label:", "plate_label", None),
                    ("Dry sample storage worksheet no.", "dry_eluate", None),
                    ("IgG eluate storage worksheet no.", "eluate", None)],
            },
        },
        "deglyco": {
            "grid_page": 0,
            "fields": {
                0: [("No.", "deglyco", 473),
                    ("Date:", "date", 447),
                    ("IgG isolation worksheet no.", "isolation", None),
                    ("Dry sample storage worksheet no.", "dry_eluate", None),
                    ("GA batch No.:", "batch", None),
                    ("Average amount of dried IgG", "dried_igg", None)],
            },
        },
        "cleanup": {
            "grid_page": 1,                      # page 2
            "fields": {
                0: [("No.", "cleanup", 473),
                    ("Date:", "date", 447),
                    ("In solution deglycosylation and APTS labelling worksheet no.",
                     "deglyco", None),
                    ("GA batch No.:", "batch", None)],
                2: [("APTS IgG N-glycan storage worksheet no.:", "apts", None)],
            },
        },
    }


def values_for(key, batch, numbers, date, initials, avg_conc, aliquot_ul):
    """The values that go on one worksheet."""
    v = dict(numbers)
    v["batch"] = batch
    v["date"] = date.strftime("%d.%m.%Y")
    if key == "isolation":
        v["plate_label"] = ws_sheets.plate_label(
            batch, numbers.get("eluate"), date, initials)
    if key == "deglyco" and avg_conc and avg_conc[0] is not None:
        dbs, std = avg_conc
        v["dried_igg"] = (f"{dbs * aliquot_ul:.1f} / {std * aliquot_ul:.1f}"
                          if std is not None else f"{dbs * aliquot_ul:.1f}")
    return v


def _consumable_spec(key):
    """-> {page: [(label, value key, near_x, after)]} for one worksheet."""
    out = {}
    for page, label, vkey, near_x, after in CONSUMABLES.get(key, []):
        out.setdefault(page, []).append((label, vkey, near_x, after))
    return out


def _solution_spec(key, solutions, initials):
    """-> {page: [(row label, column label, value)]} for the solutions table.

    `solutions` is {solution name: preparation date}.  A solution with no
    date recorded is skipped, so the operator writes that row in by hand -
    which is exactly the fallback the analyst asked for.
    """
    if not solutions or key not in SOLUTION_TABLES:
        return {}
    page, col_head = SOLUTION_TABLES[key]
    rows = store.SOLUTIONS.get(key, [])
    out = []
    for row in rows:
        date = solutions.get(row)
        if not date:
            continue
        out.append((row, "Date of preparation", date))
        if initials:
            out.append((row, "Initials", initials))
    return {page: out} if out else {}


def fill_storage_sheets(source, out_dir, layout, batch="", numbers=None,
                        date=None, labels=None, colours=None, kinds=None,
                        dates=None, log=print):
    """One filled GBL-WS-002 per storage number the plate took.

    Fills what follows from the run: the storage number, the date, which IgG
    isolation worksheet it belongs to, the sample reception number, and the
    coloured 8x12 sample list.  The sample type and the packing are ticked
    because they follow from what is being stored.

    Left blank on purpose: the fridge/freezer letter and drawer number, which
    are chosen standing at the freezer and are not knowable here.
    """
    numbers = numbers or {}
    labels = labels or {}
    date = date or datetime.date.today()
    written = []

    for key in (kinds or STORAGE_KINDS):
        no = numbers.get(key)
        if not no:
            continue
        what, sample_type, packed_in, stored_on = STORAGE_KINDS[key]
        when = (dates or {}).get(stored_on) or date
        spec = {
            "grid_page": 0,
            "fields": {0: [("No.", "no", None),
                           ("Date:", "date", None),
                           ("Sample label", "label", None)]},
            # these two have their box drawn before the wording, not after
            "consumables": {0: [
                ("Lab worksheet no. (if applicable)", "isolation", None, "box_left"),
                ("Sample reception worksheet no. (if applicable)", "reception",
                 None, "box_left"),
            ]},
            "ticks": {0: [sample_type, packed_in]},
        }
        vals = {"no": no, "date": when.strftime("%d.%m.%Y"),
                "isolation": numbers.get("isolation", ""),
                "reception": numbers.get("reception", ""),
                "label": labels.get(key, "")}
        stem = f"{batch} " if batch else ""
        out = os.path.join(out_dir, f"{stem}storage {no} - {what}.pdf")
        log(f"Sample storage worksheet - {what}:")
        fill_worksheet(source, out, spec, vals, layout, colours, log=log)
        written.append(out)
    return written


def fill_all(sources, out_dir, layout, batch="", numbers=None, date=None,
             initials="", avg_conc=None, aliquot_ul=40.0, pages=None,
             colours=None, consumables=None, solutions=None, dates=None,
             log=print):
    """Fill each worksheet PDF given in `sources` -> [path]."""
    numbers = numbers or {}
    date = date or datetime.date.today()
    # Only the three process worksheets have a spec.  discover() also finds
    # GBL-WS-002, which is filled separately by fill_storage_sheets(), so it
    # must never fall into this loop - it did, and took the CLI down with a
    # KeyError the moment --pages was left off.
    wanted = set(pages or sources) & set(specs())
    written = []
    for key, src in sources.items():
        if key not in wanted or not src:
            continue
        spec = specs()[key]
        when = (dates or {}).get(key) or date
        vals = values_for(key, batch, numbers, when, initials,
                          avg_conc, aliquot_ul)
        vals.update({k: v for k, v in (consumables or {}).items() if v})
        spec["consumables"] = _consumable_spec(key)
        spec["table"] = _solution_spec(key, solutions, initials)
        name = dict((k, n) for k, _, n in ws_sheets.WORKSHEETS)[key]
        stem = f"{batch} " if batch else ""
        out = os.path.join(out_dir, f"{stem}{name} worksheet.pdf")
        log(f"{name}:")
        fill_worksheet(src, out, spec, vals, layout, colours, log=log)
        written.append(out)
    return written
