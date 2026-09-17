# Russian Orthodox Calendar Generator 1.9.0

This release applies a dedicated formatting-fidelity pass to PDF and editable
Word exports. The supplied PDF and Word files were used only as visual and
measurable style references; no dates, saints, feast names, or other calendar
content was copied into the application.

## Reference-matched output

- A4 landscape pages now use measured 7 mm side and 5 mm top/bottom margins.
- Weekday strips, equal-width columns, borders, title rows and weekly grids match
  the corresponding reference format more closely.
- PDF output uses available Times New Roman and Arial Narrow system fonts, with
  bundled Unicode-capable fallbacks for portability.
- Word output uses the reference roles and sizes: 40 pt month titles, 28/14 pt
  civil/Julian dates, 9 pt weekday labels and 8 pt body copy.
- Sunday, weekday, fasting and major-feast colours use the measured source values.
- All fasting days receive the restrained grey wash; Great Feast and Vigil pink
  treatment retains visual precedence.
- Rank and fasting symbols remain source-faithful and legends stay inside unused
  grid cells.
- Footers are centred and generated from the active project rather than copied
  from the references.
- Five- and six-row Word months use separate editable table rhythms so each month
  remains on one page.

## Verification

- The complete automated test suite passes, including new measured-format checks.
- Full 12-month PDF and Word publications were rendered and visually inspected.
- The packaged Windows executable generates and validates PDF and DOCX output,
  reopens the shipped project fixture, and completes its GUI launch/close smoke test.
