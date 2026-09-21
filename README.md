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
│  GlycanAge   │  999-GA-202609                       │
│  plate run   │  999-GA-202609 Pippeting List.xlsx   │
│              │                                      │
│  ✓ 999-GA-…  │ [1 Plate][2 Numbers][3 Materials]…   │
│  ◐ 998-GA-…  │  ┌────────────────────────────────┐  │
│  ✓ 997-GA-…  │  │  one step at a time            │  │
│              │  └────────────────────────────────┘  │
│ [New plate]  │                                      │
├──────────────┴──────────────────────────────────────┤
│ Report                                              │
└─────────────────────────────────────────────────────┘
```

Dressed in the GlycanAge colours taken from **glycanage.hr** - deep green
`#09341F`, the single orange accent `#E66439`, the soft ground `#F1F5F3` -
so it reads as part of the same thing rather than a lab script bolted on.
The orange is used only on the button you are meant to press next.

**Four steps, one visible at a time.** Everything used to be stacked in six
sections down a scrolling page, so finding a button meant hunting. Now the
step you want is one click away and always on screen.

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

### Dates - one per day of the process

A plate is three days of bench work, and each worksheet carries the date it
was actually done. Type **Day 1 (isolation)** and the other two follow on the
next *working* days - an isolation started on a Friday puts the
deglycosylation on the Monday and the clean-up on the Tuesday, not on the
weekend. All three boxes stay editable for when a run slips.

The storage worksheets are dated when the material actually goes into
storage, which is not the same day for all three: the IgG eluate and the
dried IgG are both put away at the end of the isolation, but the
APTS-labelled glycans do not exist until the clean-up on day 3.

### Worksheet and storage numbers

They are taken in a run, so only the first is worth typing. Put `GA3084` in
the first box, press **Fill ↓**, and the rest follow - `GA3085`, `GA3086`.
The prefix and the digit width are kept, so `GA0099` steps to `GA0100`. If
the first entry does not end in a number there is nothing to count from, and
it says so rather than guessing.

### Protein G plate - counted, not typed

*How many times has this Protein G plate been used?* is no longer a box to
fill in. The program counts it: the number of distinct GA batches that plate
has been used on, across every analyst, because the count lives on the share.
Pick the plate number and the form says

    used on 6 plate(s) so far  →  this plate is no. 7

Rebuilding a worksheet for the same plate does not inflate the count, and two
analysts running two different plates both add to it.

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

### Plate labels

A wwPTFE plate is labelled with the plate's own name and nothing else -
`999-GA-202609`. A plate that goes into storage carries the longer form,
which names its contents and the GBL-WS-002 number it is logged under:

    999-GA-202609 IgG eluate GA3084 25.09.2026 MF
    999-GA-202609 APTS N-glycans GA3086 29.09.2026 MF

| Label | Filled with |
|---|---|
| wwPTFE plate (isolation) | plate name |
| 2 mL collection plate | plate name |
| PCR plate **name** (deglycosylation) | plate name |
| wwPTFE 0,2 µm plate (clean-up) | plate name |
| 1 mL collection plate (IgG eluate) | the long form |
| 0.8 mL round-bottom (APTS glycans) | the long form |

`Sample label` on each GBL-WS-002 repeats the label of the plate that sheet
describes, so the paperwork and the plate read the same.

The answer boxes behind these range from 55pt to over 400pt wide. Rather than
widen the rectangle filter until page furniture starts qualifying, an
unfound box falls back to writing just after the label - which lands inside
it anyway.

## The storage worksheets (GBL-WS-002)

One filled sheet per storage number the plate takes - IgG eluate, dry IgG,
APTS labelled N-glycans - from the **Storage worksheets (x3)** button.

| Filled | From |
|---|---|
| No. | the GBL-WS-002 number for that output |
| Date | the day that material goes into storage |
| Lab worksheet no. | the IgG isolation worksheet number |
| Sample reception worksheet no. | as entered for the plate |
| Sample type / Packed in | ticked - they follow from what is being stored |
| Sample list | the coloured 8x12 plate grid |

Left blank on purpose: **the fridge/freezer letter and the drawer number**.
Those are chosen standing at the freezer and are not knowable here.

Note that GBL-WS-002 puts its answer boxes *before* the wording for
`Sample reception worksheet no.` and `Lab worksheet no.`, where every other
worksheet puts them after - so those two are placed into the box on the left.

## Solutions

One shared list. Whoever makes up a solution records the date with **+**;
everyone else is offered it from the dropdown. When a bottle is used up,
**−** takes that preparation off the list for everybody.

That is all it tracks. There are no volumes, no stock levels and no expiry:
the bottle in the fridge is the authority on all three, and a number in a
program that disagrees with the bottle is worse than no number at all.

The date you pick is what goes into the worksheet's own
`Solution | Date of preparation | Initials` table.

*Skip these and fill the tables in by hand after printing* leaves every
solution row blank on the paper.

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

**Size of everything else.** Values written into the worksheet's own fields
are 11pt and the buffer/solution tables 10pt - big enough to read on paper at
the bench. A value goes in at the left edge of its ruled box so two fields in
identical boxes look identical, and shrinks (down to 6pt) only if it would
otherwise run past the printed border. Where the label is printed *inside*
the box - `No.`, `Date:` - the value stays put rather than being written over
the label.

The plate grid is sized separately and is unaffected: 96 sample names have to
fit in 96 cells, so it gets as much as it can and no more.

**Typography.** The names are set in Segoe UI, taken from the system rather
than bundled (Helvetica stands in if it is missing). One size is chosen for
the whole grid - the largest that fits every name with real margin in its own
cell - because sizing each cell to its own width makes the columns ragged,
the worksheet's columns not all being the same width. Each name is centred in
its cell box both ways rather than dropped on the row-letter baseline, and
standards and blanks are set in the semibold weight so the plate's landmarks
read at a glance.

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

## For the analysts

`HOW TO INSTALL AND USE.txt` sits next to the exe on the share and is written
for someone who just wants to use it: how to make the shortcut, what the
SmartScreen box is, and - the question everyone asks - how one person's LOT
number or solution batch reaches everybody else.

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
