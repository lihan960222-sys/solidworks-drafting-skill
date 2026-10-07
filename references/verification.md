# Verification and recovery

Do not equate file creation, annotation count, a nominal feature table or a successful COM call with engineering completeness.

Model dimensions: compare the actual `Visibility.model_dimension_inventory` against the necessary engineering definitions before choosing `keep`. An inspection feature parameter may not be returned by native drawing import for the selected views/settings. Execute reports its actual `model_dimension_import`, including missing requested identities, and refuses to continue when required imports are absent. Full source identities and their two-part drawing names must resolve to the same bound dimension and SI value after reopen. A legitimate CAD failure must retain its native error, rather than be mislabeled as a request-identity failure.

Nominal geometry: apply [geometric-definition.md](geometric-definition.md). A complete feature coverage record is necessary but insufficient; native/output acceptance also checks `geometry_audit`. Missing dimensions, redundant semantic definitions, unmapped driving annotations, dependency cycles, stale source binding or unperformed reconstruction checks block acceptance. Independently inspect actual equations/relations and remaining geometric freedom; the checker does not solve arbitrary geometry or free-text equations. Deferred tolerances and surface finish do not excuse missing nominal definitions.

Regression commands: run `python -m unittest discover -s tests`, `tests/native-acceptance.ps1 -Case Compile -InteropPath <installed-redist>`, and `tests/native-dimension-inventory.ps1 -Plan <tentative-plan> -Output <new-internal-report> -Python <python> -InteropPath <installed-redist>`. The inventory test proves native measurement and source integrity; it does not certify complete geometry coverage or drawing legibility.

Native: inspect hash/configuration; reject source modifications; check actual created dimension values and scoped visible edges; verify no dangling annotations; save, close, reopen and compare annotation/view/table snapshots and model references. New native files keep a private operation-to-annotation mapping; all Verify/Prepare/Execute/Export gates compare planned view names/orientations/positions/scales, bound annotation identities, dimension values/positions and table rows, and recompute view bounds/intersections. Verify refuses to close a drawing opened before its operation. For plans with `layout`, the executor measures conservative text/line/arrow/leader/table footprints, packs entire view blocks, then remeasures actual block and reserved-area intersections. Reopened snapshots include measured envelopes and line weights. The plan-hash-bound layout record must reproduce the same placement. Review local text and leader crossings inside each block visually; global packing does not prove local legibility.

DWG/PDF: export one sheet with explicit settings, then restore the caller's settings. Hash the DWG. Load that exact file read-only in a separate eDrawings control, require one sheet, print one-to-one to Microsoft Print to PDF and wait for completion and stable file size. Close that viewer's document. Verify source DWG identity, PDF hash, actual page count and paper size, plus exactly two nonempty delivery files. Native SLDDRW-to-PDF Preview is internal and never substitutes for the DWG-derived PDF.

The SOLIDWORKS DWG importer on the development machine changed dimension values (80 became 20) and positions despite explicit settings. That route was rejected. The direct eDrawings route retains nominal dimensions in the tested plate. This does not prove DWG annotations remain associative to the 3D model. eDrawings PDF may outline text and substitute fonts; visually inspect actual typography and Chinese/special symbols. Incomplete extraction receives `PARTIAL_OR_OUTLINED_TEXT_REQUIRES_VISUAL_REVIEW`, not fabricated extraction success. Font mismatch remains unresolved unless the actual output satisfies the selected template's acceptance criteria.

The installed ActiveX host terminates during WinForms disposal. The isolated viewer worker closes its document and then exits its own process, releasing its owned host/window. It does not modify installation files or terminate the user's CAD process. Viewer nonzero exit, timeout, missing report or missing completion event fails the run. CAD and viewer sidecars have unique per-request paths; the runner checks CAD request identity and both process exit codes. A failed/unknown upstream stage cannot be promoted by a later offline visual audit.

## Visual record

After inspecting the rendered **actual output** and comparing it with the native baseline, save `internal/visual-review.json`:

```json
{
  "dwg_sha256": "actual delivered DWG hash",
  "pdf_sha256": "actual delivered PDF hash",
  "checks": {
    "template": true, "views": true, "dimensions": true,
    "symbols": true, "tables": true, "legibility": true, "projection": true
  },
  "observations": "Specific dimensions, tables, symbols and template areas inspected"
}
```

Mark only observed checks true. The verifier rejects stale hashes and incomplete checks. Do not use an automated script to invent a review. Structural output success before visual review is `REVIEW_REQUIRED`. Draft acceptance is never manufacturing release approval.

## Envelope layout evidence, 2026-10-07 (rc3)

Additional preparation regression: a nonadjacent side/top pair could be nonoverlapping yet only 6 mm apart. The shared packer now enforces the full gap inside the orthographic group, preserving projection alignment by moving the top block farther from the front. Forty-one offline tests pass including that reproducer. Import/pruning progress is now recorded. A native bulk-selection experiment rejected drawing annotations and was withdrawn; the original per-annotation selection remains. Native case evidence is recorded separately before any claim of successful recovery.

The subsequent fresh P02 run passes measured envelope clearance, native dimension identity/value checks, save/reopen, fixed font heights and DWG/PDF provenance. Its occupied rectangle area is 35.5%, below the preferred range, and rendered local dimensions remain crowded. Whole-drawing acceptance remains FAILED for 15 unresolved feature definitions. Existing P01/P03 measurements reproduce the same placements under the corrected packer, so their previously frozen PDFs remain unchanged. No geometry-completeness or visual-legibility gate was relaxed.

Forty offline tests pass. The native backend compiles against the installed SOLIDWORKS interop; the C# geometry checks cover counterclockwise quarter arcs, clockwise major arcs and full circles. Layout tests cover asymmetric annotation margins, projection alignment, reserved regions, table stacks, scale/occupation settings, unchanged note content across CRLF/LF, and rejection of altered reopened positions, envelopes or line hierarchy.

