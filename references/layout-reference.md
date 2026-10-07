# Layout reference and decisions

Reviewed source: [Innerscene drawing library](https://www.innerscene.com/tools/library/drawings/format/dwg), specifically [dimensioned hub flange](https://www.innerscene.com/tools/library/drawings/hub-flange-drawing-dimensioned-52ff43f4). The downloaded DXF was parsed and rendered locally for layout inspection. Raw reference drawings stay outside this package.

Observed in that file: A4 landscape, 297 × 210 mm outer rectangle and 10 mm inset border; a dominant flange view in the left region; a section in the right region; aligned centres; a compact bottom-right title block; a combined six-hole/PCD note; diameter dimensions use different diagonal directions. These are observations from one mechanical example, not a claim that the whole library follows a single standard. Its dimension block text is unusually small; keep the selected readable drawing font instead of copying that defect.

Use its composition: give the principal view enough space to read its features, place supporting views/sections beside it, group repeated hole information, and reserve the title block. Determine scale from the usable drawing area, not from the physical size of the model. Uniformly scale associated orthographic views; keep dimension values as the true model measurements. Detail views may use a separately labelled scale.

The planner compares tables beside the views and below them. The user subsequently confirmed the existing GB A3 template and rejected replacing its frame. With that template's actual reserved title/stamp regions, the synthetic plate uses 2:1 orthographic views, an upper-right schedule and a 1:1 isometric below it. The reference informs composition only. Actual annotation bounds and a PDF visual review remain necessary.

Quality decisions:

- Preserve the approved template and use the largest fitting common view scale within its usable area; select another paper only with a matching approved template.
- Balance the occupied envelope across the usable frame; avoid a small cluster surrounded by unused paper.
- Keep projection alignment and consistent orthographic scale. Change centres, gaps and dimension lanes together.
- Use tables or combined callouts where they reduce clutter, retaining feature IDs, units, origin, axes and source evidence.
- Do not turn the example's 45° diameter direction into a universal rule.
