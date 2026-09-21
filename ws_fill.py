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

ROWS = "ABCDEFGH"
FONT = "Helvetica"
INK = (0.05, 0.15, 0.55)        # dark blue, so filled values read as added

# where the blank worksheets live, and the document code of each
WS_DIR = r"\\10.70.119.100\Glikobiologija\SOPs and WS\WSs"
WS_CODES = {"isolation": "GBL-WS-031",
            "deglyco":   "GBL-WS-029",
            "cleanup":   "GBL-WS-030"}


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
    """Sample names into the plate grid, shrunk per cell to fit.

    `colours` paints each well the colour the Pippeting List gives it, so the
    printed grid reads like the Excel plate map.  The fill is inset by a hair
    to leave the worksheet's own printed cell borders showing, and the text
    ink flips to white on the dark fills.
    """
    colours = colours or {}
    boxes = boxes or {}
    gaps = [cols[i + 1] - cols[i] for i in range(len(cols) - 1)]
    cell_w = min(gaps) if gaps else 39.0

    for ci, cx in enumerate(cols, start=1):
        digits = len(str(ci))
        centre = cx + pdfmetrics.stringWidth(str(ci), FONT, size_hdr) / 2 \
            if digits else cx
        for r in ROWS:
            well = f"{r}{ci}"
            name = layout.get(well)
            rgb = colours.get(well)
            box = boxes.get(well)

            if rgb and box:
                x0, y0, w, h = box
                c.setFillColorRGB(*layout_colours.to_float(rgb))
                c.rect(x0 + 0.6, y0 + 0.6, w - 1.2, h - 1.2, stroke=0, fill=1)

            if not name:
                continue
            c.setFillColorRGB(*(layout_colours.readable_ink(rgb) if rgb else INK))
            width = (box[2] if box else cell_w)
            size = 4.6
            while size > 2.4 and pdfmetrics.stringWidth(name, FONT, size) > width - 3:
                size -= 0.1
            c.setFont(FONT, size)
            c.drawCentredString(centre, rows[r] - 1.0, name)

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
SOLUTION_TABLES = {
    "isolation": (4, "Buffer", ["1x PBS", "1xPBS (0,25M NaCl)", "10x PBS",
                                "0,1M FA", "1M AmBic", "Storage buffer"]),
    "deglyco":   (2, "Solution", ["1,66x PBS", "0,5% SDS", "4% Igepal",
                                  "5x PBS", "1,2M 2-PB", "30mM APTS"]),
    "cleanup":   (2, "Solution", ["Biogel P10 slurry", "80 % ACN",
                                  "80% ACN / 100mM TEA", "HiDi Formamide"]),
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
    page, col_head, rows = SOLUTION_TABLES[key]
    out = []
    for row in rows:
        date = solutions.get(row)
        if not date:
            continue
        out.append((row, "Date of preparation", date))
        if initials:
            out.append((row, "Initials", initials))
    return {page: out} if out else {}


def fill_all(sources, out_dir, layout, batch="", numbers=None, date=None,
             initials="", avg_conc=None, aliquot_ul=40.0, pages=None,
             colours=None, consumables=None, solutions=None, log=print):
    """Fill each worksheet PDF given in `sources` -> [path]."""
    numbers = numbers or {}
    date = date or datetime.date.today()
    wanted = set(pages or sources)
    written = []
    for key, src in sources.items():
        if key not in wanted or not src:
            continue
        spec = specs()[key]
        vals = values_for(key, batch, numbers, date, initials,
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
