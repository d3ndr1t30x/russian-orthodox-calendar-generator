# Russian Orthodox Calendar Generator 1.10.0

This release is limited to the project editor interface. PDF and Word rendering
logic, styling and output formatting are unchanged from version 1.9.0.

## Project editor improvements

- Checkbox indicators now have a darker two-pixel outline, stronger hover state,
  high-contrast checked fill and a clear tick.
- Primary saints are selected from a visible checkbox list rather than a compact
  dropdown. The list enforces one primary selection and keeps that saint enabled
  for publication.
- Additional saints use the same visible, wrapped checkbox-list presentation
  immediately below the primary list.
- Both saint lists retain the complete saint name and stay synchronized when a
  name is edited.
- Double-clicking a saint or feast now opens a wide, wrapped full-text editor.
- The editing window uses a blue outline, tinted background and explicit EDIT
  MODE label so the editable state is immediately apparent.

## Verification

- 85 automated tests pass, including new primary/additional selection, checkbox
  contrast and full-text editing checks.
- The packaged Windows executable completes project open and GUI launch tests.
- PDF and DOCX generation smoke tests continue to pass using the unmodified
  rendering modules.