Two complex native module runs in a fresh output directory pass source integrity, dimension identity/value checks, measured envelope placement, fixed paper text height, save/reopen, and DWG-derived PDF provenance. Both use 3 mm envelope padding, 12 mm block/table clearance, and usable bounds [35,70,405,282] inside the tested GB A3 frame. P03 retains 36 native dimensions plus three associated overall dimensions; the selected factor is 0.75 and occupied rectangle area is 45.2%. P01 retains 101 native dimensions; its selected factor is 0.5 and occupied area is 37.7%, below the preferred 45%-65% range. This missed composition target remains a review issue, not an accepted aesthetic result.

Actual rendered DWG-derived PDFs preserve the frame, upper-right table placement and visibly heavier model outlines than dimensions. Local text and leader crowding remains inside several view blocks, especially P01; P03 also has stacked bore labels and clustered small/angular dimensions. Global envelope checks do not certify local legibility. Both whole-drawing gates remain FAILED for unresolved nominal geometry definitions (12 features for P03, 19 for P01). Neither run is a complete manufacturing drawing, and these module regressions do not replace or rescore the original first-attempt blind comparison.

An earlier P01 worker exceeded its 360-second limit while repeatedly resolving annotation identities. View-scoped annotation indexing and reuse of measured snapshot bounds removed that repeated COM work; the subsequent fresh P01 run completed within the same limit. The runner default is now 600 seconds and records unique native progress sidecars. The earlier unsaved timeout drawing and preexisting documents were preserved. These observations establish tested module behavior, not arbitrary-model runtime or packing guarantees.

## Observed development evidence, 2026-10-06

Repair regression, 2026-10-07 (rc2): 32 offline tests pass, including full source identity normalization, same-short-name dimensions on different features, explicit hidden-feature options, geometric-audit acceptance wiring and native-validator field compatibility, missing definitions, semantic duplication and dependency cycles. The backend compiles against installed SOLIDWORKS interop. Native temporary-view inventories for five complex parts return 92/79/39/130/44 dimensions; their full source identity sets match the original automation-port runs exactly, with unchanged source hashes. These counts prove import parity, not geometric completeness.

Selective import regression retains eight measured dimensions per part, including a full source identity. All five import reports pass. P01-P04 save/reopen and identity/value/position checks pass. P05 saves but native acceptance rejects four dangling cosmetic-thread annotations inherited into front/isometric views (`孔螺蚊线4`/`孔螺蚊线6`), despite its selected dimensions being non-dangling. That failure remains explicit. The intentionally overbroad 142-dimension P01 request still fails before native save with a detailed missing-import report and a preserved native error. These are module regression drawings with deliberately incomplete coverage; none is certified as a complete manufacturing drawing. The original first-attempt blind comparison is unchanged.

P01 with `include_hidden_features: true` returns 133 actual dimensions, matching 98 of the original 142 requests and still missing 44. Enabling hidden features therefore does not make all inspected parameters transferable; preflight and explicit missing-definition handling remain required.

Independent publication snapshot, 2026-10-07: the complete skill now occupies the root of `solidworks-drafting-skill`. Twenty offline tests and backend compilation pass from that location. Execution-source hashes match the previously tested implementation; this packaging update is not a new native CAD acceptance run. Automatic DimXpert schemes and detail views remain deferred.

Release-candidate checks: 20 new offline tests and seven legacy tests pass; the new C# backend compiles against the installed SOLIDWORKS interop. The final plate run passes native plan identity/value/position checks, source integrity, saved reopen, worker exit codes, DWG/PDF provenance and document cleanup. A separate installed-entry audit is required after copying the package. A native ownership test confirms Verify rejects a preexisting open drawing and leaves it open. Whole-branch review findings were addressed in one repair pass: shared semantic gates, strict coverage IDs and experimental payloads, upstream failure preservation, template-font inheritance, document ownership and unique worker reports.

The approved local GB A3 template was retained after user rejected a replacement A4 frame. Plate orthographic views use 2:1; the isometric uses 1:1; the six-hole schedule sits at upper right. Native snapshot/reopen and exact nominal 80/50/20 dimensions pass; the end-to-end export returns REVIEW_REQUIRED. The original A3 template preview and actual DWG-derived PDF were visually checked for layout. DWG-derived preview retains the frame and dimension values; typography, the top-left template stamp and unfinished title metadata require review.

A simple cylinder reuses its native 70 mm length and creates a measured Ø30 annotation, both visible in actual DWG-derived PDF. Its initial vertex-based overall dimension failed because a cylinder has no usable corner vertices. The corrected plan imports the native length; partial PDF text extraction is correctly left for visual review. This is a simple-cylinder test, not stepped/blind-hole shaft acceptance.

The L-section bracket's exterior dimensions pass, but associated wall-thickness edge matching failed. The initial failure and three deliberate repairs are retained; no completed bracket drawing is claimed. The general edge-to-edge backend therefore remains experimental. A2 printer support, the full advanced fixture set and independent blind reconstruction acceptance are not certified in this release candidate.

User scope update: new automatic DimXpert schemes and native detail views are deferred optional improvements, to be reconsidered after further user tests. Their implementation is not a current acceptance condition. This does not permit omitting a geometric definition when an individual drawing needs an unsupported operation; report that case explicitly. Existing native dimension reuse and existing-PMI import remain in scope.

Preserve all failed reports. After a timeout, inspect first. Retry only in new directories with a concrete cause; at most three repairs for a sample. Close this operation's generated/opened documents promptly, preserve preexisting unsaved documents, release COM references and check available memory before continuing.
