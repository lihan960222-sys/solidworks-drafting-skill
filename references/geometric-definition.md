# Complete nominal geometry with no redundant dimensions

Read this before choosing dimensions. Acceptance means that the delivered 2D drawing alone uniquely determines the nominal solid, up to a rigid movement of the whole part. The recipient must not need the 3D model, sketch constraints, feature-tree knowledge, pixel measurements, or an unstated symmetry assumption. Tolerances, surface finish and manufacturing release are separate. Deferring tolerances does not defer diameters, blind depths, thread nominal size/pitch/depth, radii, angles or other nominal geometry.

## Inventory before import

Inspect every body and its faces, edges, connectivity, openings and inner boundaries. Use feature history to explain geometry, not as the completeness criterion: auxiliary sketches, deleted/intermediate shapes and feature parameters may not describe the final solid; imported bodies may have little useful history. Give final geometric features stable IDs with face/edge evidence. Include small fillets/chamfers and back-side features. Do not remove a real feature because it is small or the import API did not return a dimension.

Choose a local part coordinate frame from identifiable faces/axes. This is a nominal dimensioning reference, not an invented GD&T datum system. Define origins, axis directions and handedness. Separate a feature's size from its location and orientation. Absolute world position is not a part requirement. A claimed parallel, concentric, coaxial, tangent, symmetric or equally spaced relationship must be visible and explicit in the delivered drawing or supported by its dimension scheme. The original model's implicit constraint does not carry into a PDF.

For each feature, ask which independent geometric quantities remain unknown to someone reading the drawing:

| Feature | Definitions to check |
| --- | --- |
| Base and nonrectangular profiles | Complete outer/inner profile, thickness or extent, steps, offsets, slopes, corners and connecting conditions; overall extents alone are insufficient |
| Hole, recess, counterbore or countersink | Every diameter and stage depth; blind/through condition and pointed-bottom shape when present; centre coordinates or a complete locating scheme; axis direction; entry side; quantity and member identity |
| Slot or pocket | Width, end radii/shape, centre distance or overall length with an explicit relation, depth, wall/bottom shape, location and direction |
| Stepped shaft or bore | Each diameter, shoulder location/segment length, axis relationships, blind depths, grooves and end features |
| Fillet and chamfer | Radius or distance/angle, exact affected edges and extent; never assume a radius equals half a width unless the shape explicitly establishes that relation |
| Pattern or mirror | Seed geometry, count, spacing or pitch-circle radius/diameter, direction/axis, phase or starting position, mirror plane and all member coverage |
| Tilted or internal feature | True shape/size, direction/angle and location; add an informative reverse/section view rather than relying on foreshortened appearance or an isometric |
| Freeform or unsupported surface | A mathematically sufficient profile/coordinate definition with verified scope; otherwise fail explicitly. A few overall dimensions do not define an arbitrary surface |

Use supported full sections for internal geometry. If the backend cannot express a required view or associated dimension, report `unsupported_operation`. A missing feature definition blocks acceptance even if all available model dimensions imported successfully.

## Select an independent dimension scheme

Build necessary definitions first, then find annotations that express them. Prefer existing associative dimensions when their meaning and attachment match; otherwise use a supported associated dimension or an exact, uniquely labelled feature table. `Visibility.model_dimension_inventory` establishes import availability only. Never choose `keep` by taking every inspected parameter, every imported parameter, a fixed count or only positive values. Signed coordinates and zero offsets can matter to location.

Use one authoritative driving representation for a given geometric property in the same frame. Do not repeat it in another view or in both a dimension and a table. Different features with equal numbers are not duplicates. A verified shared specification may cover multiple identical features only when it explicitly identifies all members; the current hole table requires one labelled hole per row, not an unverified grouped-pattern shortcut.

