# IgG Concentration Builder

Paperwork for a GlycanAge plate - IgG isolation, the concentration
measurement that follows it, and the deglycosylation and clean-up after
that.

**One window, two files.** The Pippeting List goes in once and the NanoDrop
export goes in once; everything else is produced from those:

| Out | What it is |
|---|---|
| `<plate>.xlsx` | the concentration workbook - **Well / Sample ID / conc. / units**, colour-coded, with the DBS and standard averages |
| IgG isolation worksheet | filled GBL-WS-031/07, with the real coloured plate layout |
| Deglycosylation worksheet | filled GBL-WS-029/04, average dried IgG worked out |
| Clean up worksheet | filled GBL-WS-030/04 |

Replaces doing all of it by hand.

```
┌──────────────┬──────────────────────────────────────┐
│ Plates       │  1. The plate - both files, once     │
│              │  2. Worksheet and storage numbers    │
│ 999-GA-…  ✓  │  3. Filter plates and enzyme         │
│ 998-GA-…  ◐  │  4. Solution dates (optional)        │
│ 997-GA-…  ✓  │  5. Build                            │
│              │  6. Where the blank worksheets live  │
│ [New plate…] │                                      │
├──────────────┴──────────────────────────────────────┤
│ Report                                              │
└─────────────────────────────────────────────────────┘
```

## The run

1. open the **Pippeting List** for the plate
2. enter the worksheet numbers taken for it (isolation, deglycosylation,
   clean-up) and the three GBL-WS-002 storage numbers (IgG eluate, dry IgG,
   APTS labelled N-glycans)
3. confirm the filter plate / Protein G plate / enzyme LOTs and, if you want
   them, the solution preparation dates
4. **build and print the IgG isolation worksheet**, then go and do the isolation
5. *next day* - drop in the NanoDrop `.txt`
6. get the concentration workbook plus the **deglycosylation and clean-up**
   worksheets, with the average dried IgG already worked out and each
   worksheet quoting the number of the one before it

**Nothing is ever locked.** Every output can be rebuilt and saved again at any
point, in any order. The numbered sections are the normal path, not a cage -
the only real ordering constraint is that the isolation happens before the
NanoDrop, and that is the bench's constraint, not the program's.

### The plate list

Every plate the program has seen, newest first, with how far it got:

| | |
|---|---|
| ✓ | all three worksheets built |
| ◐ | part way through |
| · | nothing built yet |

Click one and it comes back exactly as it was left - the numbers, the LOTs,
the save folder, the NanoDrop file. That is what makes day 2 a click rather
than a retype. **New plate...** starts one from a Pippeting List; **Remove**
forgets a plate without touching any file it produced.

If a Pippeting List has been moved or renamed since, opening the plate says
so and Browse relinks it.

### It remembers

**Per plate** - everything entered is filed under the GA batch number, so day
2 does not mean retyping day 1. Open the same Pippeting List and it all comes
back, with a note of what has already been built. Without a GA batch number
nothing can be filed, and the report says so rather than losing your work
quietly.

**Per lab** - the LOT numbers live on the share next to the exe, because the
lab shares the physical plates and solution batches. Record a new wwPTFE plate
LOT once and the next analyst is offered it as the current one; the previous
ones stay in the dropdown. If the share is unreachable it falls back to a
local copy, so an outage does not stop work. A write re-reads and merges
before saving, so two people saving at the same moment cannot corrupt the
file - the worst case is a lost edit, never a broken file.

Filled from the store, all of them optional:

| Field | Worksheet |
|---|---|
| wwPTFE plate LOT no. | isolation, clean-up |
| 50 µl CV Protein G monolithic plate (No.) | isolation |
| How many times has this Protein G plate been used | isolation |
| PNGase F enzyme LOT | deglycosylation |
| Enzyme date of reconstitution | deglycosylation |
| Buffer / solution date of preparation + initials | all three |

The deglycosylation worksheet prints two alternative `Enzyme LOT` lines, one
per PNGase F vial size. Pick 30 µg or 50 µg and only that line is filled.

Anything left empty stays empty on the printed worksheet for you to write in -
including every solution date at once, via *Skip these and fill the tables in
by hand after printing*.

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

### The plate grid on the worksheets

The 8x12 grid printed onto each worksheet is the **real plate layout, in the
Pippeting List's own colours** - the green standards, the red blank, the grey
HiDi filler, exactly where Excel shows them. Paper and screen are then the
same picture of the same plate, which is the point of printing it.

The colours are read out of the workbook's cells, not hard-coded, so if the
Pippeting List template is ever restyled the worksheets follow with no code
change. The palette today is:

| Fill | Meaning |
|---|---|
| `FFFFFF` white | real sample (left unpainted, so the worksheet's own cell borders show) |
| `00CC00` green | STAND_08 |
| `3399FF` blue | STAND_09 |
| `FFD700` gold | STAND_10 |
| `FF3333` red | Blank DBS / Blank PBS |
| `D3D3D3` grey | HiDi and other filler |

Text ink flips to white on the dark fills so every name stays legible.

The cell boxes are taken from the worksheet's own drawn rectangles rather
than estimated from where the row letters sit, so the colour lands inside the
printed cell rather than near it. All 96 cells resolve exactly on all three
worksheets; if a revised worksheet ever stopped resolving, the names are
still written and the report says the colours were skipped.

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

Building writes the derivable values straight onto a copy of
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

Left blank on purpose: shaking and drying times, incubation times, the YES/NO
training questions, deviations and signatures - everything the operator has to
observe as it happens.

The LOT numbers, Protein G plate number and times used, enzyme LOT and
reconstitution date, and the solution preparation dates were on that list too
until the **Plate run** tab gained a memory for them. They are still optional:
leave one empty and it prints empty.

Left blank because the format is not known: wwPTFE and 2 mL collection plate
labels, PCR plate name, wwPTFE 0.2 um and 0.8 mL round-bottom labels.

**Pre-filling a controlled document is a QA decision, not a technical one.**
Clear it with whoever owns document control before it becomes routine.

This now matters more than it did. Pre-filling a *derived* value - the sample
grid, a worksheet number, an average - only restates something already
recorded elsewhere. Pre-filling a **LOT number or a solution preparation
date** is different: it is a traceability record, and the program is
asserting it from memory rather than from the analyst reading the label in
front of them. A remembered LOT that is no longer the plate actually on the
bench would print as though it had been checked.

Two things follow, and they are the analyst's responsibility, not the
program's:

- **Check the offered LOT against the physical label before printing.** The
  dropdown shows what was used *last*, which is a convenience, not evidence.
- If your QA position is that these fields must be handwritten, leave them
  empty (and tick *Skip these* for the solutions). Everything else still
  fills, and those rows print blank.

### Separate sheet instead

The *Separate sheet to attach, instead of filling the worksheets* option
under **5. Build** produces the earlier one-page-per-
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
