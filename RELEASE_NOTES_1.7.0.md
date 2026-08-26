# Russian Orthodox Calendar Generator 1.7.0

This release adds editable Word publishing, explicit primary saints and derived edited-day tracking.

## Editable Word calendars

- New **File > Export Editable Word Document...** action and `--generate-docx` command.
- Genuine `.docx` output generated directly from resolved calendar data using editable tables, paragraphs, runs and icon images.
- Twelve intact A4 landscape month grids followed, where needed, by a compact editable details section containing every overflow commemoration.
- English and Russian output uses existing language-specific source records; no translation API is used.
- PDF and DOCX share the same selected-saint ordering and primary-saint resolution.

## Primary saints

- Every saint-bearing source day receives a deterministic default primary saint.
- Explicit source-primary designations take precedence, followed by source order.
- The editor exposes a clear Primary / featured saint selector and an Add Additional Saint action.
- Primary changes, additions, selection and ordering persist as project overrides; reset restores the source default.

## Edited-day tracking

- Edited state is derived by comparing effective resolved state with the project's saved source snapshot.
- No-op edits do not create overrides or pencil indicators.
- Modified viewer cells show a small pencil with an explanatory tooltip; the editor shows Default or Edited status.
- Project status displays the live edited-day count.
- Day, month and year resets recalculate edited state immediately.

## Compatibility and verification

- Project schema 2 stores default/current primary identity; schema-1 projects migrate automatically.
- The authoritative SQLite source remains untouched by project edits.
- Automated coverage includes primary selection, migration, no-op comparison, edit persistence/reset, pencil interaction, custom saints, dense Word overflow, Cyrillic Word content and Word/PDF consistency.
- Final English and Russian DOCX files were opened in Microsoft Word and rendered page-by-page for visual inspection.
