# Russian Orthodox Calendar Generator 1.8.0

This release aligns feast-rank and fasting presentation with the supplied source Word calendar while preserving the existing editor, project and publishing workflows.

## Source-faithful symbols and placement

- Uses the original Unicode Typikon symbols found in the supplied Word document for Great Feast Vigil, Vigil with Litia, Polyeleos, Doxology and Six Stichera.
- Places each feast-rank symbol immediately to the left of its commemoration on the same line; day cells no longer print a rank description.
- Uses the original oil and fish symbols at the top-right of each day cell, without explanatory text in Word output.
- Keeps Vigil/Litia and Polyeleos text red while Doxology and Six Stichera text remains black.
- Treats No Sign as an ordinary service classification with no printed glyph, matching the source instead of inventing a substitute.

## Word and PDF publication

- Sets editable Word calendar body text to the source document's Arial Narrow 8 pt default.
- Matches PDF and Word spacing, washes, symbol placement and inline rank treatment more closely.
- Places fasting and liturgical-rank legends inside otherwise unused calendar-grid cells.
- Preserves strict-fast grey wash independently of feast rank.

## Editor and project behaviour

- Saints of the day are unselected by default unless a project explicitly selects them.
- Adds a persistent Liturgical Week / Tone toggle to application and project settings.
- When enabled, Liturgical Week / Tone appears above the saints list in PDF and Word cells.
- Project schema 3 stores the new setting and migrates earlier project files automatically.

## Verification

- Automated coverage includes exact glyph and colour mapping, hidden-by-default saints, fasting symbol priority, Word font/placement/legend structure, PDF and Word tone toggling, and project migration.
- Complete 12-month PDF and Word exports were rendered and inspected page by page.
- The packaged Windows executable is tested for project loading, PDF export, editable Word export and GUI launch/close.
