# Completion report

The message /setup-ai-build-kit ends with. Lead with what's ready, where it's saved,
whether anything was uploaded, and the next command to type. Never lead with a
checkpoint reference, Git state, package-manager command, port, branch, or
remote status.

## Translate before reporting

Internal facts recorded for later agents, and what the user hears instead:

- `npm test` passes -> "The automatic project check passed."
- `npm start` serves a local address -> "The private preview opened successfully."
- the working tree is clean -> "All setup work has been saved."
- the current branch is ahead of its remote -> "The saved work has not been uploaded."
- founding saved on a branch other than the default -> "The setup is saved on the branch [name], and reaches [the default branch] when that branch is merged."
- the commit identifier -> only in the checkpoint reference at the very end, never leading the report.
- no push occurred -> "No code was uploaded or published."
- the online repository holds none of the project's code yet, so the first push waits for a yes -> "The code stays on this computer until your first build asks you before putting it online."
- the pieces were opened as issues -> "The build steps are listed as issues in the project's online repository."
- `Recipe: <file name>.md` in AGENTS.md -> "The tool will run on [the recipe's name, from its file], and the kit can check its launch steps."
- the recipe's tool report, on the same line -> "This computer has the tools those checks use." or "Before the first launch this computer needs [each missing tool, in plain words]; that is on the plan as a setup task."
- `Recipe: none` in AGENTS.md -> "The tool runs on a stack the kit has no recipe for, so it cannot check the launch steps a recipe would."
- `Project check:` names a workflow of the project's own -> "Your project's own automatic check stays the one that runs on every change, and the kit added no check beside it."
- that line ends `; kit steps not added` -> "Your own check does not count the length of the project's instructions or check the sensitive-area map, so /maintain measures both each month instead."
- an adopted project keeps its own AGENTS.md, and it is above 200 lines -> "Your project's instructions are [the count] lines, above the 200 its automatic check allows, so that check will show red until you type /maintain, which moves the detail to where it belongs."

These commands and states stay wherever agents already keep them (AGENTS.md,
the changelog); the report never leads with them.

## Shape

Include only the subsections that apply to this project; skip the rest
rather than leaving a placeholder line unfilled. The checkpoint reference
belongs at the very end, for troubleshooting only, and it is the one line that
is never skipped.

Read the checkpoint back before writing any of this, and carry its reference
into the report from what you read. Where there is no checkpoint beyond the
state the project started in, the report is not due: go and save one. Never
write that the work is saved on the strength of having meant to save it. A run
once ended "Everything's set up and saved" over a project holding nothing but
its opening commit, and the person had no way to tell.

Naming the reference is what makes that impossible to do by accident, because
there is no reference to name for a checkpoint that was never taken.

End with a clean cut, not an offer to build. Say plainly that setup is done and
the work is saved, and say the empty project is expected rather than broken.
Founding takes each piece it shapes no further than `shaping:spec`, because
writing the acceptance checks pushes a branch and founding uploads no code. So
name the pieces waiting in spec, with the first one and a rough, honest time,
and point at `/shape` to take the first piece on from there, ideally in a fresh
session so the founding conversation does not carry into it. Once a piece is
ready, `/implement` builds it. Do not offer to build the first piece in this
session; founding a project and building it are separate, deliberate steps. On
an adopted project that is not empty, drop the "this is normal" line and name
the first outstanding piece instead.

Do not tell the person to push the founding checkpoint from this report.

```md
# Your [project name] is ready to build

The initial setup is complete.

## What is ready

- The purpose of the tool, its intended users, and its access rules are written down.
- The work has been divided into [number] small build steps.
- A separate review checked the plan, and any important findings were resolved.
- [What the tool will run on, whether the kit can check its launch steps, and whether this computer has the tools those checks use.]
- The automatic project check passed.
- The instructions for opening the private preview were tested successfully.

## Where it is saved

A checkpoint has been saved inside the project on this computer.
[Only where founding saved on a branch other than the default:] The setup is
saved on the branch `[branch]`, and reaches `[default branch]` only when that
branch is merged.

No code was uploaded or published. The build steps are listed as issues in the
project's online repository, which is where the kit keeps the work still to do.
[Only where the online repository holds none of the project's code yet:] The
code stays on this computer until your first build asks you before putting it
online.
[State whether an online project copy exists and whether it was updated.]

Private preview address: `[address]`

This address works only on this computer while the preview is running.

## What to do next

Setup is done and your work is saved. Your project is empty right now, which is
how it should look at this point, not a sign anything went wrong. The plan holds
[number] small build steps, and [the number in spec] of them wait in spec for
their acceptance checks. The first is [first step name], about [rough time].

Then start a fresh chat and type `/shape` to take it on from there. Once a
piece is ready, `/implement` builds it. `/what-now` tells you where things
stand any time.

Checkpoint reference: `[short reference]`
```
