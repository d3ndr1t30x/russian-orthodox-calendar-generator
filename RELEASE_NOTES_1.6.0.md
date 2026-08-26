# Russian Orthodox Calendar Generator 1.6.0

This release completes the calendar editor UX and safe project-reset pass.

## Interactive calendar viewer

- Every valid calendar date is now a real interactive cell.
- Whole-cell hover outlines preserve feast and fasting background semantics.
- Single-click selects a date; double-click opens that exact date for editing.
- Day context menus expose Edit Day and Reset Day; month context menus expose Reset Month.
- Supported service ranks appear as a consistent bundled icon plus readable text.

## Responsive day editor

- Resizable, minimizable and maximizable window with a scrollable detail pane.
- Expandable Date, Saints, Feast, Service Ranking, Fasting, Notes and Advanced sections.
- Always-visible service-rank icon and label, with a centralized rank/icon mapping shared by GUI and PDF.
- Persistent Reset Day, Cancel and Save Edits action bar.
- Transactional cancel/discard behavior prevents accidental commits.

## Reset and save safety

- Reset Day, Reset Month and Reset Year remove only project overrides and rebuild from the project's saved source snapshot.
- Scope-specific confirmations include affected date/month counts; full-year reset requires `RESET <year>`.
- SQLite authoritative data and external source versions are never modified or synchronized by reset.
- Successful validated project saves show explicit confirmation; failed saves retain the dirty state.

## Verification

- Automated interaction coverage includes hover, exact-date double-click, rank presentation, responsive editor controls, transactional cancel, all reset scopes, source-database isolation, round-trip persistence and save feedback.
- Packaged EXE checks exercise project loading, the interactive viewer, responsive editor, rank assets and clean GUI exit.
