# AI Loop Kit

AI Loop Kit helps you shape software work, build it with coding agents and check
the result. Each piece is a GitHub issue; gate scripts move it through the loop.

Version 0.1.0 is an early field-test preview for attended runs on your own
computer, using Claude Code. Stay available to read refusals and answer
questions. It is unfinished software, not the full v1.0 design.

## Install after publication

The maintainer must publish the public v0.1.0 release first. These instructions
do not establish that the tag or release already exists. Do not install today's
development branch as a release.

After publication, run these commands in Claude Code:

```text
/plugin marketplace add gwpicard/ai-loop-kit#v0.1.0
/plugin install ai-loop-kit@ai-loop-kit
```

The tagged catalogue selects the plugin in kit/. Setup verifies its shipped
content against the public release and pins generated checks to the resolved
commit. The [installation guide](docs/install-preview.md) explains version
records, relocation and refusals. This route is checked with local stand-ins;
real Claude installation has not been rehearsed.

Start with setup, then shape one piece and run it. The maintainer will try these
skills in a scratch project and use the findings to choose the next fixes.

## Known gaps

This preview has no GitHub App, walk-away runs or deployment. Before the App,
follow the gate's person-run GitHub steps. Use a scratch project and data you
can afford to lose. Read [SECURITY.md](SECURITY.md) before trying it.

The command guard still misses clustered short wrapper options. Common
settings denials provide a second layer but do not close that parser hole.
Reviewer output authority and readback hardening remain unfinished. Do not
treat builder/reviewer permissions or the sandbox as proved isolation.

Unchecked dependency identity and origin repairs are deferred. New-test
checking has a separate checker stage; complete attempt enforcement remains
open. Judge execution inventories and their acceptance consumers are not
fully hardened. Frozen-spec whitespace, fetched-main baselines, accepted judge
recovery and safe integration repairs also remain unfinished.

Risk acceptance, hidden cases, records, spend limits and several other core
repairs remain open. Measurement/reference judge routes, controlled judge
assembly and hosted dependency/closing-piece checks are later work. The
[core review](docs/design/v1/core-review.md) and
[design](docs/design/v1/design.md) describe those areas; neither is a claim that
this preview meets the whole design.

No real-model hardening batch or release rehearsal ran for this light preview.
Automated checks and stand-ins do not prove real skill or sandbox behaviour.
Report what setup, shape or run actually does; field-test blockers come next.

## Support

Use [CONTRIBUTING.md](CONTRIBUTING.md) for ordinary reports and
[private vulnerability reporting](https://github.com/gwpicard/ai-loop-kit/security/advisories/new)
for security problems. Keep secrets and personal project data out of public
reports. The kit is licensed under [MIT](LICENSE).
