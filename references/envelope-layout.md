# Layout of dimensioned view blocks

Use `layout` in new drawing plans. First build all required dimensions, labels and tables and perform the requested local dimension alignment. Then measure each view together with its annotations as one paper-space rectangle. Move these blocks as units, keeping orthographic projection alignment. Geometry definitions and annotation identities remain unchanged by packing.

```json
{
  "layout": {
    "usable_bounds_mm": [35, 70, 405, 282],
    "reserved_boxes_mm": [[230, 10, 415, 60]],
    "orthographic_views": {"front": "front", "top": "top", "right": "right"},
    "gap_mm": 12,
    "padding_mm": 3,
    "fill_range": [0.45, 0.65],
    "target_fill": 0.55,
    "scale_factors": [1, 0.95, 0.9, 0.85, 0.8, 0.75, 0.625, 0.5, 0.375, 0.25, 0.2, 0.125]
  },
  "line_hierarchy": true
}
```

The bounds above are an example for the tested GB A3 template. Measure the chosen template's frame, stamp, title and notes; do not copy these bounds to another template. Coordinates use mm from the sheet bottom-left. Roles map to actual model-view IDs, independently of localized model orientation names. A front role is required; top and right roles are optional.

The native executor measures the union of the view outline and annotation display primitives: extension and dimension lines, leaders, arrowheads, text, arcs and polygons. Text uses native display position/angle/width/height, with conservative allowance for glyphs and descenders. Arc bounds use their sweep and projected extrema; this is an occupied-area estimate, not a minimum-area packing proof. Unsupported display primitives or unavailable data fail explicitly. The view envelope gets `padding_mm` on all four sides; tables use their rendered footprint. Sheet notes remain fixed obstacles. Approved reserved regions remain obstacles.

The planner accounts for asymmetric annotation margins relative to each view's centre. Front/top centres share X; front/right centres share Y. The projection convention determines which side receives the top and right views. These three rectangles form an aligned group, with supporting/isometric views packed around it. Tables stack downwards from the usable region's upper-right corner, leaving `gap_mm` between them. Table/region conflicts stop the layout. Move each view and its attached annotations by the same translation, then rebuild and remeasure; test actual positions and all block/table/reserved intersections before saving.

`scripts/planner.py::pack_envelopes` is shared by native execution and offline verification. It translates at each trial scale without rotating views, reducing font size, deleting dimensions or changing nominal values. Native execution tries the descending `scale_factors` relative to the initially authored scales. It scales model geometry and annotation positions about each view centre while retaining fixed paper text heights and arrow settings; remeasure after every scale. Compare measured text heights before/after and keep orthographic scales consistent. Select the fitting trial closest to `target_fill`, preferring `fill_range`. Stop exploring smaller scales once measured occupation reaches the target; restore the best trial if needed. Occupation is the sum of view-envelope and table-rectangle areas divided by usable drawing area, not the number of inked pixels. Record every trial and any missed target; visual balance and local legibility still require review. It uses a bounded corner/grid search: failure after the allowed scale trials can mean the arrangement needs different dimension lanes, more informative views or a verified feature table; it does not prove mathematical impossibility. If no placement fits at any allowed trial, retain all required geometry and report the failure. Do not shrink the whole exported PDF: that would also shrink fonts and the template frame. Select scale during preflight with `candidate_layouts`, then verify its actual annotated envelopes. During a first-attempt skill comparison, preserve the frozen first result and follow the user's retry restriction.

`line_hierarchy: true` gives visible model edges the document's THICK line weight and dimensions/leaders THIN, with black annotations. It changes only the new drawing's content style; frame, projection, font and arrows stay with the approved template. These are SOLIDWORKS line-weight categories, not a guarantee of a specific millimetre width in every template/printer. The new drawing's actual DWG-derived PDF must retain a visibly heavier part outline than dimensions in monochrome printing. Colour alone is insufficient when output is monochrome. `false` preserves inherited content weights.

Native files retain a plan-hash-bound `_DraftingLayout` record with the measurements, solved positions and actual final envelopes. Verify/Export recompute the same solution, compare reopened measured envelopes and styles, and reject missing/stale records. Retain the `layout_measurement` and `envelope_layout` reports for review.

Global block packing prevents one view's annotation footprint from covering another block or table. It does not untangle overlapping text or crossing leaders *within* a view. Inspect dimension lanes and local legibility before treating the layout as accepted; dimension completeness and nonredundancy remain separate gates.

## Quantified defaults

Use 3 mm envelope padding, 12 mm block-to-block/block-to-table/table-to-table clearance, and at least 10 mm clearance inside the actual drawing frame. The selected template may require larger reserved zones. Native local dimension alignment uses 8 mm spacing within each view. Dimension and table text targets are 3.5 mm and 3 mm respectively; preserve the approved template family and readable paper height rather than scaling fonts with views. If the template has different approved heights, report them and keep them fixed during scale search. Aim for 55% occupied rectangle area, prefer 45%-65%, and review content-envelope centre offsets relative to the usable frame. These are composition defaults, not a drafting standard or proof of readability.

Use `{scale:iso}` (or another actual view ID) in a note wherever a view scale is shown. The executor resolves it and updates it after scale selection; verification checks the final numeric text. Do not hard-code a scale note when adaptive scaling is enabled. Overall view scale changes the paper drawing, never the nominal model dimensions or coordinate table values.
