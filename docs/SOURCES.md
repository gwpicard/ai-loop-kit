# Sources

AI Loop Kit took ideas from other people who work in the open. This page names
that work and says what each piece gave. It credits borrowed ideas. It does not
list everything the kit depends on.

The research behind the v1 design is in `docs/design/v1/drafts/`, with its own
links. Code copied from the older kit is listed in `BORROWED.md`.

Nobody named here was asked first. Nobody named here has endorsed the kit.

| Source | What it gave the kit |
|---|---|
| [mattpocock/skills](https://github.com/mattpocock/skills) | The agent's best guess attached to every interview question, the habit of building a reliable way to reproduce a fault before reading any code, and the brief rules that hold a piece to behaviour rather than steps. |
| [Geoffrey Huntley on the Ralph technique](https://ghuntley.com/ralph/) | Changing the instructions and running again when an unattended run goes wrong. |
| [Clayton Farr's Ralph Playbook](https://github.com/ClaytonFarr/ralph-playbook) | The clearest written version of that same rule, compiled from Huntley's technique and credited to him. |
| [METR on reward hacking by recent models](https://metr.org/blog/2025-06-05-recent-reward-hacking/) | The finding that telling a model not to cheat did not change how often it did. A script that lists every changed test works better than an instruction to leave tests alone. |
| [Anthropic on harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | The rule, given to its own agents, that removing or editing a test is unacceptable. It is why the bar a piece is built against is fixed when the piece is ready. It also gave the progress file that a new session reads at the start. |
| [Claude Code's permission rules](https://code.claude.com/docs/en/permissions) | An `ask` rule, which Claude Code checks before any `allow` rule, as the mechanical guard on a merge that goes live. |
| [Anthropic's memory guidance](https://code.claude.com/docs/en/memory) | The limit of fewer than 200 lines for standing instructions, and the habit of trimming what the agent can find in the code. |
| [ETH Zurich's Evaluating AGENTS.md study](https://arxiv.org/abs/2602.11988) | Keeping standing instructions to practices the code cannot show, not a repeat of the repository overview. |
| [GitHub CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) | A short, readable path list beside the rule that applies there. |
| [github/spec-kit](https://github.com/github/spec-kit) | Its `analyze` template: a read-only pass that compares what was promised with what is planned, lists what has nothing behind it, and changes nothing by itself. |
| [OpenSpec concepts](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md) | Carrying a proposed change on the piece and applying it when the work lands. Each requirement is a case that can be checked on its own. |
| [Kiro's proposal to record what a spec was checked against](https://github.com/kirodotdev/Kiro/issues/9435) | Recording a saved code state, so a later change can show how far the spec may have drifted. |
| [doc-drift](https://github.com/sunnydachs/doc-drift) | Its rule that a document may omit but never invent. A document that says less than the project does is not flagged. Only a name that points at nothing is. |
| [Gary Klein, "Performing a Project Premortem"](https://hbr.org/2007/09/performing-a-project-premortem), Harvard Business Review | The pre-mortem: imagine the work has gone live and gone wrong, then ask who noticed and what they saw. Write the answer down before anything is built. |
| [StrykerJS incremental testing](https://stryker-mutator.io/docs/stryker-js/incremental/) and [mutmut](https://mutmut.readthedocs.io/en/latest/) | Breaking only the changed code on purpose to check whether the tests notice, as optional local evidence. |
| [Thoughtworks Technology Radar](https://www.thoughtworks.com/radar) | Reviewing the tools in use on a fixed cycle and publishing each review as a dated view of what moved. The maintainers do this when they check the recipes against the products they name. |
| [coolify-devops](https://github.com/KasperHonore/coolify-devops) | The fields of a hosting request, and the rule that the person carries it to the server by hand and the server does not fetch it. |
| [Playwright](https://playwright.dev/) and [Poppler's `pdftoppm`](https://poppler.freedesktop.org/) | Taking a whole-page screenshot from the command line, and rendering each page of a PDF to an image a model can read. |
