"""permission-matcher.py: a small stand-in for Claude Code's permission matcher.

Nothing here can run Claude Code's own matcher without a model, so the checks
that judge a project's permission rules share this one. It follows the rule
shape documented at https://code.claude.com/docs/en/permissions ("Wildcard
patterns" and "Bash"):

  - a rule matches the whole command text;
  - `*` may sit anywhere and stands for any text, spaces included;
  - everything else is literal, including a space before a `*`, and a colon
    anywhere but a final `:*`;
  - a final `:*` is the same as a final ` *`;
  - a final ` *` that is the rule's only wildcard also matches the bare
    command with nothing after it.

It is fed one command at a time. Claude Code also splits a compound command
and strips wrappers such as `timeout` and leading variable assignments before
it matches; none of the spellings the checks feed it needs that, so it is not
modelled.

A check calls self_test() first, which runs the examples in the
documentation's own table, so a matcher that drifted from the documentation
fails before it judges anything. Run on its own, this file runs that test.
"""

import re
import sys


def compile_rule(rule):
    m = re.fullmatch(r"Bash\((.*)\)", rule, re.S)
    if not m:
        return None
    body = m.group(1)
    if body.endswith(":*"):
        body = body[:-2] + " *"
    pattern = ".*".join(re.escape(part) for part in body.split("*"))
    bare = body[:-2] if body.count("*") == 1 and body.endswith(" *") else None
    return re.compile(pattern, re.S), bare


def matches(rule, command):
    compiled = compile_rule(rule)
    if compiled is None:
        return False
    pattern, bare = compiled
    return pattern.fullmatch(command) is not None or command == bare


def any_match(rules, command):
    return any(matches(rule, command) for rule in rules)


# The documentation's own table, row by row: a rule, the commands it matches,
# and the commands it does not.
DOCUMENTED = [
    ("Bash(npm run build)", ["npm run build"], ["npm run build --watch"]),
    ("Bash(npm run *)", ["npm run build", "npm run test --watch", "npm run"], ["npm install"]),
    ("Bash(git log * main)",
     ["git log --oneline main", "git log -5 main", "git log --output=<file> main"],
     ["git log main", "git push origin main"]),
    ("Bash(git * main)",
     ["git merge main", "git push origin main", "git -c core.fsmonitor=<script> diff main"],
     ["git log"]),
    ("Bash(* --version)", ["node --version", "bash -c 'echo hi' --version"], ["node -v"]),
    ("Bash(ls *)", ["ls -la", "ls"], ["lsof"]),
    ("Bash(ls*)", ["ls -la", "lsof"], []),
    ("Bash(* --help *)", ["npm --help x"], ["npm --help"]),
    ("Bash(ls:*)", ["ls -la", "ls"], ["lsof"]),
    ("Bash(git:* push)", [], ["git push", "git status push"]),
]


# --- file rules ----------------------------------------------------------------
#
# Edit(...) and Read(...) rules follow the documentation's "Read and Edit"
# section. A rule holds a gitignore pattern, anchored by its first characters:
#
#   - `//path` at the filesystem root;
#   - `~/path` at the home folder;
#   - `/path` at the settings source, which for a project's own settings is
#     the session's primary working directory, so in a worktree session it is
#     the worktree, not the main folder;
#   - `path` or `./path` at the current directory.
#
# A rule matches only a file under its anchor. Inside it, `*` stays within one
# path segment and `**` crosses folders. A pattern with no slash, such as
# `.env`, matches at any depth, and so does a deny or ask rule naming a single
# folder, such as `src/**`. Any other shape matches only where it is anchored.
#
# Claude Code checks a file tool against Edit and Read rules only. An Edit rule
# covers every built-in tool that edits a file, Write included, and a Read
# deny rule also blocks Edit and Write on the same path. A path rule for
# Write, NotebookEdit or MultiEdit is accepted but never consulted, so it
# refuses nothing. A bare tool name with no path, such as `Write`, matches that
# tool everywhere.

