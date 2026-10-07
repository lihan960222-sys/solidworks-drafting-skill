# Plan v2

All paths are absolute and quote-free. Geometry facts use SI; plan positions and linear sizes use mm; angular dimensions use degrees. All operations are grounded in the same inspected source hash/configuration. The runner performs offline validation before CAD mutation and repeats native checks.

Required roots: `version: 2`, `facts`, `template`, `output_drawing`, `output_dwg`, `output_pdf`, `sheet`, `views`, `dimensions`, `diameters`, `sections`, `labels`, `tables`, `notes`, `unresolved`, `coverage`, `dimension_ids`. Lists can be empty except `views`; geometry coverage cannot be empty. SLDDRW goes in `internal/`; DWG/PDF share a separate `deliverables/`. Refuse existing outputs except in Verify/Export/Preview modes.

`sheet`: `width_mm`, `height_mm`, `first_angle` boolean. Use one A4, A3 or A2 sheet, either orientation. These values must match the selected template; the executor never resizes or replaces its format. Microsoft Print to PDF paper availability must also pass actual output checks; A2 is not certified on this machine.

| Operation | Fields |
| --- | --- |
| `views[]` | `id`, `model_view` exactly from facts, `position_mm: [x,y]`, `scale`, `reason` |
| `dimensions[]` | `id`, `view`, `direction: horizontal/vertical`, `expected_mm`, `position_mm`, `evidence`; associated overall span |
| `diameters[]` | `id`, `view`, `edge_id`, `expected_mm`, `position_mm`, `evidence` |
| `linear[]` | `id`, `view`, `a_edge`, `b_edge`, `direction: horizontal/vertical/angular`, `expected_mm` or `expected_deg`, `position_mm`, `evidence` |
| `radial[]` | `id`, `view`, `edge_id`, `expected_mm`, `position_mm`, `evidence` |
| `sections[]` | See the bundled `validate_native.py` section validator for the exact straight-section fields; the cut is a real native section |
| `labels[]` | `id`, `view`, `edge_id`, `text`, `offset_mm`; attaches to a uniquely matched visible circle |
| `notes[]` | `id`, `text`, `position_mm`; inherit template text format, font overrides are rejected |
| `model_dimensions` | `include_unmarked` boolean, `keep` list of exact native dimension names; optional `positions: [{name, position_mm}]` moves only retained dimensions; imported IDs become `model:<name>` |
| `import_pmi` | Boolean. Imports existing DimXpert-related annotations through `IView.ImportAnnotations`; no tolerance generation |
| `auto_arrange` | Boolean. Aligns selected dimensions locally with native `AlignDimensions`; does not prove global collision freedom |

Related orthographic views share a scale; an isometric can use another scale with a visible scale note. Do not use the scale to change nominal sizes. Existing model dimensions are selectively retained by identity, not by number alone.

`tables[]`: `role` is `nominal_hole_schedule` or `nominal_feature_schedule`; include `position_mm`, `row_height_mm`, `column_widths_mm`, rectangular string `rows` (header first), `feature_ids`, `units`, `row_evidence`, and `evidence`. Row first cells must equal the corresponding unique IDs. Each ID must appear as a visible label. Hole schedules require 3D `origin`, global `axes: ["X","Y"]` and `units: "mm"`; headers ID, X (mm), Y (mm), D (mm), Depth and Qty/Count; each row is one labelled hole with quantity 1 and exact `edges:<id>` evidence matching its label. Coordinates/diameter are checked against that circle; depth/THRU is checked against matching cylindrical faces and body bounds. Other frames, grouped quantities and arbitrary column layouts need a verified backend. The agent must review each row's feature meaning, face type and consistency with drawn dimensions; general feature schedules remain a manually reviewed representation.

`dimension_ids` is the exact union of operation IDs, `table:<feature-id>` and `model:<name>`. `coverage[]` entries contain `feature` matching facts' `draft_features[].id`, `status`, and `fields`. Every required field has `value`, `unit`, `evidence`, and an `annotation` in `dimension_ids`. Missing/unsupported geometry uses `missing_geometry_definition` or `unsupported_operation` plus `reason` and prevents acceptance. Supplemental B-rep definitions must first be recorded explicitly in a copy of the facts inventory, preserving source hash and original measured geometry; unknown coverage IDs are rejected, including missing supplemental definitions. The validator checks this supplied inventory, not exhaustive manufacturing intent.

Nonempty `details`, `dimension_scheme`, `style` and `export` overrides are rejected; they must never be silently ignored. The template supplies styles and the current export backend is explicit. Do not add guessed dimensions, PMI or metadata merely to make coverage pass.

Modes:

```powershell
# Run with Windows PowerShell 5.1 -NoProfile -Sta -ExecutionPolicy Bypass
& <skill>/scripts/run.ps1 -Mode Inspect -Source <saved-part> -Output <internal/facts.json> -Python <python>
& <skill>/scripts/run.ps1 -Mode Execute -Plan <internal/plan.json> -Output <internal/execution.json> -Python <python>
```

Supply `-InteropPath` if registry discovery is unavailable. Preview produces an internal PDF only. Inspect/Visibility/Prepare can be used before Execute, but a prepared native drawing must be exported using `Export`, since Execute refuses the existing native output. Verify/Export refuse preexisting open drawings so save/reopen never closes a user-owned document. New native files retain a private semantic annotation mapping; legacy native files without it must be regenerated or audited through an explicit supported migration, not certified by counts alone.
