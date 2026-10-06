# Working rules

<!-- The rules a build and a review follow in this project, written for the
agent first. -->

## Areas

The project's areas are in the file `docs/area-map`, not here. It holds one
`<pattern> <area>` line for each rule, in the style of a CODEOWNERS file, and the
last matching line wins. Run `python3 .agents/tools/area-map.py check` to see
whether it is still true. Change the map in the same save as the code it
describes.
