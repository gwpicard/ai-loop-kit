# Capability check

Determine what the current harness and repository can actually do. Do not ask
the user to configure optional features before the project interview.

Check:

1. Repository files can be read and edited.
2. Shell commands can run.
3. Git is available and this is a repository.
4. The current project state is understood.
5. A suitable name and email label are configured for saving project versions.
6. An online repository exists, if the selected route will require sharing.
7. The current user has access to that online repository, when required.
8. Online authentication works, when uploads, pull requests, or online checks
   are required.
9. The project can be started or its runtime can be installed.
10. The test or smoke-check command can be discovered or created. Record the
    project check as the capability profile's `Project check:` line, as
    `project-check.md` says.
11. What the walk-through can look with. Record a `Walk-through eyes:` line in
    the capability profile: the browser tool the coding agent offers, or
    `none`; Playwright present or not; and each of `pdftoppm`, `soffice` and
    `magick` present or not. Section-builder's step 6 says how each is used.
12. An independent-review route exists: subagent, separate session, or a
    user-opened clean chat.
13. A reach-check engine is recorded. Prefer the harness's language server or
    Serena, then a related-test or affected-code command, then a graph tool the
    person already installed. Where none exists, record that the agent reads
    imports and callers directly.
14. Hooks and mechanical command blocks are recorded as optional enhancements,
    never assumed. Record whether the harness runs anything when a session
    opens. When it does not, the check-up reminder reaches the person through
    `/what-now` instead.

15. The pieces are kept as issues, which the kit requires: the GitHub command
    line tool is installed and signed in, and issues are switched on for the
    repository.
16. The label set can be put in order: the signed-in account can create and
    delete labels on the repository.

`scripts/check-tooling.sh` is the machine check behind items 3, 11, 15, and 16.
It reports whether Git, the GitHub command line tool, and python3 are present,
whether the account is signed in with issues switched on and labels it can
order, and which of Playwright and the three renderers are here. The browser
tool is the coding agent's own, so confirm that one by hand.
`required-tools.md` lists what it checks and why. Run it first, then confirm the
rest of this list by hand.

Where that tool is missing or nobody is signed in, the pieces cannot be kept as
issues yet, and the kit keeps them there. This is a required setup step rather
than an optional one: guide the person through installing and signing in to the
GitHub command line tool, following `manual-setup.md`, before the pieces are
founded. Where the repository has issues switched off, say what you found and
offer to switch them on. Do not switch them on yourself, because it changes a
setting on something the person owns.

Where the account cannot create or delete labels, which is what a collaborator
without write access will find, the pieces still become issues and the work
still goes ahead. Say which labels could not be made and which of GitHub's own
could not be removed. A missing label costs a little clarity on the list; it
stops nothing.

Where `origin` is the kit's own repository, which a whole copy of the kit can
keep, the report says so and skips the issue and label lookups. That
repository is not the person's, so nothing is opened or pushed there. Founding
asks for their own before the first issue, and carries on with none as it does
when no repository exists.

A remote address is never treated as proof that the current person has an
account or access to it. A previous commit's author is never treated as the
current person's identity.

Write the result into AGENTS.md under Capability profile.

For every missing capability, choose one:

- continue with a safe fallback;
- create a setup task;
- reduce automation;
- stop because the current build path requires it.

Never claim "works in this harness" merely because an adapter folder exists.
