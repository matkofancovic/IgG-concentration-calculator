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

## Filling the worksheets

The **Worksheets** tab writes the derivable values straight onto a copy of
each worksheet PDF - the 8x12 sample grid, GA batch, worksheet and storage
numbers, the IgG eluate plate label, the average dried IgG - in dark blue, so
what the program added is obvious against the black original. The blanks on
the share are never modified.

Fields are located at run time from the labels printed on the page, not from
fixed coordinates, so a revised worksheet still fills. Anything that cannot
be found is reported rather than written into empty space.

The blank worksheets are discovered in

    \10.70.119.100\Glikobiologija\SOPs and WS\WSs

by document code, newest revision winning, so a new release is picked up
without a code change. The folder is editable in the form.

| Worksheet | Filled |
|---|---|
| **IgG isolation** | no., date, batch, grid, reception, sample storage, dry sample storage, IgG eluate storage, 1 mL plate label |
| **Deglycosylation** | no., date, batch, grid, isolation no., dry sample storage, average dried IgG |
| **Clean up** | no., date, batch, grid, deglycosylation no., APTS N-glycan storage |

Left blank on purpose: shaking and drying times, LOT numbers, Protein G plate
number and times used, enzyme LOT and reconstitution date, incubation times,
solution preparation dates, the YES/NO training questions, deviations and
signatures - everything the operator records as it happens.

Left blank because the format is not known: wwPTFE and 2 mL collection plate
labels, PCR plate name, wwPTFE 0.2 um and 0.8 mL round-bottom labels.

**Pre-filling a controlled document is a QA decision, not a technical one.**
Clear it with whoever owns document control before it becomes routine.

### Separate sheet instead

The *Separate sheet to attach* option produces the earlier one-page-per-
worksheet PDF instead, for when attaching is preferred to filling.

### GA batch number

Not stored in any cell of the Pippeting List, so it is read from the file name
(`999-GA-202609 Pippeting List.xlsx`) and, failing that, from the plate folder
the file sits in. A renamed file still resolves.

### IgG eluate plate label

    <GA batch> IgG eluate <IgG eluate storage no.> <date> <initials>
    999-GA-202609 IgG eluate GA3084 18.09.2026 MF

### Average amount of dried IgG

Two figures, DBS and plasma:

    DBS mean concentration       x aliquot volume  ->  DBS ug
    standards mean concentration x aliquot volume  ->  plasma ug

For GlycanAge the plasma figure is the standards: the three plasma standards
are the only plasma on the plate. The aliquot is what step 6 of the isolation
worksheet dries down, 40 uL by default and editable. The DBS figure uses
exactly the wells the concentration workbook's `DBS` average uses.

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
