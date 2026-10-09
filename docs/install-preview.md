# Installing the attended preview

This is the proposed distribution route for the attended preview. It is not an
invitation to install today's development tree. The maintainer must first finish
the preview gates and publish the public `v0.1.0` release. Real Claude installation
has not been rehearsed by the automated checks.

After publication, add the tagged GitHub catalogue in Claude Code:

```text
/plugin marketplace add gwpicard/ai-loop-kit#v0.1.0
/plugin install ai-loop-kit@ai-loop-kit
```

The catalogue's `./kit` source selects the plugin within the same release. The
plugin manifest supplies its version. The catalogue does not repeat that version
or try to embed its own future commit SHA. See Claude's
[marketplace reference](https://code.claude.com/docs/en/plugins/marketplace-reference)
and [hosting guide](https://code.claude.com/docs/en/plugins/host-marketplace).

Founding verifies the installed plugin against the public release before writing
project files. It fetches `v<manifest version>` anonymously from the fixed public
repository, resolves the tag to a full commit SHA and compares the entire shipped
file inventory, including executable status. Branch names, abbreviated SHAs,
missing versions and modified installed files refuse. There is no fallback to
`main` or a private repository.

The generated project's checks fetch that verified SHA, check the checkout's
identity and run scripts from `.kit/kit`. A moved release tag cannot update an
existing baseline or its generated check. Conflicting state refuses and stays
available for inspection.

Version records live beneath the existing machine-local data home, outside both
the project and the plugin cache:

```text
versions/gwpicard/ai-loop-kit/ai-loop-kit/releases/v0.1.0.json
```

Each release has a separate record. The plugin cache path does not select its
identity, so relocating the same unmodified release keeps its baseline. Use the
same `AI_LOOP_KIT_DATA` home after relocation. Claude caches installed plugin
versions in separate folders; see the
[loading reference](https://code.claude.com/docs/en/plugins/loading).

A legacy cache-local `version.json` supplies no release identity. Setup must
revalidate its hashes against the public release before creating the stable
record. It keeps the legacy file and any existing baseline. An invalid record or
conflict refuses; do not remove it to bypass the check. Updating absolute paths
in settings and hooks is a separate migration step.

A dry run requires an existing verified baseline. It rechecks the installed
content without fetching, creating scratch, locks, directories or records. First
verification needs a normal setup run with the release tag. An explicit full SHA
is accepted only when an existing verified release record already binds it.

The offline distribution checks use local Git stand-ins. They do not establish
that the release exists publicly, that Claude accepts the installation, or that a
real model session completes the attended workflow. Those remain preview gates.
