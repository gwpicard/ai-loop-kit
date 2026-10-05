# Working rules

<!-- The rules a build and a review follow in this project, written for the
agent first. -->

## Areas

<!-- Every folder of the project belongs to one named area, so a piece's
Boundary: and Reaches: lines always name real places in the code. Each area is
one line, `- <name>: <path>, <path>`, with folders and files as paths. An area
whose folder does not exist yet is written `- <name>: none yet`, and the piece
that creates the folder adds its path in the same save. An area name holds no
comma and no colon.

Under an area, at most one indented `sensitive: <name>` line points at the line
of that name under `Sensitive areas:` in the masterplan's build-path section,
and at most one indented `boundary:` line names the one boundary the area must
not cross. Hidden top-level folders, files at the project root and `changes/`
belong to no area.

Change the map in the same save as the code it describes. Run
`python3 .agents/tools/area-map.py check` to see whether it is still true. For
example:

- billing: src/billing/, src/rules/refunds.ts
  sensitive: money
  boundary: reached only through src/billing/charge.ts
- reports: src/reports/
- vendored libraries: vendor/
-->

- project records: docs/
