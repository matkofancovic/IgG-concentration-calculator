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
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics

import ws_sheets

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


def find_label(items, label, near_x=None, exact=False):
    """Where a labelled field's value should start: (x, y), or None.

    Matching ignores whitespace, because the worksheets' text layer breaks
    words apart ('Dry s ample storage worksheet no.').
    """
    target = squash(label)
    for y, parts in lines(items):
        joined = squash(" ".join(p[2] for p in parts))
        hit = (joined == target) if exact else (target in joined)
        if not hit:
            continue
        if near_x is not None and abs(parts[0][0] - near_x) > 60:
            continue
        x, size, text = parts[-1]
        try:
            w = pdfmetrics.stringWidth(text, FONT, size or 10)
        except Exception:
            w = len(text) * (size or 10) * 0.5
        return x + w + 6, y
    return None


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


# ------------------------------------------------------------------ filling

def _draw_grid(c, cols, rows, size_hdr, layout):
    """Sample names into the plate grid, shrunk per cell to fit."""
    gaps = [cols[i + 1] - cols[i] for i in range(len(cols) - 1)]
    cell_w = min(gaps) if gaps else 39.0
    for ci, cx in enumerate(cols, start=1):
        digits = len(str(ci))
        centre = cx + pdfmetrics.stringWidth(str(ci), FONT, size_hdr) / 2 \
            if digits else cx
        for r in ROWS:
            name = layout.get(f"{r}{ci}")
            if not name:
                continue
            size = 4.6
            while size > 2.4 and pdfmetrics.stringWidth(name, FONT, size) > cell_w - 3:
                size -= 0.1
            c.setFont(FONT, size)
            c.drawCentredString(centre, rows[r] - 1.0, name)


def fill_worksheet(pdf_path, out_path, spec, values, layout=None, log=print):
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

        if layout and spec.get("grid_page") == pno:
            if items is None:
                items = page_items(page)
            cols, rows, hdr = find_grid(items)
            if not cols:
                missing.append(f"p{pno + 1} sample grid")
            else:
                _draw_grid(c, cols, rows, hdr, layout)
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


def fill_all(sources, out_dir, layout, batch="", numbers=None, date=None,
             initials="", avg_conc=None, aliquot_ul=40.0, pages=None,
             log=print):
    """Fill each worksheet PDF given in `sources` -> {key: path}."""
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
        name = dict((k, n) for k, _, n in ws_sheets.WORKSHEETS)[key]
        stem = f"{batch} " if batch else ""
        out = os.path.join(out_dir, f"{stem}{name} worksheet.pdf")
        log(f"{name}:")
        fill_worksheet(src, out, spec, vals, layout, log=log)
        written.append(out)
    return written
