# Required tools

The kit runs a few small scripts of its own, and those need three outside tools
before setup can go ahead. `scripts/check-tooling.sh` checks for them and reports
which are ready, so a missing one is caught early rather than at the step that
creates the issues.

- Git, because the kit saves each project version with it.
- The GitHub command line tool, because the pieces are kept as GitHub issues.
  Setup needs it installed and signed in before it founds them.
- python3, because the kit reads the issue list with it to print your pieces.

`jq` is not needed. The kit filters JSON with python3 instead, which is also what
lets the test harness stand in for the GitHub command line tool. A tool used only
to build a release lives in the maintainer source and never reaches a project.

A project on a recipe needs a few more tools, but only at launch. Each recipe
names the command-line tools its launch checks run, on its `Command-line tools:`
line. `check-tooling.sh --recipe <recipe file>` adds one line for each: ready,
or missing and needed before the first `/ship`. A missing one never stops
founding, because a project that uses no recipe needs none of them.

The report also says what the walk-through can look with, since the agent
looks at each piece before it is saved. Poppler's `pdftoppm` turns a PDF into
pictures, LibreOffice's `soffice` turns a Word, PowerPoint, Excel or
OpenDocument file into a PDF, and ImageMagick's `magick` turns an SVG into a
picture. Playwright takes a screenshot of a web page where the coding agent
has no browser tool of its own. Each gets one line: ready, or missing with the
install command for this computer. A missing one never stops founding either,
and the kit never installs it. The walk-through then names what it could not
see, and the piece waits for the person.

The report also says when the project still points at the kit's own
repository, which a whole copy of the kit can keep as its `origin`. It then
asks GitHub nothing more about that repository, and founding opens no piece
there. That line does not stop founding either.

When `check-tooling.sh` reports a tool as missing, `manual-setup.md` guides the
install one step at a time. Keep this list and the script in step: a tool added
to one belongs in the other.

## When GitHub access fails

This applies whenever a kit command needs GitHub, at founding and afterwards.
Run `gh` through the current agent's command tool: a working terminal or
connector does not prove that tool can reach GitHub or write to it.

A network failure or a command refused by the client does not mean the person
is signed out. Request the access needed for the authorised operation through
the client's approval mechanism, then retry it after access is granted. Say:
"GitHub access is blocked in this session; I need it to read or save your pieces."
Do not weaken permission settings, repeat a denied request through a different
tool, or move to an outside terminal unless the person explicitly authorises
that route. If access remains unavailable, name the limitation and keep the
last printout; never treat a failed read as an empty backlog or completed work.

An authentication refusal, including HTTP 401, does not prove sign-out. Compare
`gh auth status --hostname github.com` in the command tool and the person's
terminal. Report only whether `GH_TOKEN` and `GITHUB_TOKEN` exist, since they
override stored credentials. Compare the `gh` path, user, `HOME`, `GH_CONFIG_DIR`
and `XDG_CONFIG_HOME`. Never print a credential or use `--show-token`.
For Codex, follow [the recovery guide](codex-github.md) when networking or
credential access differs between those environments.

If those checks establish that the account is signed out, guide `gh auth login`
in the person's terminal. If it refuses repository access, check the account's permissions for
that repository. Neither is repaired by enabling network access.