EDITING_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")


def _glob(pattern):
    """A regular expression for a gitignore pattern, relative to its anchor."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("/**", i) and i + 3 == len(pattern):
            out += "/.*"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return out


def file_rule_matches(rule, tool, path, cwd, project_dir, home, kind="deny"):
    """Whether a file rule applies to a file tool on an absolute path.

    cwd is the session's current directory, project_dir the folder a `/` rule
    anchors at, and home the home folder. kind is "allow", "deny" or "ask".
    """
    m = re.fullmatch(r"(Edit|Read|Write|NotebookEdit|MultiEdit|Glob)(?:\((.*)\))?", rule, re.S)
    if not m:
        return False
    name, body = m.group(1), m.group(2)
    if body is None:
        return name == tool
    if name == "Edit":
        if tool not in EDITING_TOOLS:
            return False
    elif name == "Read":
        if tool not in ("Read",) + EDITING_TOOLS:
            return False
    else:
        return False
    if body.startswith("//"):
        anchor, pattern = "/", body[2:]
    elif body.startswith("~/"):
        anchor, pattern = home, body[2:]
    elif body.startswith("/"):
        anchor, pattern = project_dir, body[1:]
    else:
        anchor, pattern = cwd, body[2:] if body.startswith("./") else body
    anchor = anchor.rstrip("/") + "/"
    if not path.startswith(anchor):
        return False
    relative = path[len(anchor):]
    inner = pattern.rstrip("/")
    # A slash at the front anchors the pattern; only a relative rule may float.
    relative_rule = not body.startswith(("/", "~/"))
    floating = "/" not in inner or (relative_rule and kind != "allow"
                                    and re.fullmatch(r"[^/*]+/\*\*", pattern))
    regex = ("(?:.*/)?" if floating and not pattern.startswith("**") else "") + _glob(pattern)
    if re.fullmatch(regex, relative, re.S):
        return True
    # A folder pattern also covers everything inside the folder.
    return re.fullmatch(regex + "/.*", relative, re.S) is not None


def file_denied(rules, tool, path, cwd, project_dir, home="/home/someone"):
    return any(file_rule_matches(rule, tool, path, cwd, project_dir, home) for rule in rules)


# The documentation's own examples for file rules: a rule, its kind, the tool,
# and the files it matches and does not. P is the primary working directory,
# which is also the current directory, and H the home folder.
P, H = "/work/project", "/Users/alice"
DOCUMENTED_FILES = [
    ("Edit(/docs/**)", "deny", "Edit", [P + "/docs/a.md"], ["/docs/a.md", P + "/.claude/docs/a.md"]),
    ("Read(~/.zshrc)", "deny", "Read", [H + "/.zshrc"], [P + "/.zshrc"]),
    ("Edit(//tmp/scratch.txt)", "deny", "Edit", ["/tmp/scratch.txt"], [P + "/tmp/scratch.txt"]),
    ("Read(src/**)", "deny", "Read", [P + "/src/a.ts", P + "/vendor/pkg/src/lib.js"], []),
    ("Read(src/**)", "allow", "Read", [P + "/src/a.ts"], [P + "/vendor/pkg/src/lib.js"]),
    ("Read(.env)", "deny", "Read", [P + "/.env", P + "/app/.env"], ["/work/.env"]),
    ("Read(**/.env)", "deny", "Read", [P + "/.env", P + "/app/.env"], ["/work/.env"]),
    ("Read(//**/.env)", "deny", "Read", ["/work/.env", "/elsewhere/x/.env", P + "/.env"], []),
    ("Read(//Users/alice/secrets/**)", "deny", "Read", [H + "/secrets/key"], [P + "/secrets/key"]),
    ("Read(~/Documents/*.pdf)", "deny", "Read", [H + "/Documents/a.pdf"], [H + "/Documents/x/a.pdf"]),
    ("Edit(/src/**/*.ts)", "deny", "Edit", [P + "/src/a.ts", P + "/src/x/b.ts"], [P + "/src/a.js"]),
    ("Read(*.env)", "deny", "Read", [P + "/a.env", P + "/x/b.env"], [P + "/a.envy"]),
    ("Edit(src/**)", "allow", "Edit", [P + "/src/app.ts"], [P + "/vendor/pkg/src/lib.js"]),
    ("Edit(src/**)", "deny", "Edit", [P + "/src/app.ts", P + "/vendor/pkg/src/lib.js"], []),
    ("Edit(/src/**)", "deny", "Edit", [P + "/src/app.ts"], [P + "/vendor/pkg/src/lib.js"]),
    ("Edit(**/src/**)", "deny", "Edit", [P + "/src/app.ts", P + "/vendor/pkg/src/lib.js"], []),
    ("Edit(./Finance (2024)/**)", "deny", "Edit", [P + "/Finance (2024)/a.xlsx"], []),
    # An Edit rule covers the Write tool, and a Read deny rule blocks Edit and Write.
    ("Edit(docs/**)", "deny", "Write", [P + "/docs/new.md"], []),
    ("Read(/secrets/**)", "deny", "Write", [P + "/secrets/new.txt"], []),
    # A path rule for Write is never consulted, so it refuses nothing; a bare
    # Write rule matches the tool everywhere.
    ("Write(docs/**)", "deny", "Write", [], [P + "/docs/new.md"]),
    ("Write", "deny", "Write", [P + "/docs/new.md", "/tmp/x"], []),
]


def self_test():
    """Return a list of problems; empty when the matcher agrees with the table."""
    problems = []
    for rule, yes, no in DOCUMENTED:
        for command in yes:
            if not matches(rule, command):
                problems.append("matcher: %s should match %r, as the documentation says" % (rule, command))
        for command in no:
            if matches(rule, command):
                problems.append("matcher: %s should not match %r, as the documentation says" % (rule, command))
    for rule, kind, tool, yes, no in DOCUMENTED_FILES:
        for path in yes:
            if not file_rule_matches(rule, tool, path, P, P, H, kind):
                problems.append("matcher: %s as %s should match %s on %r, as the documentation "
                                "says" % (rule, kind, tool, path))
        for path in no:
            if file_rule_matches(rule, tool, path, P, P, H, kind):
                problems.append("matcher: %s as %s should not match %s on %r, as the "
                                "documentation says" % (rule, kind, tool, path))
    return problems


def section(text, heading):
    """The lines under a `## ` heading, up to the next one. None when absent.

    Two sections of blocked-commands.md carry lists that open with the same
    marker, so a reader that took the first match would read the push lists
    twice and the delete lists never.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip() == heading:
            break
    else:
        return None
    body = []
    for line in lines[i + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def read_list(text, marker, keep, heading=None):
    """The backticked spellings in the bullet list that follows a marker line.

    A bullet may wrap onto indented lines. Only spellings for which keep()
    is true are returned, so prose in backticks is left out. With a heading,
    the marker is looked for only under that `## ` heading. None when the
    heading or the marker is not in the text.
    """
    if heading is not None:
        text = section(text, heading)
        if text is None:
            return None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if marker in line:
            break
    else:
        return None
    items, current = [], None
    for line in lines[i + 1:]:
        if line.startswith("- "):
            if current is not None:
                items.append(current)
            current = line[2:].strip()
        elif line.startswith("  ") and current is not None:
            current += " " + line.strip()
        elif line.strip() == "" and current is None:
            continue
        else:
            break
    if current is not None:
        items.append(current)
    spellings = []
    for item in items:
        spellings += [s for s in re.findall(r"`([^`]+)`", item) if keep(s)]
    return spellings


if __name__ == "__main__":
    found = self_test()
    if found:
        print("\n".join(found))
        sys.exit(1)
    print("  ok: the matcher agrees with every example in the documentation's table")
