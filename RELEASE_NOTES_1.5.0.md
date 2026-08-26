# Russian Orthodox Calendar Generator 1.5.0

This release adds editable, portable calendar projects.

## Project documents

- Create, open, save, save-as and close `.rocproject` files from the File menu.
- Preserve the full annual source snapshot plus explicit project-only saint selections, exclusions, ordering, primary designation, feast and fasting overrides, service ranks and notes.
- Preserve language, Australian jurisdiction, A4 layout, legends, parish details and other publication settings independently of global application defaults.
- Keep authoritative SQLite records separate from publication edits.
- Open a project directly by passing its path to the EXE or command line.

## Safety and recovery

- Human-readable, versioned JSON with strict size, schema, type, date, ID, enum and safe-path validation.
- Atomic saves, a single `.bak` backup and periodic `.recovery` files.
- Recovery prompts, unsaved-change prompts and a dirty-state marker in the window title.
- Portable embedded PNG/JPEG parish logos rather than machine-specific absolute paths.
- Saved source snapshots provide a genuine Keep Existing Data option; controlled updates retain overrides and report unmatched records.

## Verification

- Includes `tests/fixtures/sample_calendar.rocproject`, clearly marked as test-only data.
- The automated suite covers round-trip editing, save-as, backup, recovery, corruption, source changes, portability, GUI editing and PDF output.
- The Windows build verifies PDF generation from a reopened project through the compiled EXE.