A complete chain supplies enough independent relations to determine every segment; it does not need every segment explicitly dimensioned. For a straight three-segment part, `L=100`, `a=30`, `b=40` determines `c=L-a-b=30`. Omit the extra driving `c=30`; record its derivation. Similarly, use centre coordinates or inter-hole distances with a complete origin/orientation scheme, without independently dimensioning both equivalent schemes. Prefer direct dimensions for functionally important quantities. Do not remove one solely to minimize annotation count if it leaves a less clear or ambiguous scheme. This backend has no certified reference-dimension operation: omit redundant annotations rather than pretending a driving dimension is a reference dimension.

Inspect chains as a dependency graph. Derived definitions must resolve to independent annotated definitions, have no cycles, and agree with measured geometry. Do not use a closed loop to conceal a missing origin, direction or independent size. Check circular patterns' phase, and mirrored geometry's plane and side: spacing/count or symmetry alone may leave an undetermined movement. Inconsistent dimensions also fail, even if none is missing.

Keep the distinction between parameter coverage and drawing definition. A redundant source parameter may be explained by an existing authoritative definition and an explicit derivation in coverage; it need not have its own imported annotation. Never relabel an undimensioned real feature as auxiliary. Supplement the conservative feature inventory using measured final geometry, preserving source hash and original measurements.

## Reconstruction and recorded audit

Perform an independent read of the actual annotation scheme. Hide the model facts while determining geometry from the views, dimensions, explicit relations and tables; then compare the resulting feature definitions with measured facts. For every feature, list any remaining freedom: translation, rotation, size, shape, depth, count or handedness. A missing nominal relation, ambiguity, unsupported surface or unresolved dependency is a failure. Do not fill a gap using the source model or visual estimation.

Record `geometry_audit` in the v2 plan and update it if the view/dimension scheme changes:

- `scope: "nominal_geometry"`, and `source_sha256` matching facts.
- `checks` with `feature_inventory`, `sizes`, `locations`, `orientations`, `depths_and_sections`, `patterns_and_relations`, `dimension_chains`, `nonredundancy`, `reconstruction`. Each is `{ "passed": true, "evidence": "specific features, frames and checks performed" }`. Do not fill these with generic success text or mark unperformed checks true. Explain genuinely inapplicable categories using actual geometry.
- `definitions`: each entry has unique `id`, `entity`, `property`, `frame`, `evidence`. A driving definition names one exact planned `annotation` ID. A derived definition instead has `depends_on` definition IDs and an explicit `equation`; do not give it another driving annotation. Separate e.g. hole diameter, X, Y and depth into different properties. A table row ID may support several properties from its different validated cells. Evidence must identify which cell/property is used. All driving dimension and table-row IDs need semantic mappings. Multiple coverage requirements may refer to the same authoritative definition.
- `missing_definitions` and `redundant_definitions`: empty only after checking. Preserve entries while unresolved; they block acceptance.

The deterministic gate checks source binding, required review evidence, semantic duplicates, annotation mappings and dependency cycles. It does **not** solve arbitrary geometric constraints, evaluate free-text equations or reconstruct a B-rep. Numerical derivations, complete feature enumeration, relation independence and reconstruction are agent review responsibilities, followed by the user's drawing review. Do not claim a formal mathematical or manufacturing certificate from this gate. If these responsibilities cannot be carried out reliably, stop at `FAILED`/`REVIEW_REQUIRED` and identify the undecided geometry.

After native save/reopen and export, inspect the delivered PDF against this audit. All required definitions must be visible, legible, correctly attached and unambiguous there. A dimension present only in the native model or outside the delivered sheet is missing from the drawing. Verify printed values, units, signs and necessary precision; do not let display rounding change the nominal geometry. Read the drawing as a machinist would, without needing the 3D source.

Reference basis: [MIT's engineering drawing guidance](https://ocw.mit.edu/courses/2-007-design-and-manufacturing-i-spring-2009/pages/related-resources/drawing_and_sketching/) explains complete, unambiguous dimensional definition. [SOLIDWORKS Model Items](https://help.solidworks.com/2026/english/SolidWorks/sldworks/HIDD_DVE_INSERT_MODEL_ITEMS.htm) documents native duplicate elimination; this removes duplicate model items, not all semantically redundant drawing definitions.
