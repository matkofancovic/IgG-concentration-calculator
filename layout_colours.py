#!/usr/bin/env python3
"""
The colours the Pippeting List itself uses for the plate map.

The analyst already reads the plate as a coloured picture in Excel - green
standards here, the red blank there.  Reproducing *those* colours on the
printed worksheet means the paper and the screen look like the same plate,
which is the whole point of printing it.

So the colours are read out of the workbook rather than hard-coded.  If
whoever maintains the Pippeting List template restyles it, the worksheets
follow with no change here.  The known GlycanAge palette is:

    FFFFFF  white       real sample
    00CC00  green       STAND_08
    3399FF  blue        STAND_09
    FFD700  gold        STAND_10
    FF3333  red         Blank DBS / Blank PBS
    D3D3D3  grey        HiDi and other filler

but nothing below depends on that list - it is whatever the cells say.
"""
import openpyxl

ROWS = "ABCDEFGH"

# Excel's own "no fill" and plain white.  Painting white over the worksheet
# would hide its printed cell borders and gains nothing, so it is dropped.
_BLANKS = {None, "", "00000000", "FFFFFFFF", "FFFFFF"}


def _rgb(cell):
    """-> 'RRGGBB' for a solid-filled cell, or None."""
    fill = cell.fill
    if fill is None or fill.patternType != "solid":
        return None
    fg = fill.fgColor
    if fg is None:
        return None
    rgb = getattr(fg, "rgb", None)
    if not isinstance(rgb, str):
        return None                      # theme/indexed colour - not resolvable
    rgb = rgb.upper()
    if rgb in _BLANKS:
        return None
    return rgb[-6:]                      # drop the alpha byte


def read_colours(path, sheet=None):
    """-> {well: 'RRGGBB'} for the wells the layout gives a fill colour.

    Reads the same grid shape `read_layout` does: a header row carrying the
    column numbers 1..12, then eight rows labelled A..H.  `Plate_layouts`
    repeats that block once per pipetting step; the blocks agree, so a later
    one simply overwrites an earlier one.
    """
    try:
        wb = openpyxl.load_workbook(path)        # styles need data_only=False
    except Exception:
        return {}
    if sheet and sheet in wb.sheetnames:
        names = [sheet]
    else:
        names = [s for s in ("Plate_layouts", "List 1") if s in wb.sheetnames]
    if not names:
        return {}

    ws = wb[names[0]]
    colours, cols = {}, None
    for row in ws.iter_rows():
        vals = [c.value for c in row]
        numbered = {j: int(str(v).strip()) for j, v in enumerate(vals)
                    if v is not None and str(v).strip().isdigit()}
        label = str(vals[0]).strip() if vals and vals[0] is not None else ""
        if len(numbered) >= 8 and label == "":
            cols = numbered
            continue
        if cols is None or label not in ROWS:
            continue
        for j, n in cols.items():
            if j >= len(row):
                continue
            rgb = _rgb(row[j])
            if rgb:
                colours[f"{label}{n}"] = rgb
    return colours


def to_float(rgb):
    """'RRGGBB' -> (r, g, b) in 0..1."""
    return tuple(int(rgb[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def readable_ink(rgb):
    """Black or white text, whichever stays legible on `rgb`."""
    r, g, b = to_float(rgb)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0) if luminance > 0.55 else (1, 1, 1)
