# Russian Orthodox Calendar Generator

Version 1.5.0 adds portable, editable `.rocproject` documents to the A4 landscape, Sunday-first publication layout reverse-
engineered from the supplied bilingual calendar reference. The renderer keeps
calendar content dynamic while matching the reference's typography, grid,
colours, icons, fasting washes, and compact legends.

The measured design specification is in [`design/`](design). Generate a stress
month and optional reference comparison with:

```powershell
.\.venv\Scripts\python.exe tools\visual_regression.py --reference-page path\to\rendered-reference-page.png
```

A Windows desktop application for producing print-ready Russian Orthodox calendars in English or Russian, with Australian public holidays kept separate from liturgical observances.

![A4 landscape calendar preview](docs/images/calendar-preview.png)

## Highlights

- Twelve-page A4 landscape PDF by default, with optional portrait output.
- Original English and Russian Holy Trinity source content; Russian liturgical text is not machine-translated.
- Gregorian civil dates and Julian church dates.
- Source-derived Typikon service ranks: Great Feast, Vigil, Polyeleos, Doxology, Six Stichera and No Sign.
- Distinct, bundled service-rank and fasting-permission icons that remain available offline.
- Great Feast/Vigil pink washes, strict-fast grey washes and restrained print-friendly styling.
- Select, deselect, search and reorder saints before publication.
- Australian state and territory public holidays using `python-holidays`.
- SQLite provenance, bilingual source records, cache-first synchronization and user overrides.
- Standalone Windows distribution: end users do not need Python or the legacy .NET application.
- Human-readable project documents that preserve edits separately from the source database.
- Atomic save, backup, autosave/recovery, recent-project and calendar-data update workflows.

## Install the Windows release

1. Open the repository's **Releases** page.
2. Download `RussianOrthodoxCalendar-1.5.0-windows-x64.zip`.
3. Extract the complete archive.
4. Run `RussianOrthodoxCalendar.exe`.

Keep the EXE and its `_internal` directory together. Writable data is stored under `%LOCALAPPDATA%\RussianOrthodoxCalendar`.

## Create and edit a project

1. Choose **File > New Project** (`Ctrl+N`). Select the Gregorian year, Australian state or territory, English or Russian, template and A4 orientation. The current computer year is the default, but any supported year can be entered.
2. If authoritative annual data is unavailable, use the offered **Sync Calendar Data** or **Import Data** action. The application does not silently substitute invented saint data.
3. Choose **Edit Calendar**. On each date, check or uncheck saints, drag them into the required order, edit displayed names, feasts, fasting and service rank, and add project notes. The first checked saint is the primary commemoration.
4. Choose **File > Save Project** (`Ctrl+S`). A new project receives a suggested `.rocproject` filename. Use **Save Project As** (`Ctrl+Shift+S`) for independently editable variants.
5. Preview and **Export PDF** use the current in-memory edits. Export does not silently save the project; an asterisk in the title continues to indicate unsaved work.

Open an existing document with **File > Open Project** (`Ctrl+O`), the Recent Projects submenu, or by passing its filename to the application:

```powershell
.\dist\RussianOrthodoxCalendar\RussianOrthodoxCalendar.exe "C:\Calendars\2027 Queensland.rocproject"
```

The saved year, jurisdiction, language, saint selections and exclusions, exact order, primary saint, overrides, notes, parish details and PDF settings replace global defaults when reopened. **Close Project** (`Ctrl+W`), New, Open and application exit all offer Save / Don't Save / Cancel when necessary.

## Project files, portability and recovery

A `.rocproject` file is readable, indented JSON with `project_schema_version: 1`. It contains project metadata, one annual source snapshot, source version/provenance, explicit overrides and publication settings. It is the editable publication document; the application SQLite database remains the authoritative/reference store and is never overwritten by project edits.

Project writes are atomic. Before an existing file is replaced, one `.rocproject.bak` copy is retained. While changes are unsaved, the application periodically writes a separate `.rocproject.recovery` file and offers Recover or Discard when that project is next opened. These files never silently replace the main document.

Project input is treated as untrusted: size, schema, dates, controlled values, references and asset paths are validated before use. PNG/JPEG parish logos are embedded in the JSON so moving a project to another computer does not retain or break an absolute local path. A corrupt main file produces a useful error and offers its backup when present.

Each document records its calendar-data version. If local data is newer, opening offers **Keep Existing Data**, **Update Project**, or **Compare**. Keep uses the saved annual snapshot. Update refreshes the snapshot, reapplies explicit overrides and retains unmatched saved saints with a review warning rather than deleting them.

Windows file association is prepared at the command-line level: a `.rocproject` path opens automatically when passed as the first argument. The portable ZIP does not write registry keys; users may select **Open with > RussianOrthodoxCalendar.exe** in Windows if they want double-click association.

## Run from source

Python 3.12 or 3.13 is recommended.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe app.py
```

Useful command-line operations:

```powershell
# Synchronize the bilingual source
.\.venv\Scripts\python.exe app.py --sync-holy-trinity --year 2027

# Generate English and Russian calendars
.\.venv\Scripts\python.exe app.py --generate-pdf --year 2027 --state QLD --language English
.\.venv\Scripts\python.exe app.py --generate-pdf --year 2027 --state QLD --language Russian

# Reopen a saved project or generate its exact saved publication
.\.venv\Scripts\python.exe app.py "C:\Calendars\2027 Queensland.rocproject"
.\.venv\Scripts\python.exe app.py --project "C:\Calendars\2027 Queensland.rocproject" --generate-pdf --output calendar.pdf

# Use only previously downloaded source pages
.\.venv\Scripts\python.exe app.py --sync-holy-trinity --year 2027 --cache-only
```

## Authoritative source handling

The **Update Data** action uses the English and Russian Holy Trinity Orthodox Calendar endpoints previously used by the legacy application:

- English: `https://www.holytrinityorthodox.com/htc/ocalendar/v2calendar.php`
- Russian: `https://www.holytrinityorthodox.com/htc/ocalendar/ru/v2calendar.php`

Typikon signs are normalized according to Holy Trinity's published [English](https://www.holytrinityorthodox.com/htc/ocalendar/TipikonSigns.htm) and [Russian](https://www.holytrinityorthodox.com/htc/ocalendar/ru/TipikonSigns.htm) keys. Original rank code/text, source URL and normalized classification are retained. Missing and unknown classifications are not silently converted to No Sign.

The synchronizer is user-initiated, cache-first and conservatively rate-limited. Failed updates preserve existing data. Calendar content should still be verified against the current official calendar used by the relevant parish or diocese; this application is a publishing tool, not an ecclesiastical authority.

## Build and verify

```powershell
.\build_exe.ps1
```

The build script runs the tests, creates the PyInstaller onedir distribution, generates a complete PDF through the compiled EXE, reopens the shipped test project through the EXE, and validates both PDFs' page count, A4 dimensions and extractable text.

Primary output:

```text
dist\RussianOrthodoxCalendar\RussianOrthodoxCalendar.exe
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The suite covers calendar mathematics, Pascha and movable feasts, fasting, all Australian jurisdictions, bilingual source parsing, service-rank normalization and hierarchy, unknown/no-data handling, provenance and overrides, editor selection states, project round trips, selection/exclusion/order/primary persistence, save-as, backup/recovery, corrupt files, embedded assets, project PDF output, Cyrillic output and annual PDF validation.

## Data scope

- Australian holidays are civil-calendar information and never liturgical feasts.
- Source synchronization and imported data retain provenance.
- No automatic translation service is used for authoritative Russian content.
- The application does not require the old legacy .NET executable or its files.
