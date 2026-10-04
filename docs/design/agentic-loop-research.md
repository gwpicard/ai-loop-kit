# Agentic loop: the outside work behind it

What the review of outside work found on 2 October 2026, while the decisions in
[agentic-loop.md](agentic-loop.md) were being made. It keeps the findings, the
sources and where the kit stands among related projects, so a later change can
start from them rather than search again.

This is a research record, not a credit list. An idea is credited in
[SOURCES.md](../SOURCES.md) when a piece that uses it lands. Many outside pages
could not be opened from the research environment, so some findings rest on
search summaries; those are marked "secondary".

## Loops and goals

Loop engineering is the 2026 name for designing the loops that prompt coding
agents, rather than prompting them by hand. The inner loop is the agent acting
and checking within one session; the outer loop is a harness that starts it
again with a fresh context. Each loop needs a trigger, an exit condition and a
feedback signal, and automatic checks reject wrong output (secondary: Addy
Osmani, Peter Steinberger, June 2026).

| Loop | Exit | Who judges | Source |
|---|---|---|---|
| Ralph: the same prompt run again and again | A manual stop or an iteration cap | Tests, types and linters | [Ralph playbook](https://github.com/ghuntley/how-to-ralph-wiggum), December 2025 |
| Claude Code goal | A small model reading the transcript says the condition is met | A separate model with no tools | [Claude Code goal](https://code.claude.com/docs/en/goal) |
| Codex goal | The same model marks it complete after a self-audit, or the token budget ends | The same model | Secondary, April 2026 |
| Planner, generator and evaluator | The evaluator's thresholds, agreed before the build | A separate agent using the running app | [Anthropic, harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps), March 2026 |
| Metric loop | A target, or the budget | A fixed scorer the agent cannot edit | [karpathy/autoresearch](https://github.com/karpathy/autoresearch), March 2026 |
| Gauntlet loop | The work wins a blind comparison with a named, fetchable reference | A fresh critic with a yes or no verdict | [robonuggets/gauntlet-loop](https://github.com/robonuggets/gauntlet-loop), 2026 |

The goal judge in Claude Code reads only the transcript, so a goal is only as
strong as what the agent's output proves. Metric loops are safe only with a
scorer the agent cannot reach, a fixed budget per try, a held-out check and
guard measures that act as hard limits. The gauntlet's most common failure is a
vague reference, which lets the critic approve everything.

## Spec-driven tools

| Tool | Gate before building | Held by |
|---|---|---|
| [GitHub Spec Kit](https://github.com/github/spec-kit) | Tasks exist and checklists are complete; `analyze` before building and `converge` after | A script for file existence; the rest is prose |
| Kiro | Requirements, design and tasks, each approved by a person | The interface (secondary) |
| BMAD | A readiness check: pass, concerns or fail | An agent (secondary) |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | Every requirement has a scenario; changes recorded as added, modified and removed, then merged into living specs | Its validator |
| cc-sdd | Each phase approved, tasks marked with boundary and dependencies | A person and validators |

The lessons kept: fix how success is judged before the build; check that the
build did exactly what was asked, including work nobody asked for (Spec Kit's
`converge`); record changes to current behaviour as deltas (OpenSpec); declare
each task's boundary and dependencies (cc-sdd). The most cited failure of these
tools is ceremony: long documents, slow reviews, and the same process for a
one-line fix as for a feature (secondary: Birgitta Böckeler on martinfowler.com,
October 2025; Scott Logic).

## Skill collections and methods

[obra/superpowers](https://github.com/obra/superpowers) gives every task two
review verdicts, one on the spec and one on the code, and four ending statuses
for a builder: done, done with concerns, needs context, blocked.
[mattpocock/skills](https://github.com/mattpocock/skills) separates work ready
for an agent from work ready for a person, and writes a brief of behaviour and
interfaces rather than steps. [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills)
gives a reviewer only the work and the contract, never the author's claim.

[EveryInc's compound engineering](https://github.com/EveryInc/compound-engineering-plugin)
records one lesson per task, and only what the code cannot show, so the next
task starts wiser. [HumanLayer's 12-factor agents](https://github.com/humanlayer/12-factor-agents)
puts human review on research and plans, where it pays most, and keeps passing
output quiet. Beads links discovered work to the task that found it. Gas Town
merges finished work one item at a time and stops for a person on a conflict
(secondary).

## Software factories

Dan Shapiro's levels run from autocomplete to a "dark factory" where nobody
reads the code (secondary, January 2026). StrongDM's factory goes without human
review only because scenarios the builder cannot see score the work against
copies of the outside services (secondary). Stripe's Minions produce about 1,300
pull requests a week from blueprints that mix fixed steps with agent steps, and
people still merge (secondary). Spotify's background agents run fixed verifiers
from a stop hook; agents deleted failing tests to get green, and an LLM judge
was later removed as models improved (secondary).

[Anthropic's data on autonomy](https://www.anthropic.com/research/measuring-agent-autonomy)
shows experienced users approve less and interrupt more: they watch and step in.
Cloud agents fence the agent off: firewalled sandboxes, secrets gone before the
agent starts, pushes allowed only to the agent's branch. An unattended agent
that holds private data, reads unchecked content and can send data out is
Simon Willison's "lethal trifecta".

## Verification and code health

Every team that removed the human found agents weakening tests
([Anthropic, long-running harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents):
"It is unacceptable to remove or edit tests"; ImpossibleBench, 2025). A separate
evaluator tuned to be sceptical works far better than asking a builder to judge
itself. OpenAI's harness engineering post (February 2026) enforces architecture
with lints whose messages tell the agent how to fix the fault, and runs
clean-up agents against drift. Böckeler splits a harness into guides, which act
before the agent, and sensors, which check after (secondary).

Giving the builder the existing tests that guard the code it changes cut
regressions from about 6% to about 2% ([TDAD](https://arxiv.org/abs/2603.17973));
telling it to "do TDD" made them worse. Strong models find code well without a
code graph, and a stored index goes stale; git history of files that change
together catches links a static scan misses.

## Crews and resources

Most failures of systems built from several agents come from their design (MAST,
NeurIPS 2025, secondary). Independent agents multiply each other's errors, and a
central coordinator limits that (Google research, December 2025, secondary).
Parallel builders on one interdependent task overwrite each other
([Anthropic, C compiler](https://www.anthropic.com/engineering/building-c-compiler)).
Debate does no better than a vote, models favour their own output, and a panel
helps only when its members are diverse. Anthropic's lead agent spawned too many
subagents until effort rules were written down
([multi-agent research](https://www.anthropic.com/engineering/multi-agent-research-system)).

Coding agents cap the number of subagents (Claude Code 20, Codex 6) but neither
looks at memory. A real run of ten builders froze a 15 GiB computer for about
four hours. Claude Code's stall timeout misses a builder that keeps reading
without writing.

## Harness engineering

The harness is everything around the model that turns its ability into
reliable work. Each part encodes an assumption about what the model cannot yet
do, so parts should be tested by removing them as models improve. Context files
written by a model were measured to lower success slightly, which is why lessons
become checks first. Scripts should be quiet when they pass and say what to do
next when they fail (secondary: HumanLayer). Without a statement of what an
agent may do outside the code, it reached further measurably more often
(secondary).

## Where the loop kit stands

Most related work sits at one end of the flow. Spec-driven tools stop at a
written plan and gate it with a person reading documents. Loop tools such as
Ralph and goal modes run until a condition holds but have no gate before they
start. Factories either remove the person, at the cost of hidden scenarios and
copies of every outside service, or keep the person on every merge. Skill
collections describe good practice in prose the agent has to remember.

The loop kit joins the two ends with one mechanical seam. Shaping is where the
person's time goes, and the ready gate is the only door into the loop. After
it, the bar decides which loop module builds a piece, the gate script holds the
rules a model would otherwise forget, and anything that needs a person flows
back to shaping rather than being finished by hand.

What sets it apart, as the research found it:

- Shaping is the work and the loop is its consequence, with the person deciding
  and never building, and review that never stops the loop.
- Loop modules chosen by the kind of bar: checks, a metric or a reference. No
  spec-driven tool found has metric or gauntlet loops, and no loop tool found
  has a gate before the loop.
- States, the bar and merges held by a script rather than by prose, with sensors
  that stay and guides that are tested for removal.
- Kickback as the normal route for a gap, so the loop never needs a person.
- Written for people who do not read code: plain sentences, one-line reach
  summaries and two boards.
- The whole life of a tool in a small command set: founding, recipes,
  deployment, upkeep and moving installed projects forward. Most tools stop at
  the pull request.
- Local and free of any service: it runs on the person's computer and GitHub,
  and sizes itself to the computer.
- Autonomy that a project earns from measured clean runs.
- Small crews fixed in shaping, where many tools let a model decide how many
  agents to start.

## Deliberately left out

A permanent model judge. Agent hierarchies with named roles such as mayors and
refineries. Specs as the source that code is regenerated from. A spec, plan,
task list and checklist for every piece. Coverage or mutation scores as gates.
A stored code graph or index. Debate between agents. Prescribed TDD steps
inside a loop.
