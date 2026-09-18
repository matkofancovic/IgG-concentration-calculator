# IgG Concentration Builder

Paperwork for a GlycanAge plate's day 1 - IgG isolation and the concentration
measurement that follows it. Two tabs, one plate layout file behind both.

| Tab | Produces |
|---|---|
| **IgG concentrations** | the concentration workbook: **Well / Sample ID / conc. / units**, colour-coded, with the DBS and standard averages |
| **List of samples (WS-031)** | a printable companion sheet for GBL-WS-031/07 step 1.3 - the filled 8x12 plate grid and the worksheet numbers taken for the plate |

Replaces doing both by hand.

## What it does

Takes two files:

| Input | What it is |
|---|---|
| `<plate>.txt` | NanoDrop export from the `concentrations` folder |
| `<plate> Pippeting List.xlsx` | plate layout, sheet `Plate_layouts` |

and writes `<plate>.xlsx` with one row per well, the sample name filled in from
the layout, and an average block:

- `DBS` — mean of the real samples (standards, blanks and empty wells excluded)
- `STAND_08`, `STAND_09`, `STAND_10` — mean of each set of 4 replicates

Averages are written as live `=AVERAGE()` formulas, not pasted numbers, so the
workbook stays auditable.

### Colour coding

| Colour | Meaning |
|---|---|
| 🔴 red | blanks |
| 🟢 green | STAND_08 |
| 🔵 blue | STAND_09 |
| 🟡 yellow | STAND_10 |

Wells are classified from their **names** in the layout, not their positions —
the plate is randomized per run, so position carries no information:

- `STAND_08_1` … → standard, grouped by the `STAND_08` part
- `Blank PBS`, `Blank DBS` → blank
- `HiDi` → filler, skipped
- anything else → a real sample
- measured but absent from the layout → written with no Sample ID, excluded
  from the averages

## Things it handles

These all come from real exports and are each reported in the run log:

- **Croatian decimal comma and scientific notation** — `0,2278`, `-8,307E-4`
- **A well measured twice.** On plate 999 the whole of column 2 was read at
  13:24 (all ≈ 0, a failed read) and again at 13:25. The later read wins.
- **Two plates in one `.txt`.** The `995-996` export holds both plates; the
  one matching the layout is selected automatically.

## The layout check

Before writing anything it verifies the layout actually describes the plate
that was measured:

- every standard group has 4 replicates
- every blank reads below 0.05 mg/ml
- every standard reads between 0.05 and 1.0 mg/ml

This exists because plate 999 has **two** layout files that disagree on 81 of
86 wells. The stale one (`999-GA-202609.xlsx` sheet `List 1`) claims `F4` and
`E8` are the blanks — they measured 0.120 and 0.189 mg/ml, plainly real IgG.
The correct one (the Pippeting List) puts the blanks at `F9` and `D11`, which
measured -0.021 and 0.004. Using the wrong file mislabels almost every sample
on the plate, and nothing downstream would notice.

If the check fails the workbook is **not** written and the report says why.
Untick *Stop if the layout does not match the readings* to override.

## Running it

**Colleagues:** double-click the desktop shortcut to
`Run IgG Concentration Builder.bat`. That's all — it keeps itself up to date.

**From source:**

```
pip install -r requirements.txt
python igg_conc_gui.py
```

**Batch / scripted:**

```
python igg_conc_gui.py <nanodrop.txt> <layout.xlsx> <output.xlsx> [--lenient]
```

The exe accepts the same arguments.

## Releasing a new version

1. Bump `__version__` in `igg_conc_gui.py` (it shows in the title bar and the
   report — it's how anyone tells which build they're on).
2. Run `build.bat`.
3. Copy `dist\IgG Concentration Builder.exe` over the copy in the share folder.
4. Commit and tag.

Every PC picks the new version up the next time someone launches it. Because
the launcher copies to `%LOCALAPPDATA%` and runs from there, you can replace
the share copy even while colleagues have the app open.

## The worksheet companion sheets

All three worksheets are flat PDFs with no form fields, and controlled
documents, so nothing writes to them. The sheets print separately and get
attached. `GBL-WS-030/04` step 3 says so outright: *"write down the correct
sample list in the provided table or paste printed table with sample name"*.

One page per worksheet, each carrying the filled 8x12 grid plus the numbers
**that** worksheet asks for:

| Page | Quotes | Also filled |
|---|---|---|
| `GBL-WS-031/07` isolation | reception, sample storage, dry sample storage, IgG eluate storage | standards, blank positions |
| `GBL-WS-029/04` deglycosylation | **isolation no.**, dry sample storage | **average dried IgG** |
| `GBL-WS-030/04` clean-up | **deglycosylation no.**, APTS N-glycan storage | |

The worksheets quote each other - WS-029 asks for the isolation number, WS-030
for the deglycosylation number - so entering the six numbers once here keeps
all three consistent across the three days.

### Average amount of dried IgG

`GBL-WS-029/04` asks for this as two figures, DBS and plasma:

    DBS mean concentration       x aliquot volume  ->  DBS ug
    standards mean concentration x aliquot volume  ->  plasma ug

The aliquot is the volume `GBL-WS-031/07` step 6 dries down, 40 uL by default
and editable. Give the tab the NanoDrop .txt and both are computed; leave it
out and the field prints as a dash. The DBS figure uses exactly the wells the
concentration workbook's `DBS` average uses, so the two always agree.

Everything the operator must *observe* - shaking and drying times, LOT numbers,
Protein G plate number and times used, plate labels, enzyme LOT, solution
preparation dates, signatures - stays on the worksheet. Pre-printing a field
that should be recorded live would undermine the record.

## Distribution

`Run IgG Concentration Builder.bat` is the entry point. Edit the `SHARE` path
near the top to the folder holding the exe, put the .bat on the share, and have
everyone shortcut to **the .bat, not the .exe**.

On launch it copies the exe to `%LOCALAPPDATA%\IgG Concentration Builder` only
if the share copy differs, then runs the local one. If the share is unreachable
it falls back to the local copy, so a network outage doesn't stop work.

### Two things to expect

- **SmartScreen.** The exe is unsigned, so the first run on each PC shows
  *"Windows protected your PC"* → **More info** → **Run anyway**. Signing it
  needs a code-signing certificate.
- **Antivirus false positives.** PyInstaller one-file executables are
  occasionally flagged on sight. If that happens, the IT allowlist needs the
  path.

## No lab data in this repository

`.gitignore` blocks `*.txt`, `*.xlsx`, `*.csv` on purpose: NanoDrop exports and
plate layouts carry participant sample IDs. They belong on the Glikobiologija
share. Keep it that way — this is a private repo, but that is not a reason to
put participant data in it.
